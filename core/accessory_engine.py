import os
import cv2
import numpy as np
import tensorflow as tf
from pathlib import Path

class AccessoryDetector:
    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent
        # Switched to .keras files for higher accuracy using Colab's VRAM
        self.mask_path = self.root / "model" / "mask_detector.keras"
        self.glass_path = self.root / "model" / "glasses_detector.keras"

        # Load full Keras models instead of TFLite interpreters
        self.mask_model = self._load(self.mask_path)
        self.glass_model = self._load(self.glass_path)

    def _load(self, path):
        if not path.exists(): 
            print(f"Warning: Model not found at {path}")
            return None
        return tf.keras.models.load_model(str(path))

    def analyze(self, frame, face_box):
        y1, x2, y2, x1 = face_box
        
        # Add a 10% padding to the crop to ensure the edges of glasses/mask aren't cut off
        h_pad = int((y2 - y1) * 0.1)
        w_pad = int((x2 - x1) * 0.1)
        face_img = frame[max(0, y1-h_pad):y2+h_pad, max(0, x1-w_pad):x2+w_pad]
        
        if face_img.size == 0:
            return {"mask": "No Mask", "glasses": "No Glasses"}

        # --- MASK DETECTION ---
        mask_status = self._predict(self.mask_model, face_img)

        # --- GLASSES DETECTION (With Contrast Enhancement) ---
        # We apply CLAHE to make transparent frames stand out from the skin
        lab = cv2.cvtColor(face_img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        enhanced_face = cv2.merge((cl,a,b))
        enhanced_face = cv2.cvtColor(enhanced_face, cv2.COLOR_LAB2BGR)
        
        # Focus on the eye region (top 65% of the enhanced face)
        h, w = enhanced_face.shape[:2]
        eye_region = enhanced_face[0:int(h*0.65), :]
        
        glass_status = self._predict(self.glass_model, eye_region)

        return {
            "mask": "Mask" if mask_status else "No Mask",
            "glasses": "Glasses" if glass_status else "No Glasses"
        }

    def _predict(self, model, img):
        if not model: return False
        
        # Get the required input size from the model's first layer
        input_shape = model.layers[0].input_shape[0]
        size = (input_shape[1], input_shape[2]) # Usually (224, 224) or similar
        
        # Preprocessing: Resize and Normalize
        img_resized = cv2.resize(img, size).astype(np.float32) / 255.0
        img_input = np.expand_dims(img_resized, axis=0)

        # Full Keras Prediction
        preds = model.predict(img_input, verbose=0)[0]
        
        # Return True if the 'Positive' class (index 1 or high probability) is detected
        return preds[1] > 0.5 if len(preds) > 1 else preds[0] > 0.5
