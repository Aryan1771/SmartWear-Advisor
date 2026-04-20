import os
import cv2
import numpy as np
import tensorflow as tf
from pathlib import Path

class AccessoryDetector:
    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent
        self.mask_path = self.root / "models" / "mask_detector.keras"
        self.glass_path = self.root / "models" / "glasses_detector.keras"

        self.mask_model = self._load(self.mask_path)
        self.glass_model = self._load(self.glass_path)

    def _load(self, path):
        if not path.exists(): 
            print(f"Critical Error: Model not found at {path}")
            return None
        return tf.keras.models.load_model(str(path))

    def analyze(self, frame, face_box):
        y1, x2, y2, x1 = face_box
        
        # Increase padding to 15% to capture the edges of glasses/mask better
        h_pad = int((y2 - y1) * 0.15)
        w_pad = int((x2 - x1) * 0.15)
        face_img = frame[max(0, y1-h_pad):y2+h_pad, max(0, x1-w_pad):x2+w_pad]
        
        if face_img.size == 0:
            return {"mask": "No Mask", "glasses": "No Glasses"}

        # --- MASK DETECTION ---
        # Lowering threshold to 0.4 for higher sensitivity
        mask_status = self._predict(self.mask_model, face_img, threshold=0.4)

        # --- GLASSES DETECTION (Enhanced Focus) ---
        # Convert to LAB for CLAHE (Contrast Improvement)
        lab = cv2.cvtColor(face_img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8)) # Increased clipLimit
        cl = clahe.apply(l)
        enhanced_face = cv2.merge((cl,a,b))
        enhanced_face = cv2.cvtColor(enhanced_face, cv2.COLOR_LAB2BGR)
        
        # Crop strictly to eye region (top 20% to 55% of the face) 
        # to prevent mouth/nose from confusing the glasses model
        h, w = enhanced_face.shape[:2]
        eye_region = enhanced_face[int(h*0.2):int(h*0.55), :]
        
        # Lowering threshold to 0.3 to catch transparent frames
        glass_status = self._predict(self.glass_model, eye_region, threshold=0.3)

        return {
            "mask": "Mask" if mask_status else "No Mask",
            "glasses": "Glasses" if glass_status else "No Glasses"
        }

    def _predict(self, model, img, threshold=0.5):
        if not model: return False
        
        # Resize and use ImageNet-style preprocessing
        input_shape = model.layers[0].input_shape[0]
        size = (input_shape[1], input_shape[2])
        
        img_resized = cv2.resize(img, size).astype(np.float32)
        # Standardize pixel values (some models prefer -1 to 1 or 0 to 1)
        img_resized /= 255.0 
        img_input = np.expand_dims(img_resized, axis=0)

        preds = model.predict(img_input, verbose=0)[0]
        
        # Check if model output is multi-class or single binary neuron
        if len(preds) > 1:
            # Assumes index 1 is "Positive" (Mask or Glasses)
            return preds[1] > threshold
        else:
            return preds[0] > threshold
