import json
import cv2
import numpy as np
import face_recognition
from flask import Flask, render_template, Response, request, jsonify
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

# Ensure directories exist
ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)

detector = AccessoryDetector()

class FaceRegistry:
    def __init__(self):
        self.known_encodings = []
        self.known_names = []
        self.user_profiles = {}
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
        if not self.known_encodings: return "Unknown", None
        matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.52)
        if True in matches:
            face_distances = face_recognition.face_distance(self.known_encodings, encoding)
            best_match_index = np.argmin(face_distances)
            name = self.known_names[best_match_index]
            return name, self.user_profiles.get(name)
        return "Unknown", None

registry = FaceRegistry()

# Utility to convert Base64 from Browser to OpenCV Image
def base64_to_cv2(base64_string):
    header, encoded = base64_string.split(",", 1)
    nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

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
            name, _ = registry.recognize(enc)
            return jsonify({"name": name})
    except Exception as e:
        print(f"Error processing frame: {e}")
        
    return jsonify({"name": "Unknown"})

@app.route('/register_remote', methods=['POST'])
def register_remote():
    data = request.json
    name = data.get('name')
    try:
        frame = base64_to_cv2(data['image'])
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        
        if locs:
            enc = face_recognition.face_encodings(rgb, [locs[0]])[0]
            filename = f"{name}_{datetime.now().strftime('%H%M%S')}.npy"
            np.save(ENCODINGS_DIR / filename, enc)
            
            registry.user_profiles[name] = {
                "registered_on": str(datetime.now().date()), 
                "notes": "Remote Registration"
            }
            with open(USERS_FILE, "w") as f: 
                json.dump(registry.user_profiles, f)
            
            registry.reload()
            return jsonify({"message": f"Successfully registered {name}"})
    except Exception as e:
        return jsonify({"message": f"Registration error: {str(e)}"}), 400
        
    return jsonify({"message": "No face detected in capture"}), 400

@app.route('/detail/<name>')
def detail(name):
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    city = request.args.get('city', 'Delhi')
    mask_status = request.args.get('mask', 'No Mask')
    glasses_status = request.args.get('glasses', 'No Glasses')
    
    acc = {"mask": mask_status, "glasses": glasses_status}
    loc_query = f"{lat},{lon}" if lat and lat != "null" else city
    weather = get_weather(loc_query)
    profile = registry.user_profiles.get(name, {"notes": "Guest"})
    
    # In remote mode, we don't have a server-side camera to check
    # We default to standard recommendations or can pass last known acc from frontend
    recs = generate_recommendation(weather, False, False)
    
    return render_template('detail.html', name=name, profile=profile, 
                           weather=weather, recs=recs, acc=acc)

if __name__ == '__main__':
    # No internal ngrok, handled by Colab Cell
    app.run(host='0.0.0.0', port=5000)
