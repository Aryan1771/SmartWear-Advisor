import sys
from pathlib import Path

# --- Fix imports ---
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import cv2
import numpy as np
import base64
import face_recognition

from backend.recommendation_engine import generate_recommendation
from backend.weather_api import get_weather
from core.accessory_engine import AccessoryDetector
from core.face_engine import recognize_face

# --- App init ---
app = FastAPI()

# ✅ CORS (VERY IMPORTANT FOR VERCEL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

detector = AccessoryDetector()

DATA_DIR = ROOT_DIR / "data"
ENCODINGS_DIR = DATA_DIR / "encodings"
ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Helpers ----------
def read_image(file):
    try:
        contents = file.file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame
    except:
        return None


# ---------- REST API ----------
@app.get("/")
def home():
    return {"message": "SmartWear API running 🚀"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), city: str = Form("Delhi")):
    frame = read_image(file)

    if frame is None:
        return {"status": "invalid_image"}

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    faces = face_recognition.face_locations(rgb)
    if not faces:
        return {"status": "no_face"}

    encodings = face_recognition.face_encodings(rgb, [faces[0]])
    if not encodings:
        return {"status": "no_encoding"}

    name = recognize_face(encodings[0])
    accessories = detector.analyze(frame, faces[0])

    # Weather fallback safety
    try:
        weather = get_weather(city)
    except:
        weather = {"temp": 25, "condition": "clear"}

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

    if frame is None:
        return {"status": "invalid_image"}

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb)

    if len(faces) != 1:
        return {"status": "error", "msg": "Only one face allowed"}

    encodings = face_recognition.face_encodings(rgb, [faces[0]])
    if not encodings:
        return {"status": "error", "msg": "Encoding failed"}

    np.save(ENCODINGS_DIR / f"{name}.npy", encodings[0])

    return {"status": "registered", "name": name}


# ---------- WebSocket ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()

            try:
                img_data = base64.b64decode(data.split(",")[1])
                np_arr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            except:
                await websocket.send_json({"status": "invalid_frame"})
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb)

            if not faces:
                await websocket.send_json({"status": "no_face"})
                continue

            top, right, bottom, left = faces[0]

            encodings = face_recognition.face_encodings(rgb, [faces[0]])
            if not encodings:
                await websocket.send_json({"status": "no_encoding"})
                continue

            name = recognize_face(encodings[0])
            accessories = detector.analyze(frame, faces[0])

            await websocket.send_json({
                "status": "success",
                "name": name,
                "mask": accessories["mask"],
                "glasses": accessories["glasses"],
                "confidence": accessories["confidence"],
                "box": {
                    "top": int(top),
                    "right": int(right),
                    "bottom": int(bottom),
                    "left": int(left)
                }
            })

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        print("WebSocket Error:", e)