import sys
from pathlib import Path

# --- Fix imports ---
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from fastapi import FastAPI, UploadFile, File, Form, WebSocket
import cv2
import numpy as np
import base64
import face_recognition

from backend.recommendation_engine import generate_recommendation
from backend.weather_api import get_weather
from ui.model_utils import AccessoryDetector

# --- App init ---
app = FastAPI()

detector = AccessoryDetector()

DATA_DIR = ROOT_DIR / "data"
ENCODINGS_DIR = DATA_DIR / "encodings"


# ---------- Helpers ----------
def load_encodings():
    encodings = []
    names = []

    for file in ENCODINGS_DIR.glob("*.npy"):
        encodings.append(np.load(file))
        names.append(file.stem)

    return encodings, names


def recognize_face(face_encoding):
    known_encodings, names = load_encodings()

    if not known_encodings:
        return "Unknown"

    matches = face_recognition.compare_faces(
        known_encodings, face_encoding, tolerance=0.48
    )
    distances = face_recognition.face_distance(
        known_encodings, face_encoding
    )

    best = int(np.argmin(distances))
    return names[best] if matches[best] else "Unknown"


def read_image(file):
    contents = file.file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


# ---------- REST API ----------
@app.get("/")
def home():
    return {"message": "SmartWear API running 🚀"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), city: str = Form("Delhi")):
    frame = read_image(file)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    faces = face_recognition.face_locations(rgb)
    if not faces:
        return {"status": "no_face"}

    face_box = faces[0]
    encoding = face_recognition.face_encodings(rgb, [face_box])[0]

    name = recognize_face(encoding)
    accessories = detector.analyze(frame, face_box)
    weather = get_weather(city)

    recommendations = generate_recommendation(
        weather=weather,
        is_mask=accessories["mask"] == "Mask Detected",
        is_glasses=accessories["glasses"] == "Glasses Detected",
    )

    return {
        "status": "success",
        "name": name,
        "accessories": accessories,
        "weather": weather,
        "recommendations": recommendations,
    }


@app.post("/register")
async def register(name: str = Form(...), file: UploadFile = File(...)):
    frame = read_image(file)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    faces = face_recognition.face_locations(rgb)

    if len(faces) != 1:
        return {"status": "error", "msg": "Only one face allowed"}

    encoding = face_recognition.face_encodings(rgb, [faces[0]])[0]
    np.save(ENCODINGS_DIR / f"{name}.npy", encoding)

    return {"status": "registered", "name": name}


# ---------- WebSocket (LIVE DETECTION) ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    while True:
        try:
            data = await websocket.receive_text()

            img_data = base64.b64decode(data.split(",")[1])
            np_arr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb)

            if not faces:
                await websocket.send_json({"status": "no_face"})
                continue

            face_box = faces[0]
            encoding = face_recognition.face_encodings(rgb, [face_box])[0]

            name = recognize_face(encoding)
            accessories = detector.analyze(frame, face_box)

            await websocket.send_json({
                "status": "success",
                "name": name,
                "mask": accessories["mask"],
                "glasses": accessories["glasses"],
                "confidence": accessories["confidence"]
            })

        except Exception as e:
            await websocket.send_json({
                "status": "error",
                "msg": str(e)
            })