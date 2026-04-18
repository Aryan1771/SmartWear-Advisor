import numpy as np
import face_recognition
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "encodings"

def load_encodings():
    encodings = []
    names = []

    for file in DATA_DIR.glob("*.npy"):
        try:
            encodings.append(np.load(file))
            names.append(file.stem)
        except:
            continue

    return encodings, names


def recognize_face(face_encoding):
    known_encodings, names = load_encodings()

    if not known_encodings:
        return "Unknown"

    matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.48)
    distances = face_recognition.face_distance(known_encodings, face_encoding)

    best = int(np.argmin(distances))
    return names[best] if matches[best] else "Unknown"