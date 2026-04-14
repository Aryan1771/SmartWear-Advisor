import cv2
import numpy as np
import face_recognition
import os
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

# ---------------- CONFIG ----------------
ENCODINGS_PATH = "data/encodings"
os.makedirs(ENCODINGS_PATH, exist_ok=True)

# ---------------- GLOBALS ----------------
known_encodings = []
known_names = []

# Load existing encodings
def load_encodings():
    global known_encodings, known_names
    known_encodings = []
    known_names = []

    for file in os.listdir(ENCODINGS_PATH):
        if file.endswith(".npy"):
            enc = np.load(os.path.join(ENCODINGS_PATH, file))
            known_encodings.append(enc)
            known_names.append(file.split(".")[0])

load_encodings()

# ---------------- FACE RECOGNITION ----------------
def recognize_face(face_encoding):
    if len(known_encodings) == 0:
        return "Unknown"

    matches = face_recognition.compare_faces(known_encodings, face_encoding)
    face_distances = face_recognition.face_distance(known_encodings, face_encoding)

    if len(face_distances) == 0:
        return "Unknown"

    best_match = np.argmin(face_distances)

    if matches[best_match]:
        return known_names[best_match]

    return "Unknown"

# ---------------- REGISTER FACE ----------------
def register_face(name):
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = face_recognition.face_locations(rgb)

        for (top, right, bottom, left) in faces:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 255), 2)

            cv2.putText(frame,
                        "Remove accessories before registering face",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2)

            face_encoding = face_recognition.face_encodings(rgb, [(top, right, bottom, left)])[0]

            # Save encoding
            np.save(os.path.join(ENCODINGS_PATH, name + ".npy"), face_encoding)

            cap.release()
            cv2.destroyAllWindows()
            load_encodings()

            messagebox.showinfo("Success", f"{name} registered successfully!")
            return

        cv2.imshow("Register Face", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

# ---------------- MAIN CAMERA ----------------
class CameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartWear Advisor")
        self.root.configure(bg="#121212")

        self.video_label = tk.Label(root, bg="#121212")
        self.video_label.pack()

        self.name_label = tk.Label(root, text="", fg="#00FFAA", bg="#121212", font=("Arial", 18))
        self.name_label.pack(pady=10)

        self.capture_btn = tk.Button(root, text="Start Camera", command=self.start_camera,
                                     bg="#1f1f1f", fg="white")
        self.capture_btn.pack(pady=5)

        self.register_btn = tk.Button(root, text="Register Face", command=self.open_register,
                                      bg="#1f1f1f", fg="white")
        self.register_btn.pack(pady=5)

        self.cap = None
        self.running = False

    def open_register(self):
        reg_window = tk.Toplevel(self.root)
        reg_window.title("Register Face")
        reg_window.configure(bg="#121212")

        tk.Label(reg_window, text="Enter Name:", fg="white", bg="#121212").pack(pady=10)

        name_entry = tk.Entry(reg_window)
        name_entry.pack(pady=5)

        def submit():
            name = name_entry.get()
            if name:
                register_face(name)
                reg_window.destroy()

        tk.Button(reg_window, text="Register", command=submit,
                  bg="#1f1f1f", fg="white").pack(pady=10)

    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        self.running = True
        self.update_frame()

    def update_frame(self):
        if not self.running:
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, faces)

        for (top, right, bottom, left), face_encoding in zip(faces, encodings):
            name = recognize_face(face_encoding)

            # GREEN BOX
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

            # NAME DISPLAY
            cv2.putText(frame, name, (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 255, 0), 2)

            if name != "Unknown":
                self.name_label.config(text=f"Welcome, {name}")
                self.show_details_screen(name)

        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        imgtk = ImageTk.PhotoImage(image=img)

        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

        self.root.after(10, self.update_frame)

    def show_details_screen(self, name):
        self.running = False
        self.cap.release()

        detail_window = tk.Toplevel(self.root)
        detail_window.title("User Details")
        detail_window.configure(bg="#121212")

        tk.Label(detail_window, text=f"User: {name}",
                 fg="#00FFAA", bg="#121212",
                 font=("Arial", 20)).pack(pady=20)

        # Placeholder for backend integration
        tk.Label(detail_window,
                 text="Fetching weather & recommendations...",
                 fg="white", bg="#121212").pack(pady=10)

        tk.Label(detail_window,
                 text="Recommendation: Wear sunglasses ☀️",
                 fg="yellow", bg="#121212").pack(pady=10)

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.mainloop()