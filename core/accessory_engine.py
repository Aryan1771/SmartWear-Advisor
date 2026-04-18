from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite


APP_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = APP_DIR / "model"


@dataclass
class BinaryPrediction:
    label: str
    confidence: float
    source: str


class BinaryImageClassifier:
    def __init__(self, model_name, labels):
        self.model_path = MODEL_DIR / model_name
        self.labels = labels
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.input_size = (128, 128)
        self.load()

    def load(self):
        if not self.model_path.exists():
            print(f"[ERROR] Model not found: {self.model_path}")
            return

        self.interpreter = tflite.Interpreter(model_path=str(self.model_path))
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        shape = self.input_details[0]["shape"]
        self.input_size = (shape[1], shape[2])

        print(f"[INFO] Loaded model: {self.model_path.name}")

    def predict(self, image):
        if self.interpreter is None:
            return None

        img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, self.input_size)
        img = img.astype("float32") / 255.0
        img = np.expand_dims(img, axis=0)

        self.interpreter.set_tensor(self.input_details[0]["index"], img)
        self.interpreter.invoke()

        output = self.interpreter.get_tensor(self.output_details[0]["index"])
        value = float(output[0][0])

        if value >= 0.5:
            return BinaryPrediction(self.labels[1], value, self.model_path.name)
        else:
            return BinaryPrediction(self.labels[0], 1 - value, self.model_path.name)


class AccessoryDetector:
    def __init__(self):
        self.mask_model = BinaryImageClassifier(
            "mask_model.tflite",
            ["without_mask", "with_mask"]
        )

        self.glasses_model = BinaryImageClassifier(
            "glasses_model.tflite",
            ["without_glasses", "with_glasses"]
        )

    def analyze(self, frame, face_box):
        top, right, bottom, left = face_box

        h, w = frame.shape[:2]
        top, bottom = max(0, top), min(h, bottom)
        left, right = max(0, left), min(w, right)

        face = frame[top:bottom, left:right]

        if face.size == 0:
            return {
                "mask": "Unknown",
                "glasses": "Unknown",
                "confidence": "Low"
            }

        mask_pred = self.mask_model.predict(face)
        glass_pred = self.glasses_model.predict(face)

        mask = "Mask Detected" if mask_pred and mask_pred.label == "with_mask" else "No Mask"
        glasses = "Glasses Detected" if glass_pred and glass_pred.label == "with_glasses" else "No Glasses"

        score = max(
            mask_pred.confidence if mask_pred else 0,
            glass_pred.confidence if glass_pred else 0,
        )

        confidence = "High" if score > 0.85 else "Medium" if score > 0.65 else "Low"

        return {
            "mask": mask,
            "glasses": glasses,
            "confidence": confidence
        }