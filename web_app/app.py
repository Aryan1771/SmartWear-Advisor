import json, cv2, numpy as np, face_recognition, base64, os
from flask import Flask, render_template, request, jsonify
from pathlib import Path
from datetime import datetime
from core.accessory_engine import AccessoryDetector
from backend.weather_api import get_weather
from backend.recommendation_engine import generate_recommendation

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
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
        # Tolerance 0.5 is balanced for mobile camera quality
        matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.5)
        if True in matches:
            distances = face_recognition.face_distance(self.known_encodings, encoding)
            best_match_index = np.argmin(distances)
            return self.known_names[best_match_index]
        return "Unknown"

registry = FaceRegistry()

def base64_to_cv2(b64_str):
    try:
        encoded_data = b64_str.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except: return None

@app.route('/')
def index(): return render_template('index.html')

@app.route('/process_remote_frame', methods=['POST'])
def process_remote_frame():
    data = request.json
    frame = base64_to_cv2(data.get('image', ''))
    if frame is None: return jsonify({"name": "Unknown", "status": "empty"})

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb)
    
    if locs:
        enc = face_recognition.face_encodings(rgb, [locs[0]])[0]
        name = registry.recognize(enc)
        acc = detector.analyze(frame, locs[0])
        return jsonify({
            "name": name,
            "box": locs[0], # [top, right, bottom, left]
            "mask": acc.get('mask', 'No Mask'),
            "glasses": acc.get('glasses', 'No Glasses')
        })
    return jsonify({"name": "Unknown"})

@app.route('/register_remote', methods=['POST'])
def register_remote():
    data = request.json
    name = data.get('name')
    frame = base64_to_cv2(data.get('image'))
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb)
    if not locs: return jsonify({"message": "No face detected!"})
    
    encoding = face_recognition.face_encodings(rgb, [locs[0]])[0]
    np.save(ENCODINGS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d')}.npy", encoding)
    
    registry.user_profiles[name] = {
        "registered_on": datetime.now().strftime("%Y-%m-%d"),
        "notes": "Mobile Registration"
    }
    with open(USERS_FILE, "w") as f: json.dump(registry.user_profiles, f)
    registry.reload()
    return jsonify({"message": f"Successfully registered {name}!"})

@app.route('/detail/<name>')
def detail(name):
    lat, lon = request.args.get('lat'), request.args.get('lon')
    city = request.args.get('city', 'Ghaziabad')
    mask, glasses = request.args.get('mask'), request.args.get('glasses')
    
    weather = get_weather(f"{lat},{lon}" if lat and lat != "null" else city)
    recs = generate_recommendation(weather, mask == 'Mask', glasses == 'Glasses')
    profile = registry.user_profiles.get(name, {"notes": "Guest Profile", "registered_on": "N/A"})
    
    return render_template('detail.html', name=name, profile=profile, 
                           weather=weather, recs=recs, acc={"mask": mask, "glasses": glasses})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
