# ai_model/detect_accessories.py
# ─────────────────────────────────────────────────────────────────
# DEV / TESTING UTILITY — NOT DEPLOYED
# ─────────────────────────────────────────────────────────────────
# Run locally to verify that your trained .tflite (or .keras) models
# work correctly before uploading them to the HuggingFace Space.
#
# Usage:
#   python ai_model/detect_accessories.py
#   python ai_model/detect_accessories.py --model keras
#   python ai_model/detect_accessories.py --camera 1
#
# What it does:
#   1. Loads mask_labels.txt / glasses_labels.txt for correct index mapping
#   2. Opens webcam, detects faces with Haar cascade
#   3. Runs mask + glasses inference using the same CLAHE+eye-region
#      pipeline as the production accessory_engine.py
#   4. Draws colour-coded bounding boxes and confidence scores

import argparse
import cv2
import numpy as np
from pathlib import Path

parser = argparse.ArgumentParser(description="SmartWear dev accessory tester")
parser.add_argument("--model",     default="tflite", choices=["tflite","keras"])
parser.add_argument("--camera",    default=0, type=int)
parser.add_argument("--threshold", default=0.4, type=float)
args = parser.parse_args()

ROOT      = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"

# ── Label loading ─────────────────────────────────────────────────
def load_labels(filename):
    path = MODEL_DIR / filename
    if not path.exists():
        print(f"[Labels] WARNING: {path} not found — using default mapping.")
        return {0: "negative", 1: "positive"}
    labels = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if ":" in line:
            idx, name = line.split(":", 1)
            labels[int(idx)] = name.strip()
    print(f"[Labels] {filename}: {labels}")
    return labels

mask_labels    = load_labels("mask_labels.txt")
glasses_labels = load_labels("glasses_labels.txt")

def positive_index(labels):
    for idx, name in labels.items():
        if name.lower().startswith("with_"):
            return idx
    return 1

# ── Model loading ─────────────────────────────────────────────────
def load_tflite(name):
    path = MODEL_DIR / f"{name}_model.tflite"
    if not path.exists():
        raise FileNotFoundError(f"TFLite model not found: {path}")
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow as tf
        tflite = tf.lite
    interp = tflite.Interpreter(model_path=str(path))
    interp.allocate_tensors()
    return interp

def load_keras(name):
    import tensorflow as tf
    path = MODEL_DIR / f"{name}_detector.keras"
    if not path.exists():
        raise FileNotFoundError(f"Keras model not found: {path}")
    return tf.keras.models.load_model(str(path))

def predict_tflite(interp, labels, img, threshold):
    inp  = interp.get_input_details()[0]
    out  = interp.get_output_details()[0]
    h, w = inp["shape"][1], inp["shape"][2]
    img_r = cv2.resize(img, (w, h)).astype(np.float32) / 255.0
    interp.set_tensor(inp["index"], np.expand_dims(img_r, 0))
    interp.invoke()
    preds = interp.get_tensor(out["index"])[0]
    if len(preds) > 1:
        pi    = min(positive_index(labels), len(preds)-1)
        score = float(preds[pi])
    else:
        score = float(preds[0])
    return score > threshold, score

def predict_keras(model, labels, img, threshold):
    shape = model.layers[0].input_shape[0]
    h, w  = shape[1], shape[2]
    img_r = cv2.resize(img, (w, h)).astype(np.float32) / 255.0
    preds = model.predict(np.expand_dims(img_r, 0), verbose=0)[0]
    if len(preds) > 1:
        pi    = min(positive_index(labels), len(preds)-1)
        score = float(preds[pi])
    else:
        score = float(preds[0])
    return score > threshold, score

# Load
try:
    if args.model == "tflite":
        mask_model    = load_tflite("mask")
        glasses_model = load_tflite("glasses")
        def run(model, labels, img):
            return predict_tflite(model, labels, img, args.threshold)
    else:
        mask_model    = load_keras("mask")
        glasses_model = load_keras("glasses")
        def run(model, labels, img):
            return predict_keras(model, labels, img, args.threshold)
except FileNotFoundError as e:
    print(f"[ERROR] {e}")
    print("Train models first:  python ai_model/train_model.py")
    raise SystemExit(1)

# Haar cascade
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

cap = cv2.VideoCapture(args.camera)
if not cap.isOpened():
    raise RuntimeError(f"Cannot open camera index {args.camera}")

print("\n[SmartWear Dev Tool] Press Q to quit.\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(60,60))
    for (x, y, w, h) in faces:
        face = frame[y:y+h, x:x+w]
        # CLAHE eye-region for glasses (same as production)
        lab   = cv2.cvtColor(face, cv2.COLOR_BGR2LAB)
        l,a,b = cv2.split(lab)
        cl    = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8)).apply(l)
        enh   = cv2.cvtColor(cv2.merge((cl,a,b)), cv2.COLOR_LAB2BGR)
        fh,fw = enh.shape[:2]
        eye   = enh[int(fh*0.20):int(fh*0.55), :]
        mhit, mscore = run(mask_model,    mask_labels,    face)
        ghit, gscore = run(glasses_model, glasses_labels, eye)
        ml  = f"Mask({mscore:.2f})"     if mhit else f"NoMask({mscore:.2f})"
        gl  = f"Glasses({gscore:.2f})"  if ghit else f"NoGlasses({gscore:.2f})"
        col = (0,200,80) if (mhit or ghit) else (60,60,220)
        cv2.rectangle(frame, (x,y), (x+w,y+h), col, 2)
        cv2.putText(frame, f"{ml} | {gl}",
                    (x, y-10 if y>20 else y+h+20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
        print(f"mask={mscore:.3f}  glasses={gscore:.3f}")
    cv2.imshow("SmartWear Dev — Q to quit", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
