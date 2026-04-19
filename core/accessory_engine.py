import os
import cv2
import numpy as np
import tensorflow as tf
from pathlib import Path

class AccessoryDetector:
    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent
        self.mask_path = self.root / "model" / "mask_model.tflite"
        self.glass_path = self.root / "model" / "glasses_model.tflite"

        self.mask_interpreter = self._load(self.mask_path)
        self.glass_interpreter = self._load(self.glass_path)

    def _load(self, path):
        if not path.exists(): return None
        interpreter = tf.lite.Interpreter(model_path=str(path))
        interpreter.allocate_tensors()
        return interpreter

    def analyze(self, frame, face_box):
        y1, x2, y2, x1 = face_box
        face_img = frame[y1:y2, x1:x2]
        
        if face_img.size == 0:
            return {"mask": "No Mask", "glasses": "No Glasses"}

        # Mask logic (standard 0.5 threshold)
        mask_status = self._predict(self.mask_interpreter, face_img, 0.5)

        # Glasses logic: Focus on the upper half of the face to avoid nose/mouth shadows
        h, w = face_img.shape[:2]
        eye_region = face_img[0:int(h*0.6), :] # Crop to top 60% of face
        
        # Increased threshold to 0.55 to stop false positives
        glass_status = self._predict(self.glass_interpreter, eye_region, 0.55)

        return {
            "mask": "Mask" if mask_status else "No Mask",
            "glasses": "Glasses" if glass_status else "No Glasses"
        }

    def _predict(self, interpreter, img, threshold):
        if not interpreter: return False
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        size = input_details[0]['shape'][1:3]
        img_resized = cv2.resize(img, size).astype(np.float32) / 255.0
        img_input = np.expand_dims(img_resized, axis=0)

        interpreter.set_tensor(input_details[0]['index'], img_input)
        interpreter.invoke()
        
        preds = interpreter.get_tensor(output_details[0]['index'])[0]
        # Use the highest probability class
        return preds[1] > threshold if len(preds) > 1 else preds[0] > threshold