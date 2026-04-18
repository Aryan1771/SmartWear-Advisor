import numpy as np
import face_recognition
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
ENCODINGS_DIR = ROOT_DIR / "data" / "encodings"
KNOWN_ENCODINGS = []
KNOWN_NAMES = []
def load_encodings():
    global KNOWN_ENCODINGS, KNOWN_NAMES
    KNOWN_ENCODINGS = []
    KNOWN_NAMES = []
    for file in ENCODINGS_DIR.glob("*.npy"):
        try:
            KNOWN_ENCODINGS.append(np.load(file))
            KNOWN_NAMES.append(file.stem)
        except:
            continue
load_encodings()
def recognize_face(face_encoding):
    if not KNOWN_ENCODINGS:
        return "Unknown"
    matches = face_recognition.compare_faces(
        KNOWN_ENCODINGS, face_encoding, tolerance=0.48
    )
    distances = face_recognition.face_distance(
        KNOWN_ENCODINGS, face_encoding
    )
    best = int(np.argmin(distances))
    return KNOWN_NAMES[best] if matches[best] else "Unknown"