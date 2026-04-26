# hf_space/app.py
# FastAPI inference server — deployed on HuggingFace Space (Docker SDK).
# Handles: face detection, recognition, accessory detection, and registration.
# Flask app on Render proxies to this server for all ML work.

import base64
import cv2
import numpy as np
import face_recognition
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.accessory_engine import AccessoryDetector
from core.face_engine import FaceEngine

# ── App setup ──────────────────────────────────────────────────────
app = FastAPI(title="SmartWear ML Server", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)

# ── Load models on startup (once) ─────────────────────────────────
print("[Startup] Loading models...")
detector = AccessoryDetector()
engine   = FaceEngine()
print("[Startup] Models ready.")


# ── Request schemas ────────────────────────────────────────────────
class FrameRequest(BaseModel):
    image: str          # base64 data-URI or raw base64
    name:  str = ""     # only for /register


# ── Helpers ───────────────────────────────────────────────────────
def _decode(b64_str: str):
    """Decode base64 data-URI or raw base64 → OpenCV BGR image."""
    try:
        raw  = b64_str.split(",")[1] if "," in b64_str else b64_str
        buf  = np.frombuffer(base64.b64decode(raw), np.uint8)
        img  = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"[Decode] Error: {e}")
        return None


# ── Routes ────────────────────────────────────────────────────────

@app.get("/ping")
def ping():
    """Keepalive endpoint — Render pings this every 20 min to prevent HF sleep."""
    return {"status": "alive", "users": len(engine.get_all_names())}


@app.post("/detect")
def detect(req: FrameRequest):
    """
    Detect face, run recognition, and analyse accessories.
    Returns accessory labels plus confidence/debug signals.
    """
    frame = _decode(req.image)
    if frame is None:
        return {
            "name": "Unknown",
            "box": None,
            "mask": "No Mask",
            "glasses": "No Glasses",
            "mask_confidence": 0.0,
            "glasses_confidence": 0.0,
        }

    rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    # HOG model is faster and uses less RAM than CNN on CPU
    locs = face_recognition.face_locations(rgb, model="hog")

    if not locs:
        return {
            "name": "Unknown",
            "box": None,
            "mask": "No Mask",
            "glasses": "No Glasses",
            "mask_confidence": 0.0,
            "glasses_confidence": 0.0,
        }

    # Process only the largest face (closest to camera)
    largest = max(locs, key=lambda b: (b[2] - b[0]) * (b[1] - b[3]))

    encs = face_recognition.face_encodings(rgb, [largest])
    if not encs:
        return {
            "name": "Unknown",
            "box": list(largest),
            "mask": "No Mask",
            "glasses": "No Glasses",
            "mask_confidence": 0.0,
            "glasses_confidence": 0.0,
        }

    name = engine.recognize(encs[0])
    acc  = detector.analyze(frame, largest)

    return {
        "name":    name,
        "box":     list(largest),   # [top, right, bottom, left]
        "mask":    acc.get("mask",    "No Mask"),
        "glasses": acc.get("glasses", "No Glasses"),
        "mask_confidence": acc.get("mask_confidence", 0.0),
        "glasses_confidence": acc.get("glasses_confidence", 0.0),
        "mask_debug": acc.get("mask_debug", {}),
        "glasses_debug": acc.get("glasses_debug", {}),
    }


@app.post("/register")
def register(req: FrameRequest):
    """
    Register a new face from a captured frame.
    Requires a blink-confirmed frame (liveness handled client-side).
    """
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")

    frame = _decode(req.image)
    if frame is None:
        return {"success": False, "message": "Invalid or empty image."}

    rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb, model="hog")

    if not locs:
        return {
            "success": False,
            "message": "No face detected in the image. Please try again.",
        }

    largest = max(locs, key=lambda b: (b[2] - b[0]) * (b[1] - b[3]))
    encs = face_recognition.face_encodings(rgb, [largest])
    if not encs:
        return {
            "success": False,
            "message": "Could not extract face features. Ensure good lighting and try again.",
        }

    ok, message = engine.register(req.name.strip(), encs[0])
    return {"success": ok, "message": message}


@app.get("/registered")
def registered():
    """Return list of all registered user names."""
    return {"users": engine.get_all_names()}


@app.delete("/user/{name}")
def delete_user(name: str):
    """Delete a registered user's face encoding."""
    ok = engine.delete(name)
    return {"success": ok, "name": name}
