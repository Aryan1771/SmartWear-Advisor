from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
try:
    from tflite_runtime.interpreter import Interpreter as _TFLiteInterpreter
except Exception:
    try:
        from tensorflow.lite import Interpreter as _TFLiteInterpreter
    except Exception:
        _TFLiteInterpreter = None
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
        if _TFLiteInterpreter is None:
            print(f"[ERROR] tflite Interpreter not available for: {self.model_path.name}")
            return
        self.interpreter = _TFLiteInterpreter(model_path=str(self.model_path))
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        shape = self.input_details[0]["shape"]
        try:
            if len(shape) == 4 and int(shape[3]) in (1, 3):
                self.input_size = (int(shape[1]), int(shape[2]))
                self._input_channels = int(shape[3])
            elif len(shape) == 4 and int(shape[1]) in (1, 3):
                self.input_size = (int(shape[2]), int(shape[3]))
                self._input_channels = int(shape[1])
            elif len(shape) == 3:
                self.input_size = (int(shape[1]), int(shape[2]))
                self._input_channels = 1
            else:
                self.input_size = (128, 128)
                self._input_channels = 3
        except Exception:
            self.input_size = (128, 128)
            self._input_channels = 3
        print(f"[INFO] Loaded model: {self.model_path.name}")
    def predict(self, image):
        if self.interpreter is None:
            return None
        h, w = self.input_size
        if getattr(self, "_input_channels", 3) == 1:
            img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            img = cv2.resize(img, (w, h))
            img = img.astype("float32")
            img = np.expand_dims(img, axis=-1)
        else:
            img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (w, h))
            img = img.astype("float32")

        # scale according to input dtype
        in_dtype = self.input_details[0].get("dtype", np.float32)
        if in_dtype == np.uint8:
            img = (img * 255.0).astype(np.uint8)
        else:
            img = (img / 255.0).astype(np.float32)

        img = np.expand_dims(img, axis=0)
        try:
            self.interpreter.set_tensor(self.input_details[0]["index"], img)
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(self.output_details[0]["index"])
        except Exception:
            return None
        out = np.array(output)
        if out.ndim >= 2 and out.shape[-1] == 2:
            probs = out.reshape(-1, out.shape[-1])[0]
            idx = int(np.argmax(probs))
            conf = float(probs[idx])
            return BinaryPrediction(self.labels[idx], conf, self.model_path.name)
        else:
            value = float(np.reshape(out, -1)[0])
            if value >= 0.5:
                return BinaryPrediction(self.labels[1], value, self.model_path.name)
            else:
                return BinaryPrediction(self.labels[0], 1.0 - value, self.model_path.name)
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
        try:
            top, right, bottom, left = map(int, face_box)
        except Exception:
            return {
                "mask": "Unknown",
                "glasses": "Unknown",
                "confidence": "Low"
            }
        h, w = frame.shape[:2]
        top, bottom = max(0, top), min(h, bottom)
        left, right = max(0, left), min(w, right)
        # ensure proper ordering
        if left >= right or top >= bottom:
            return {
                "mask": "Unknown",
                "glasses": "Unknown",
                "confidence": "Low"
            }
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