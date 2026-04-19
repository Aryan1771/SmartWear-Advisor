import json
import cv2
import numpy as np
import face_recognition
from flask import Flask, render_template, Response, request, jsonify
from pathlib import Path
from datetime import datetime

from core.accessory_engine import AccessoryDetector
from backend.weather_api import get_weather
from backend.recommendation_engine import generate_recommendation

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
ENCODINGS_DIR = DATA_DIR / "encodings"
USERS_FILE = DATA_DIR / "registered_users.json"

# Initialize detector and camera variable
detector = AccessoryDetector()
camera = None

def get_camera():
    global camera
    if camera is None or not camera.isOpened():
        camera = cv2.VideoCapture(0)
    return camera

def release_camera():
    global camera
    if camera is not None:
        camera.release()
        camera = None

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
            # Split to handle Aryan_123456.npy as 'Aryan'
            self.known_names.append(file.stem.split('_')[0])

    def recognize(self, encoding):
        if not self.known_encodings: return "Unknown", None
        
        # Tolerance check for accuracy
        matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.52)
        
        if True in matches:
            face_distances = face_recognition.face_distance(self.known_encodings, encoding)
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                name = self.known_names[best_match_index]
                return name, self.user_profiles.get(name)
        return "Unknown", None

registry = FaceRegistry()

def gen_frames():
    cap = get_camera()
    while True:
        success, frame = cap.read()
        if not success: break
        
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        encs = face_recognition.face_encodings(rgb, locs)

        for (top, right, bottom, left), enc in zip(locs, encs):
            name, _ = registry.recognize(enc)
            # Yellow for unknown, Green for known
            color = (0, 255, 255) if name == "Unknown" else (0, 255, 0)
            
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
            cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255,255,255), 1)

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    cap = get_camera()
    success, frame = cap.read()
    if success:
        rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        if locs:
            enc = face_recognition.face_encodings(rgb, [locs[0]])[0]
            # Save with timestamp to avoid collisions
            filename = f"{name}_{datetime.now().strftime('%H%M%S')}.npy"
            np.save(ENCODINGS_DIR / filename, enc)
            
            registry.user_profiles[name] = {
                "registered_on": str(datetime.now().date()), 
                "notes": "Registered via Web"
            }
            with open(USERS_FILE, "w") as f: 
                json.dump(registry.user_profiles, f)
            
            registry.reload()
            return jsonify({"message": f"Successfully registered {name}"})
    return jsonify({"message": "Capture failed"}), 400

@app.route('/stop_camera', methods=['POST'])
def stop_cam():
    release_camera()
    return jsonify({"status": "off"})

@app.route('/get_status')
def get_status():
    global camera
    if camera is None or not camera.isOpened(): return jsonify({"name": "None"})
    
    success, frame = camera.read()
    if not success: return jsonify({"name": "None"})
    
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb)
    
    if locs:
        enc = face_recognition.face_encodings(rgb, [locs[0]])[0]
        name, _ = registry.recognize(enc)
        acc = detector.analyze(frame, locs[0])
        return jsonify({
            "name": name, 
            "mask": acc.get('mask', 'No Mask'), 
            "glasses": acc.get('glasses', 'No Glasses')
        })
    return jsonify({"name": "Unknown"})

@app.route('/detail/<name>')
def detail(name):
    # GPS and Location handling
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    city = request.args.get('city', 'Delhi')
    
    loc_query = f"{lat},{lon}" if lat and lat != "null" else city
    weather = get_weather(loc_query)
    
    # Identify user profile
    profile = registry.user_profiles.get(name, {"notes": "Guest"})
    
    # Final check for accessories before closing camera
    cap = get_camera()
    success, frame = cap.read()
    acc = {"mask": "No Mask", "glasses": "No Glasses"}
    
    if success:
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        if locs: 
            acc = detector.analyze(frame, locs[0])
    
    # CRITICAL: Stop camera hardware when moving to details view
    release_camera()
    
    recs = generate_recommendation(
        weather, 
        acc.get('mask') == 'Mask', 
        acc.get('glasses') == 'Glasses'
    )
    
    # PASSING 'acc' FIXES THE JINJA2 ERROR
    return render_template(
        'detail.html', 
        name=name, 
        profile=profile, 
        weather=weather, 
        recs=recs, 
        acc=acc
    )

if __name__ == '__main__':
    app.run(debug=True, threaded=True)