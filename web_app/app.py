import json
import cv2
import numpy as np
import face_recognition
from flask import Flask, render_template, request, jsonify
from pathlib import Path
from datetime import datetime
import base64
from core.accessory_engine import AccessoryDetector
from backend.weather_api import get_weather
from backend.recommendation_engine import generate_recommendation
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
ENCODINGS_DIR = DATA_DIR / "encodings"
USERS_FILE = DATA_DIR / "registered_users.json"
ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)
detector = AccessoryDetector()
class FaceRegistry:
    def __init__(self):
        self.user_profiles = {}
        self.known_encodings = []
        self.known_names = []
        self.reload()
    def reload(self):
        self.known_encodings = []
        self.known_names = []
        if USERS_FILE.exists():
            with open(USERS_FILE, "r") as f:
                self.user_profiles = json.load(f)
        for file in ENCODINGS_DIR.glob("*.npy"):
            self.known_encodings.append(np.load(file))
            self.known_names.append(file.stem.split('_')[0])
    def recognize(self, encoding):
        if not self.known_encodings: return "Unknown"
        matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.5)
        if True in matches:
            best_match_index = np.argmin(face_recognition.face_distance(self.known_encodings, encoding))
            return self.known_names[best_match_index]
        return "Unknown"
registry = FaceRegistry()
def base64_to_cv2(base64_string):
    try:
        if not base64_string or ',' not in base64_string:
            return None
        encoded_data = base64_string.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        if nparr.size == 0:
            return None
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"Decode Error: {e}")
        return None
@app.route('/process_remote_frame', methods=['POST'])
def process_remote_frame():
    data = request.json
    frame = base64_to_cv2(data.get('image', ''))
    if frame is None:
        return jsonify({"name": "Unknown", "status": "empty_frame"})
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/process_remote_frame', methods=['POST'])
def process_remote_frame():
    data = request.json
    try:
        frame = base64_to_cv2(data['image'])
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        
        if locs:
            enc = face_recognition.face_encodings(rgb, [locs[0]])[0]
            name = registry.recognize(enc)
            acc = detector.analyze(frame, locs[0])
            return jsonify({
                "name": name,
                "mask": acc.get('mask', 'No Mask'),
                "glasses": acc.get('glasses', 'No Glasses')
            })
    except Exception as e:
        print(f"Server Error: {e}")
    return jsonify({"name": "Unknown"})
@app.route('/detail/<name>')
def detail(name):
    city = request.args.get('city', 'Ghaziabad')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    mask = request.args.get('mask', 'No Mask')
    glasses = request.args.get('glasses', 'No Glasses')

    weather = get_weather(f"{lat},{lon}" if lat and lat != "null" else city)
    recs = generate_recommendation(weather, mask == 'Mask', glasses == 'Glasses')
    profile = registry.user_profiles.get(name, {"notes": "Guest", "registered_on": "N/A"})

    return render_template('detail.html', name=name, profile=profile, 
                           weather=weather, recs=recs, 
                           acc={"mask": mask, "glasses": glasses})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
