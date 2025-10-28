from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import subprocess

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Serveur Flask OK"

if __name__ == "__main__":
    app.run(debug=True)
