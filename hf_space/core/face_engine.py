# hf_space/core/face_engine.py
# Handles face encoding storage, recognition, and deletion.
# Fixes the original registration bug:
#   - Encodings saved as sanitized {name}.npy (no timestamp suffix that broke name loading)
#   - reload() correctly loads name from full stem

import re
import numpy as np
import face_recognition
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
ENCODINGS_DIR = ROOT / "data" / "encodings"
ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)

TOLERANCE = 0.50   # lower = stricter matching


def _safe(name: str) -> str:
    """Convert any name to a safe filename (keeps letters, digits, underscore, hyphen)."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())


class FaceEngine:
    def __init__(self):
        self.known_encodings: list = []
        self.known_names:     list = []
        self.reload()

    def reload(self):
        """Re-scan encodings directory and rebuild in-memory index."""
        self.known_encodings = []
        self.known_names     = []
        for f in sorted(ENCODINGS_DIR.glob("*.npy")):
            try:
                enc = np.load(str(f), allow_pickle=False)
                # Name is the entire stem — no splitting on '_'
                self.known_names.append(f.stem)
                self.known_encodings.append(enc)
            except Exception as e:
                print(f"[FaceEngine] Skipping {f.name}: {e}")

        print(f"[FaceEngine] Loaded {len(self.known_names)} encodings: {self.known_names}")

    # ── Recognition ───────────────────────────────────────────────
    def recognize(self, encoding: np.ndarray) -> str:
        if not self.known_encodings:
            return "Unknown"

        matches   = face_recognition.compare_faces(
            self.known_encodings, encoding, tolerance=TOLERANCE
        )
        distances = face_recognition.face_distance(self.known_encodings, encoding)
        best      = int(np.argmin(distances))

        if matches[best]:
            return self.known_names[best]
        return "Unknown"

    # ── Registration ──────────────────────────────────────────────
    def register(self, display_name: str, encoding: np.ndarray) -> tuple[bool, str]:
        """
        Saves encoding as data/encodings/{safe_name}.npy.
        Returns (success: bool, message: str).
        """
        safe = _safe(display_name)
        if not safe:
            return False, "Invalid name."

        path = ENCODINGS_DIR / f"{safe}.npy"
        try:
            np.save(str(path), encoding)
            self.reload()
            return True, f"Successfully registered {display_name}!"
        except Exception as e:
            print(f"[FaceEngine] Register error: {e}")
            return False, "Failed to save encoding. Try again."

    # ── Deletion ──────────────────────────────────────────────────
    def delete(self, display_name: str) -> bool:
        safe = _safe(display_name)
        path = ENCODINGS_DIR / f"{safe}.npy"
        if path.exists():
            path.unlink()
            self.reload()
            return True
        return False

    # ── List ──────────────────────────────────────────────────────
    def get_all_names(self) -> list[str]:
        return list(self.known_names)
