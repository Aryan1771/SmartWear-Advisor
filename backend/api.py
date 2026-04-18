import sys
from pathlib import Path
import time
import logging
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
from core.face_engine import recognize_face, load_encodings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartwear")
app = FastAPI(title="SmartWear API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
detector = AccessoryDetector()
DATA_DIR = ROOT_DIR / "data"
ENCODINGS_DIR = DATA_DIR / "encodings"
ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)
load_encodings()
def decode_frame(data):
    try:
        img_data = base64.b64decode(data.split(",")[1])
        np_arr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame
    except:
        return None
@app.get("/health")
def health():
    return {"status": "ok"}
@app.post("/analyze")
async def analyze(file: UploadFile = File(...), city: str = Form("Delhi")):
    try:
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"status": "invalid_image"}
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = face_recognition.face_locations(rgb, model="hog")
        if not faces:
            return {"status": "no_face"}
        enc = face_recognition.face_encodings(rgb, [faces[0]])
        if not enc:
            return {"status": "no_encoding"}
        name = recognize_face(enc[0])
        accessories = detector.analyze(frame, faces[0])
        try:
            weather = get_weather(city)
        except Exception as e:
            logger.warning(f"Weather API failed: {e}")
            weather = {"temp": 25, "condition": "clear"}
        return {
            "status": "success",
            "name": name,
            "accessories": accessories,
            "weather": weather,
            "recommendations": generate_recommendation(
                weather,
                accessories["mask"] == "Mask Detected",
                accessories["glasses"] == "Glasses Detected",
            ),
        }
    except Exception as e:
        logger.error(f"/analyze error: {e}")
        return {"status": "error"}
@app.post("/register")
async def register(name: str = Form(...), file: UploadFile = File(...)):
    try:
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
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
        load_encodings()
        return {"status": "registered", "name": name}
    except Exception as e:
        logger.error(f"/register error: {e}")
        return {"status": "error", "msg": "Registration failed"}
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_process_time = 0
    try:
        while True:
            data = await websocket.receive_text()
            if time.time() - last_process_time < 0.15:
                continue
            last_process_time = time.time()
            frame = decode_frame(data)
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb, model="hog")
            if not faces:
                await websocket.send_json({"status": "no_face"})
                continue
            top, right, bottom, left = faces[0]
            enc = face_recognition.face_encodings(rgb, [faces[0]])
            if not enc:
                continue
            name = recognize_face(enc[0])
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
                    "left": int(left),
                },
            })
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")