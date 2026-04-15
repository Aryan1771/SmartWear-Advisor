from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

try:
    import tensorflow as tf
except ModuleNotFoundError:
    tf = None


APP_DIR = Path(__file__).resolve().parents[1]
MODEL_SEARCH_DIRS = [APP_DIR / "model", APP_DIR / "ai_model" / "model"]


def normalize_label(name: str) -> str:
    return "".join(char.lower() for char in name if char.isalnum() or char == "_")


@dataclass
class BinaryPrediction:
    label: str
    confidence: float
    source: str


class BinaryImageClassifier:
    def __init__(self, kind: str):
        self.kind = kind
        self.model_candidates = self.find_model_files()
        self.model_path = None
        self.labels = self.load_labels()
        self.backend = "missing"
        self.model = None
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.input_size = (128, 128)
        self.error = None
        self.load()

    # ✅ FIXED: Strict label order
    def default_labels(self):
        if self.kind == "mask":
            return ["without_mask", "with_mask"]
        return ["without_glasses", "with_glasses"]

    def find_model_files(self):
        patterns = [
            f"*{self.kind}*.tflite",
            f"*{self.kind}*.keras",
            f"*{self.kind}*.h5",
        ]
        candidates = []
        for model_dir in MODEL_SEARCH_DIRS:
            for pattern in patterns:
                candidates.extend(sorted(model_dir.glob(pattern)))
        return candidates

    def load_labels(self):
        candidates = []
        for model_dir in MODEL_SEARCH_DIRS:
            candidates.extend(sorted(model_dir.glob(f"*{self.kind}*labels*.txt")))
            candidates.extend(sorted(model_dir.glob(f"{self.kind}_labels.txt")))

        for path in candidates:
            labels = []
            try:
                with path.open("r", encoding="utf-8") as file:
                    for line in file:
                        raw = line.strip()
                        if not raw:
                            continue
                        if ":" in raw:
                            _, label = raw.split(":", 1)
                            labels.append(label.strip())
                        else:
                            labels.append(raw)
            except OSError:
                continue
            if labels:
                print(f"[INFO] Loaded labels for {self.kind}: {labels}")
                return labels

        return self.default_labels()

    def load(self):
        if not self.model_candidates:
            self.error = f"No {self.kind} model found"
            return

        if tf is None:
            self.error = "TensorFlow not installed"
            return

        for candidate in self.model_candidates:
            try:
                if candidate.suffix.lower() == ".tflite":
                    self.interpreter = tf.lite.Interpreter(model_path=str(candidate))
                    self.interpreter.allocate_tensors()
                    self.input_details = self.interpreter.get_input_details()
                    self.output_details = self.interpreter.get_output_details()
                    shape = self.input_details[0]["shape"]
                    self.input_size = (int(shape[1]), int(shape[2]))
                    self.backend = "tflite"

                else:
                    self.model = tf.keras.models.load_model(candidate, compile=False)
                    shape = self.model.input_shape
                    if isinstance(shape, list):
                        shape = shape[0]
                    self.input_size = (int(shape[1]), int(shape[2]))
                    self.backend = "keras"

                self.model_path = candidate
                print(f"[INFO] Loaded {self.kind} model: {candidate.name}")
                return

            except Exception as e:
                self.error = str(e)

    def is_available(self):
        return self.backend in {"keras", "tflite"}

    def status_text(self):
        if self.is_available():
            return f"Loaded {self.model_path.name}"
        return self.error or "Model unavailable"

    def preprocess(self, image):
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, self.input_size)
        img = resized.astype("float32") / 255.0
        return np.expand_dims(img, axis=0)

    # ✅ FIXED: Correct prediction mapping
    def predict(self, image):
        if not self.is_available():
            return None

        batch = self.preprocess(image)

        if self.backend == "keras":
            output = self.model.predict(batch, verbose=0)
        else:
            self.interpreter.set_tensor(self.input_details[0]["index"], batch.astype(np.float32))
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(self.output_details[0]["index"])

        value = float(np.ravel(output)[0])

        if value >= 0.5:
            label = self.labels[1]   # with
            confidence = value
        else:
            label = self.labels[0]   # without
            confidence = 1 - value

        return BinaryPrediction(label, confidence, self.model_path.name)


class AccessoryDetector:
    def __init__(self):
        self.mask_classifier = BinaryImageClassifier("mask")
        self.glasses_classifier = BinaryImageClassifier("glasses")

    def status_summary(self):
        return (
            f"Mask model: {self.mask_classifier.status_text()}\n"
            f"Glasses model: {self.glasses_classifier.status_text()}"
        )

    # ✅ FIXED: strict mapping
    def is_positive_label(self, kind: str, label: str):
        normalized = normalize_label(label)

        if kind == "mask":
            return normalized == "with_mask"
        return normalized == "with_glasses"

    def heuristic_fallback(self, frame, face_box):
        return {
            "mask": "Unknown",
            "glasses": "Unknown",
            "confidence": "Low",
            "accessories_clear": False,
            "source": "Fallback",
        }

    def analyze(self, frame, face_box):
        top, right, bottom, left = face_box
        face = frame[top:bottom, left:right]

        if face.size == 0:
            return self.heuristic_fallback(frame, face_box)

        mask_pred = self.mask_classifier.predict(face)
        glass_pred = self.glasses_classifier.predict(face)

        # DEBUG OUTPUT
        print("DEBUG:",
              "Mask:", mask_pred.label if mask_pred else None,
              "Glasses:", glass_pred.label if glass_pred else None)

        if mask_pred is None and glass_pred is None:
            return self.heuristic_fallback(frame, face_box)

        mask_text = (
            "Mask Detected" if mask_pred and self.is_positive_label("mask", mask_pred.label)
            else "No Mask"
        )

        glasses_text = (
            "Glasses Detected" if glass_pred and self.is_positive_label("glasses", glass_pred.label)
            else "No Glasses"
        )

        confidence = "Low"
        score = max(
            mask_pred.confidence if mask_pred else 0,
            glass_pred.confidence if glass_pred else 0,
        )

        if score > 0.85:
            confidence = "High"
        elif score > 0.65:
            confidence = "Medium"

        return {
            "mask": mask_text,
            "glasses": glasses_text,
            "confidence": confidence,
            "accessories_clear": mask_text == "No Mask" and glasses_text == "No Glasses",
            "source": f"{mask_pred.source if mask_pred else ''}, {glass_pred.source if glass_pred else ''}",
        }