from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import subprocess

app = Flask(__name__)
CORS(app)  # Autoriser les requêtes depuis ton HTML




@app.route('/')
def bnjr():
    return "Bonjour! Le serveur est opérationnel."
# ------------------ Dossiers ------------------ #
BASE_STATIC = "static"
UPLOAD_FOLDER = os.path.join(BASE_STATIC, "uploads")
SEGMENTS_FOLDER = os.path.join(BASE_STATIC, "segments")
RESIZED_FOLDER = os.path.join(BASE_STATIC, "segments_resized")  # Nouveau dossier

# Création automatique des dossiers si inexistants
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEGMENTS_FOLDER, exist_ok=True)
os.makedirs(RESIZED_FOLDER, exist_ok=True)

# ------------------ SEGMENTATION ------------------ #
@app.route('/segment', methods=['POST'])
def segment_video():
    if 'video' not in request.files:
        return jsonify({'error': 'Aucune vidéo envoyée.'}), 400

    video = request.files['video']
    duration = request.form.get('duration', 10)

    # Sauvegarde de la vidéo
    input_path = os.path.join(UPLOAD_FOLDER, video.filename)
    output_pattern = os.path.join(SEGMENTS_FOLDER, 'segment_%03d.mp4')
    video.save(input_path)

    try:
        # FFmpeg pour découper la vidéo
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c', 'copy',
            '-map', '0',
            '-segment_time', str(duration),
            '-f', 'segment',
            output_pattern
        ]
        subprocess.run(cmd, check=True)

        return jsonify({
            'message': '✅ Segmentation terminée avec succès.',
            'uploaded_file': input_path,
            'segments_folder': SEGMENTS_FOLDER
        })

    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Erreur FFmpeg : {str(e)}'}), 500

# ------------------ CHANGER RESOLUTION ------------------ #
@app.route('/change_resolution', methods=['POST'])
def change_resolution():
    if 'video' not in request.files or 'resolution' not in request.form:
        return jsonify({'error': 'Fichier ou resolution manquante.'}), 400

    video = request.files['video']
    resolution = request.form['resolution']  # ex: "1920x1080"
    try:
        width, height = map(int, resolution.split('x'))
    except ValueError:
        return jsonify({'error': 'Format de résolution invalide. Ex: 1920x1080'}), 400

    # Sauvegarde de la vidéo
    input_path = os.path.join(UPLOAD_FOLDER, video.filename)
    output_path = os.path.join(RESIZED_FOLDER, f"res_{video.filename}")  # Nouveau dossier
    video.save(input_path)

    try:
        # FFmpeg pour redimensionner
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', f'scale={width}:{height}',
            '-c:a', 'copy',
            output_path
        ]
        subprocess.run(cmd, check=True)

        return jsonify({
            'message': '✅ Résolution modifiée avec succès.',
            'uploaded_file': input_path,
            'resized_file': output_path,
            'resized_folder': RESIZED_FOLDER
        })

    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Erreur FFmpeg : {str(e)}'}), 500

# ------------------ LANCEMENT ------------------ #
if __name__ == '__main__':
    print("⚡ Serveur Flask démarré sur http://127.0.0.1:5000")
    app.run(debug=True)
