import cv2
import numpy as np
from tensorflow.keras.models import load_model
glasses_model = load_model("model/glasses_detector.keras")
mask_model = load_model("model/mask_detector.keras")
IMG_SIZE = 128
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
def preprocess(face):
    face = cv2.resize(face, (IMG_SIZE, IMG_SIZE))
    face = face.astype("float32") / 255.0
    face = np.expand_dims(face, axis=0)
    return face
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Unable to access the webcam.")
while True:
    ret, frame = cap.read()
    if not ret:
        break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    for (x, y, w, h) in faces:
        face = frame[y:y+h, x:x+w]
        try:
            processed = preprocess(face)
            glasses_pred = glasses_model.predict(processed)[0][0]
            mask_pred = mask_model.predict(processed)[0][0]
            glasses_label = "Glasses" if glasses_pred > 0.5 else "No Glasses"
            mask_label = "Mask" if mask_pred > 0.5 else "No Mask"
            label = f"{glasses_label}, {mask_label}"
            print(f"Glasses: {glasses_pred:.2f}, Mask: {mask_pred:.2f}")
        except Exception as e:
            label = "Error"
            print(e)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(
            frame,
            label,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
    cv2.imshow("SmartWear Advisor", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()