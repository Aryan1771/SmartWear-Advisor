import cv2
import numpy as np
from pathlib import Path
from typing import Optional

try:
    import tflite_runtime.interpreter as tflite

    _RUNTIME = "tflite_runtime"
except ImportError:
    import tensorflow as tf

    tflite = tf.lite
    _RUNTIME = "tensorflow"

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"

MASK_THRESHOLD = 0.82
MASK_MARGIN = 0.18
GLASSES_THRESHOLD = 0.52
GLASSES_MARGIN = 0.05


class AccessoryDetector:
    def __init__(self):
        self.mask_labels = self._load_labels("mask_labels.txt")
        self.glasses_labels = self._load_labels("glasses_labels.txt")
        self.mask_interp = self._load_tflite("mask_model.tflite")
        self.glasses_interp = self._load_tflite("glasses_model.tflite")

        print(f"[Accessory] Runtime: {_RUNTIME}")
        print(f"[Accessory] Mask labels: {self.mask_labels}")
        print(f"[Accessory] Glasses labels: {self.glasses_labels}")

    def _load_labels(self, filename: str) -> dict:
        path = MODELS_DIR / filename
        labels = {}
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if ":" in line:
                    idx, name = line.split(":", 1)
                    labels[int(idx)] = name.strip()
        return labels

    def _load_tflite(self, filename: str):
        path = MODELS_DIR / filename
        if not path.exists():
            print(f"[Accessory] Model NOT found: {path}")
            return None
        try:
            interp = tflite.Interpreter(model_path=str(path))
            interp.allocate_tensors()
            return interp
        except Exception as exc:
            print(f"[Accessory] Failed to load {filename}: {exc}")
            return None

    @staticmethod
    def _positive_index(labels: dict) -> int:
        for idx, name in labels.items():
            if name.lower().startswith("with_"):
                return idx
        return 1

    @staticmethod
    def _negative_index(labels: dict, positive_index: int) -> int:
        for idx, name in labels.items():
            if name.lower().startswith("without_"):
                return idx
        return 0 if positive_index != 0 else 1

    @staticmethod
    def _normalize_scores(preds: np.ndarray) -> np.ndarray:
        preds = np.asarray(preds, dtype=np.float32).reshape(-1)
        if preds.size == 0:
            return preds

        if preds.size == 1:
            value = float(preds[0])
            if value < 0.0 or value > 1.0:
                value = 1.0 / (1.0 + np.exp(-value))
            return np.array([np.clip(value, 0.0, 1.0)], dtype=np.float32)

        if np.all(preds >= 0.0) and np.all(preds <= 1.0):
            total = float(preds.sum())
            if 0.98 <= total <= 1.02:
                return preds

        shifted = preds - np.max(preds)
        exp_scores = np.exp(shifted)
        return exp_scores / np.sum(exp_scores)

    def _predict_details(self, interp, labels: dict, img: np.ndarray) -> dict:
        if interp is None or img is None or img.size == 0:
            return {
                "detected": False,
                "positive_confidence": 0.0,
                "negative_confidence": 1.0,
                "predicted_label": "unavailable",
            }

        input_details = interp.get_input_details()[0]
        output_details = interp.get_output_details()[0]

        height, width = input_details["shape"][1], input_details["shape"][2]
        resized = cv2.resize(img, (width, height)).astype(np.float32) / 255.0
        interp.set_tensor(input_details["index"], np.expand_dims(resized, 0))
        interp.invoke()
        raw_preds = interp.get_tensor(output_details["index"])[0]
        probs = self._normalize_scores(raw_preds)

        positive_index = self._positive_index(labels)
        negative_index = self._negative_index(labels, positive_index)

        if probs.size == 1:
            positive_conf = float(probs[0])
            negative_conf = 1.0 - positive_conf
            predicted_positive = positive_conf >= negative_conf
            predicted_label = labels.get(positive_index if predicted_positive else negative_index, "unknown")
        else:
            positive_index = min(positive_index, probs.size - 1)
            negative_index = min(negative_index, probs.size - 1)
            positive_conf = float(probs[positive_index])
            negative_conf = float(probs[negative_index])
            predicted_label = labels.get(int(np.argmax(probs)), "unknown")

        return {
            "detected": False,
            "positive_confidence": round(positive_conf, 4),
            "negative_confidence": round(negative_conf, 4),
            "predicted_label": predicted_label,
        }

    @staticmethod
    def _crop_face(frame: np.ndarray, face_box: tuple) -> Optional[np.ndarray]:
        top, right, bottom, left = face_box
        height = max(1, bottom - top)
        width = max(1, right - left)

        h_pad = int(height * 0.18)
        w_pad = int(width * 0.18)
        face = frame[
            max(0, top - h_pad) : bottom + h_pad,
            max(0, left - w_pad) : right + w_pad,
        ]
        return face if face is not None and face.size else None

    @staticmethod
    def _crop_mask_region(face: np.ndarray) -> Optional[np.ndarray]:
        if face is None or face.size == 0:
            return None
        face_height = face.shape[0]
        start = int(face_height * 0.42)
        region = face[start:, :]
        return region if region is not None and region.size else None

    @staticmethod
    def _crop_glasses_region(face: np.ndarray) -> Optional[np.ndarray]:
        if face is None or face.size == 0:
            return None

        lab = cv2.cvtColor(face, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = cv2.cvtColor(
            cv2.merge((clahe.apply(l_channel), a_channel, b_channel)),
            cv2.COLOR_LAB2BGR,
        )

        height = enhanced.shape[0]
        region = enhanced[int(height * 0.18) : int(height * 0.52), :]
        return region if region is not None and region.size else None

    def analyze(self, frame: np.ndarray, face_box: tuple) -> dict:
        face = self._crop_face(frame, face_box)
        if face is None:
            return {
                "mask": "No Mask",
                "glasses": "No Glasses",
                "mask_confidence": 0.0,
                "glasses_confidence": 0.0,
            }

        mask_region = self._crop_mask_region(face)
        glasses_region = self._crop_glasses_region(face)

        mask_result = self._predict_details(self.mask_interp, self.mask_labels, mask_region)
        glasses_result = self._predict_details(self.glasses_interp, self.glasses_labels, glasses_region)

        mask_detected = (
            mask_result["positive_confidence"] >= MASK_THRESHOLD
            and (mask_result["positive_confidence"] - mask_result["negative_confidence"]) >= MASK_MARGIN
        )
        glasses_detected = (
            glasses_result["positive_confidence"] >= GLASSES_THRESHOLD
            and (glasses_result["positive_confidence"] - glasses_result["negative_confidence"]) >= GLASSES_MARGIN
        )

        mask_result["detected"] = mask_detected
        glasses_result["detected"] = glasses_detected

        return {
            "mask": "Mask" if mask_detected else "No Mask",
            "glasses": "Glasses" if glasses_detected else "No Glasses",
            "mask_confidence": mask_result["positive_confidence"],
            "glasses_confidence": glasses_result["positive_confidence"],
            "mask_debug": {
                "positive_confidence": mask_result["positive_confidence"],
                "negative_confidence": mask_result["negative_confidence"],
                "predicted_label": mask_result["predicted_label"],
                "threshold": MASK_THRESHOLD,
                "margin": MASK_MARGIN,
                "region": "lower_face",
            },
            "glasses_debug": {
                "positive_confidence": glasses_result["positive_confidence"],
                "negative_confidence": glasses_result["negative_confidence"],
                "predicted_label": glasses_result["predicted_label"],
                "threshold": GLASSES_THRESHOLD,
                "margin": GLASSES_MARGIN,
                "region": "eye_region",
            },
        }
