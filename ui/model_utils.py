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
                return labels
        return self.default_labels()

    def load(self):
        if not self.model_candidates:
            self.error = f"No {self.kind} model found in model/ or ai_model/model/"
            return

        if tf is None:
            self.error = "TensorFlow is not installed."
            return

        last_error = None
        for candidate in self.model_candidates:
            try:
                if candidate.suffix.lower() == ".tflite":
                    self.interpreter = tf.lite.Interpreter(model_path=str(candidate))
                    self.interpreter.allocate_tensors()
                    self.input_details = self.interpreter.get_input_details()
                    self.output_details = self.interpreter.get_output_details()
                    input_shape = self.input_details[0]["shape"]
                    self.input_size = (int(input_shape[1]), int(input_shape[2]))
                    self.backend = "tflite"
                else:
                    self.model = tf.keras.models.load_model(candidate, compile=False)
                    input_shape = self.model.input_shape
                    if isinstance(input_shape, list):
                        input_shape = input_shape[0]
                    self.input_size = (int(input_shape[1]), int(input_shape[2]))
                    self.backend = "keras"

                self.model_path = candidate
                self.error = None
                return
            except Exception as error:
                last_error = error

        self.error = str(last_error) if last_error else "Model unavailable"

    def is_available(self):
        return self.backend in {"keras", "tflite"}

    def status_text(self):
        if self.is_available():
            return f"Loaded {self.model_path.name} ({self.backend})"
        return self.error or "Model unavailable"

    def preprocess(self, image):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb_image, self.input_size, interpolation=cv2.INTER_AREA)
        array = resized.astype("float32") / 255.0
        return np.expand_dims(array, axis=0)

    def predict(self, image):
        if not self.is_available():
            return None

        batch = self.preprocess(image)
        if self.backend == "keras":
            raw_output = np.asarray(self.model.predict(batch, verbose=0))
        else:
            input_index = self.input_details[0]["index"]
            output_index = self.output_details[0]["index"]
            self.interpreter.set_tensor(input_index, batch.astype(np.float32))
            self.interpreter.invoke()
            raw_output = np.asarray(self.interpreter.get_tensor(output_index))

        flat_output = np.ravel(raw_output)
        if flat_output.size == 1:
            positive_score = float(flat_output[0])
            label_index = 1 if positive_score >= 0.5 else 0
            confidence = positive_score if label_index == 1 else 1.0 - positive_score
        else:
            label_index = int(np.argmax(flat_output))
            confidence = float(flat_output[label_index])

        labels = self.labels if len(self.labels) > label_index else self.default_labels()
        label = labels[label_index] if len(labels) > label_index else self.default_labels()[label_index]
        return BinaryPrediction(label=label, confidence=confidence, source=self.model_path.name)


class AccessoryDetector:
    def __init__(self):
        self.mask_classifier = BinaryImageClassifier("mask")
        self.glasses_classifier = BinaryImageClassifier("glasses")

    def status_summary(self):
        return (
            f"Mask model: {self.mask_classifier.status_text()}\n"
            f"Glasses model: {self.glasses_classifier.status_text()}"
        )

    def is_positive_label(self, kind: str, label: str):
        normalized = normalize_label(label)
        if kind == "mask":
            return "withmask" in normalized or normalized == "mask"
        return normalized in {"withglasses", "glasses", "eyeglasses", "spectacles"}

    def heuristic_fallback(self, frame, face_box):
        top, right, bottom, left = face_box
        face_region = frame[max(0, top):bottom, max(0, left):right]
        if face_region.size == 0:
            return {
                "mask": "Unknown",
                "glasses": "Unknown",
                "confidence": "Low",
                "accessories_clear": False,
                "source": "No face crop",
            }

        height = face_region.shape[0]
        gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        upper_region = gray[: max(1, height // 2), :]
        lower_region = gray[height // 2 :, :]

        upper_density = float(np.count_nonzero(cv2.Canny(upper_region, 60, 140))) / max(1, upper_region.size)
        lower_density = float(np.count_nonzero(cv2.Canny(lower_region, 60, 140))) / max(1, lower_region.size)

        glasses_present = upper_density > 0.12
        mask_present = lower_density < 0.055

        return {
            "mask": "Mask Detected" if mask_present else "No Mask",
            "glasses": "Glasses Detected" if glasses_present else "No Glasses",
            "confidence": "Low",
            "accessories_clear": not mask_present and not glasses_present,
            "source": "Heuristic fallback",
        }

    def analyze(self, frame, face_box):
        top, right, bottom, left = face_box
        face_region = frame[max(0, top):bottom, max(0, left):right]
        if face_region.size == 0:
            return self.heuristic_fallback(frame, face_box)

        mask_prediction = self.mask_classifier.predict(face_region)
        glasses_prediction = self.glasses_classifier.predict(face_region)
        heuristic = self.heuristic_fallback(frame, face_box)
        if mask_prediction is None and glasses_prediction is None:
            return heuristic

        if mask_prediction is None:
            mask_text = heuristic["mask"]
            mask_score = 0.0
        else:
            mask_text = "Mask Detected" if self.is_positive_label("mask", mask_prediction.label) else "No Mask"
            mask_score = mask_prediction.confidence

        if glasses_prediction is None:
            glasses_text = heuristic["glasses"]
            glasses_score = 0.0
        else:
            glasses_text = (
                "Glasses Detected" if self.is_positive_label("glasses", glasses_prediction.label) else "No Glasses"
            )
            glasses_score = glasses_prediction.confidence

        combined_score = max(mask_score, glasses_score)
        confidence = "Low"
        if combined_score >= 0.85:
            confidence = "High"
        elif combined_score >= 0.65:
            confidence = "Medium"

        available_sources = [
            prediction.source
            for prediction in [mask_prediction, glasses_prediction]
            if prediction is not None
        ]
        return {
            "mask": mask_text,
            "glasses": glasses_text,
            "confidence": confidence,
            "accessories_clear": mask_text == "No Mask" and glasses_text == "No Glasses",
            "source": ", ".join(available_sources) if available_sources else "Heuristic fallback",
        }
