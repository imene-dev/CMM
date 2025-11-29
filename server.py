from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, json, subprocess, math, threading

app = Flask(__name__, static_folder="static")
CORS(app)

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
SEGMENTS_FOLDER = os.path.join(app.static_folder, "segments")
RESIZED_FOLDER = os.path.join(app.static_folder, "segments_resized")
JSON_PATH = os.path.join(app.static_folder, "segments_info.json")

for folder in [UPLOAD_FOLDER, SEGMENTS_FOLDER, RESIZED_FOLDER]:
    os.makedirs(folder, exist_ok=True)


def run_ffmpeg(cmd):
    """Exécute ffmpeg silencieusement."""
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def fast_convert(in_path, out_path, scale):
    """Conversion rapide avec ultrafast preset."""
    run_ffmpeg([
        "ffmpeg", "-y", "-i", in_path,
        "-vf", f"scale={scale}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        out_path
    ])


def process_segment(video_path, duration):
    """Découpe la vidéo + crée les versions multi-résolution."""

    # Durée totale
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    total_duration = float(result.stdout.strip())
    num_segments = math.ceil(total_duration / duration)

    resolutions = {
        "360p": "640x360",
        "480p": "854x480",
        "720p": "1280x720",
        "1080p": "1920x1080",
        "4k": "3840x2160"
    }

    segments_info = []

    for i in range(num_segments):
        start = i * duration
        segment_name = f"segment_{i+1}.mp4"
        segment_path = os.path.join(SEGMENTS_FOLDER, segment_name)

        # Extraction rapide du segment
        run_ffmpeg([
            "ffmpeg", "-y", "-i", video_path,
            "-ss", str(start),
            "-t", str(duration),
            "-c", "copy",
            segment_path
        ])

        versions = {}
        threads = []

        # Génération des différentes résolutions
        for label, res in resolutions.items():
            out_name = f"{os.path.splitext(segment_name)[0]}_{label}.mp4"
            out_path = os.path.join(RESIZED_FOLDER, out_name)

            t = threading.Thread(target=fast_convert, args=(segment_path, out_path, res))
            t.start()
            threads.append(t)

            versions[label] = f"static/segments_resized/{out_name}"

        for t in threads:
            t.join()

        segments_info.append({
            "name": segment_name,
            "versions": versions
        })

    with open(JSON_PATH, "w") as f:
        json.dump(segments_info, f, indent=4)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/segmentation")
def segmentation():
    return send_from_directory(".", "segmentation.html")


@app.route("/segment", methods=["POST"])
def segment_video():
    """Upload + segmentation."""
    file = request.files.get("video")
    duration = int(request.form.get("duration", 10))

    if not file:
        return jsonify({"success": False, "error": "Aucune vidéo envoyée"}), 400

    video_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(video_path)

    # Nettoyage
    for folder in [SEGMENTS_FOLDER, RESIZED_FOLDER]:
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))

    threading.Thread(target=process_segment, args=(video_path, duration)).start()

    return jsonify({"success": True, "message": "Segmentation lancée ✅"})


@app.route("/segments_info")
def get_segments_info():
    """Retourne les infos + vérifie si certains segments manquent."""
    if not os.path.exists(JSON_PATH):
        return jsonify({"ready": False})

    with open(JSON_PATH, "r") as f:
        data = json.load(f)

    existing_segments = []

    for seg in data:
        segment_file = os.path.join(SEGMENTS_FOLDER, seg["name"])
        if os.path.exists(segment_file):
            existing_segments.append(seg["name"])
        else:
            existing_segments.append(None)  # manquant

    return jsonify({"ready": True, "segments": existing_segments})


@app.route("/set_segment_resolution", methods=["POST"])
def set_segment_resolution():
    """Applique une résolution à tous les segments."""
    req = request.get_json()
    resolution = req.get("resolution")

    resolutions = {
        "360p": "640x360",
        "480p": "854x480",
        "720p": "1280x720",
        "1080p": "1920x1080",
        "4k": "3840x2160"
    }

    if resolution not in resolutions:
        return jsonify({"error": "Résolution invalide"}), 400

    scale = resolutions[resolution]

    def convert_all():
        for f in os.listdir(SEGMENTS_FOLDER):
            if f.endswith(".mp4"):
                in_path = os.path.join(SEGMENTS_FOLDER, f)
                out_name = f"{os.path.splitext(f)[0]}_{resolution}.mp4"
                out_path = os.path.join(RESIZED_FOLDER, out_name)
                fast_convert(in_path, out_path, scale)

    threading.Thread(target=convert_all).start()

    return jsonify({"success": True, "message": f"Conversion globale en {resolution} lancée."})


@app.route("/recreate_segment/<int:index>", methods=["POST"])
def recreate_segment(index):
    """Recrée un segment manquant."""
    if not os.path.exists(JSON_PATH):
        return jsonify({"error": "Pas d'informations de segments"}), 400

    with open(JSON_PATH, "r") as f:
        data = json.load(f)

    if index >= len(data):
        return jsonify({"error": "Index hors limite"}), 400

    video_files = os.listdir(UPLOAD_FOLDER)
    if not video_files:
        return jsonify({"error": "Aucune vidéo d’origine trouvée"}), 400

    video_path = os.path.join(UPLOAD_FOLDER, video_files[0])
    duration = 10
    start = index * duration

    segment_name = f"segment_{index+1}.mp4"
    segment_path = os.path.join(SEGMENTS_FOLDER, segment_name)

    run_ffmpeg([
        "ffmpeg", "-y", "-i", video_path,
        "-ss", str(start),
        "-t", str(duration),
        "-c", "copy",
        segment_path
    ])

    resolutions = {
        "360p": "640x360",
        "480p": "854x480",
        "720p": "1280x720",
        "1080p": "1920x1080",
        "4k": "3840x2160"
    }

    threads = []
    for label, res in resolutions.items():
        out_name = f"{os.path.splitext(segment_name)[0]}_{label}.mp4"
        out_path = os.path.join(RESIZED_FOLDER, out_name)
        t = threading.Thread(target=fast_convert, args=(segment_path, out_path, res))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return jsonify({"success": True, "message": f"Segment {index+1} régénéré."})


if __name__ == "__main__":
    app.run(debug=True)
