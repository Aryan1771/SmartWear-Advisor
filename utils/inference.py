# ===================== inference.py =====================

import base64
import numpy as np
import cv2

def decode_image(image_b64):
    img_data = base64.b64decode(image_b64.split(",")[1])
    np_arr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


def run_inference(image_b64):
    img = decode_image(image_b64)

    # ===== MOCK FACE DETECTION =====
    h, w, _ = img.shape
    box = [50, w-50, h-50, 50]

    # ===== MOCK FACE RECOGNITION =====
    name = "User" if np.random.rand() > 0.5 else "Unknown"

    # ===== MASK / GLASSES FIX =====
    # simulate model outputs
    mask_output = np.random.rand(2)
    glasses_output = np.random.rand(2)

    mask = "Mask" if mask_output[1] > mask_output[0] else "No Mask"
    glasses = "Glasses" if glasses_output[1] > glasses_output[0] else "No Glasses"

    return {
        "name": name,
        "box": box,
        "mask": mask,
        "glasses": glasses
    }
