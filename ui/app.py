import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import messagebox, simpledialog

try:
    import face_recognition
except ModuleNotFoundError:
    face_recognition = None

try:
    from backend.recommendation_engine import generate_recommendation
    from backend.weather_api import get_weather
    from ui.model_utils import AccessoryDetector
except ModuleNotFoundError:
    import sys

    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from backend.recommendation_engine import generate_recommendation
    from backend.weather_api import get_weather
    from ui.model_utils import AccessoryDetector


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
ENCODINGS_DIR = DATA_DIR / "encodings"
USERS_FILE = DATA_DIR / "registered_users.json"
ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

BG_PRIMARY = "#0d1117"
BG_PANEL = "#161b22"
BG_CARD = "#1f2937"
BG_ACCENT = "#238636"
BG_BUTTON = "#21262d"
TEXT_PRIMARY = "#f0f6fc"
TEXT_SECONDARY = "#8b949e"
TEXT_SUCCESS = "#3fb950"
TEXT_WARNING = "#f2cc60"
TEXT_DANGER = "#ff7b72"
CAMERA_SIZE = (960, 540)


def require_face_recognition():
    if face_recognition is None:
        raise ModuleNotFoundError(
            "face_recognition is not installed. Install it with 'pip install face-recognition' before running the app."
        )


def load_json_file(path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return default


def save_json_file(path, payload):
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


class FaceRegistry:
    def __init__(self):
        require_face_recognition()
        self.known_encodings = []
        self.known_names = []
        self.user_profiles = {}
        self.reload()

    def reload(self):
        self.known_encodings = []
        self.known_names = []
        self.user_profiles = load_json_file(USERS_FILE, {})

        for encoding_file in sorted(ENCODINGS_DIR.glob("*.npy")):
            try:
                encoding = np.load(encoding_file)
            except OSError:
                continue
            self.known_encodings.append(encoding)
            self.known_names.append(encoding_file.stem)

    def recognize(self, face_encoding):
        if not self.known_encodings:
            return "Unknown", None

        matches = face_recognition.compare_faces(self.known_encodings, face_encoding, tolerance=0.48)
        distances = face_recognition.face_distance(self.known_encodings, face_encoding)
        if len(distances) == 0:
            return "Unknown", None

        best_index = int(np.argmin(distances))
        if matches[best_index]:
            name = self.known_names[best_index]
            return name, self.user_profiles.get(name, {})
        return "Unknown", None

    def register(self, name, face_encoding):
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Name is required for registration.")

        file_name = f"{cleaned_name}.npy"
        np.save(ENCODINGS_DIR / file_name, face_encoding)

        profiles = load_json_file(USERS_FILE, {})
        profiles[cleaned_name] = {
            "name": cleaned_name,
            "registered_on": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "notes": "Registered with clear face capture for SmartWear Advisor.",
        }
        save_json_file(USERS_FILE, profiles)
        self.reload()


class SmartWearApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartWear Advisor")
        self.root.configure(bg=BG_PRIMARY)
        self.root.geometry("1380x820")
        self.root.minsize(1200, 760)

        self.registry = FaceRegistry()
        self.accessory_detector = AccessoryDetector()

        self.cap = None
        self.running = False
        self.detected_name = None
        self.recognition_streak = 0
        self.details_window = None
        self.latest_frame = None
        self.last_detection = None
        self.weather_city = tk.StringVar(value="Delhi")
        self.status_text = tk.StringVar(value="Camera idle. Start live recognition to begin.")
        self.overlay_text = tk.StringVar(value="Face registration requires a clean face capture.")
        self.recognition_text = tk.StringVar(value="Waiting for a registered face")
        self.accessory_text = tk.StringVar(value="Accessories: --")
        self.user_text = tk.StringVar(value="User profile not loaded")
        self.model_text = tk.StringVar(value=self.accessory_detector.status_summary())

        self.build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_layout(self):
        header = tk.Frame(self.root, bg=BG_PRIMARY)
        header.pack(fill="x", padx=24, pady=(20, 12))

        tk.Label(
            header,
            text="SmartWear Advisor",
            font=("Segoe UI Semibold", 24),
            fg=TEXT_PRIMARY,
            bg=BG_PRIMARY,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Dark-theme face recognition, accessory awareness, and recommendation dashboard.",
            font=("Segoe UI", 11),
            fg=TEXT_SECONDARY,
            bg=BG_PRIMARY,
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(self.root, bg=BG_PRIMARY)
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.build_camera_panel(body)
        self.build_side_panel(body)

    def build_camera_panel(self, parent):
        panel = tk.Frame(parent, bg=BG_PANEL, bd=0, highlightthickness=0)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.camera_label = tk.Label(
            panel,
            bg="#05070a",
            fg=TEXT_PRIMARY,
            text="Camera preview will appear here",
            font=("Segoe UI", 16),
        )
        self.camera_label.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)

        camera_footer = tk.Frame(panel, bg=BG_PANEL)
        camera_footer.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        camera_footer.grid_columnconfigure(0, weight=1)

        tk.Label(
            camera_footer,
            textvariable=self.status_text,
            font=("Segoe UI", 10),
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            anchor="w",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            camera_footer,
            textvariable=self.overlay_text,
            font=("Segoe UI", 10),
            fg=TEXT_WARNING,
            bg=BG_PANEL,
            anchor="e",
            justify="right",
        ).grid(row=0, column=1, sticky="e")

    def build_side_panel(self, parent):
        panel = tk.Frame(parent, bg=BG_PRIMARY)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        controls = tk.Frame(panel, bg=BG_PANEL)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        tk.Label(
            controls,
            text="Session Controls",
            font=("Segoe UI Semibold", 14),
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=18, pady=(18, 6))

        tk.Label(
            controls,
            text="Weather city",
            font=("Segoe UI", 10),
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=18)

        tk.Entry(
            controls,
            textvariable=self.weather_city,
            font=("Segoe UI", 11),
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
        ).pack(fill="x", padx=18, pady=(6, 12))

        button_row = tk.Frame(controls, bg=BG_PANEL)
        button_row.pack(fill="x", padx=18, pady=(0, 18))

        self.make_button(button_row, "Start Camera", self.start_camera).pack(fill="x", pady=(0, 10))
        self.make_button(button_row, "Stop Camera", self.stop_camera).pack(fill="x", pady=(0, 10))
        self.make_button(button_row, "Register Face", self.open_registration).pack(fill="x")

        self.build_status_card(panel, "Model Status", self.model_text, row=1)
        self.build_status_card(panel, "Recognition", self.recognition_text, row=2)
        self.build_status_card(panel, "Accessory Summary", self.accessory_text, row=3)
        self.build_status_card(panel, "Registered User", self.user_text, row=4)

        dataset_card = tk.Frame(panel, bg=BG_CARD)
        dataset_card.grid(row=5, column=0, sticky="ew")
        tk.Label(
            dataset_card,
            text="Training Note",
            font=("Segoe UI Semibold", 13),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(
            dataset_card,
            text=(
                "Train separate mask and glasses classifiers with two classes each:\n"
                "with_mask / without_mask and with_glasses / without_glasses."
            ),
            font=("Segoe UI", 10),
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 18))

    def build_status_card(self, parent, title, text_var, row):
        card = tk.Frame(parent, bg=BG_CARD)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        tk.Label(
            card,
            text=title,
            font=("Segoe UI Semibold", 13),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(
            card,
            textvariable=text_var,
            font=("Segoe UI", 10),
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            justify="left",
            wraplength=360,
        ).pack(anchor="w", padx=18, pady=(0, 18))

    def make_button(self, parent, label, command):
        return tk.Button(
            parent,
            text=label,
            command=command,
            font=("Segoe UI Semibold", 11),
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_ACCENT,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=12,
            pady=10,
            cursor="hand2",
        )

    def start_camera(self):
        if self.running:
            return

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera Error", "Unable to access the webcam. Please check camera permissions.")
            return

        self.running = True
        self.detected_name = None
        self.recognition_streak = 0
        self.status_text.set("Camera active. Looking for the closest face in frame.")
        self.recognition_text.set("Scanning for registered users...")
        self.update_frame()

    def stop_camera(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.status_text.set("Camera stopped. You can restart recognition anytime.")

    def update_frame(self):
        if not self.running or self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok:
            self.status_text.set("Camera frame unavailable. Check the device and retry.")
            self.stop_camera()
            return

        frame = cv2.flip(frame, 1)
        self.latest_frame = frame.copy()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame)
        face_locations = sorted(
            face_locations,
            key=lambda face: (face[2] - face[0]) * (face[1] - face[3]),
            reverse=True,
        )

        if face_locations:
            primary_face = face_locations[0]
            encodings = face_recognition.face_encodings(rgb_frame, [primary_face])
            if encodings:
                face_encoding = encodings[0]
                name, profile = self.registry.recognize(face_encoding)
                accessory_status = self.accessory_detector.analyze(frame, primary_face)
                self.last_detection = {
                    "name": name,
                    "profile": profile or {},
                    "accessories": accessory_status,
                }
                self.draw_face_box(frame, primary_face, name)
                self.accessory_text.set(
                    f"{accessory_status['mask']} | {accessory_status['glasses']} | "
                    f"Confidence: {accessory_status['confidence']} | Source: {accessory_status.get('source', 'n/a')}"
                )

                if name != "Unknown":
                    self.user_text.set(
                        f"{name}\nRegistered: {profile.get('registered_on', 'Unknown')}\n"
                        f"{profile.get('notes', 'No notes available')}"
                    )
                    self.recognition_text.set(f"Recognized registered user: {name}")
                    self.status_text.set("Registered face detected. Preparing details screen.")
                    self.recognition_streak = self.recognition_streak + 1 if self.detected_name == name else 1
                    self.detected_name = name
                    if self.recognition_streak >= 8:
                        self.show_details_screen(name, profile or {}, accessory_status)
                        return
                else:
                    self.detected_name = None
                    self.recognition_streak = 0
                    self.recognition_text.set("Face detected but not registered.")
                    self.user_text.set("Unknown user. Register the face to unlock the detail dashboard.")
                    self.status_text.set("Face found. Awaiting a registered match.")
            else:
                self.handle_no_face_state("Face detected, but encoding could not be created.")
        else:
            self.handle_no_face_state("No face detected. Center your face inside the camera view.")

        self.render_frame(frame)
        self.root.after(15, self.update_frame)

    def draw_face_box(self, frame, face_box, name):
        top, right, bottom, left = face_box
        color = (0, 255, 0) if name != "Unknown" else (0, 200, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, max(0, top - 34)), (right, top), color, -1)
        cv2.putText(
            frame,
            name,
            (left + 8, top - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (10, 15, 22),
            2,
        )

    def handle_no_face_state(self, status_message):
        self.detected_name = None
        self.recognition_streak = 0
        self.status_text.set(status_message)
        self.recognition_text.set("Waiting for a registered face")
        self.accessory_text.set("Accessories: --")
        self.user_text.set("User profile not loaded")

    def render_frame(self, frame):
        display_frame = cv2.resize(frame, CAMERA_SIZE, interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=image)
        self.camera_label.configure(image=photo, text="")
        self.camera_label.image = photo

    def open_registration(self):
        if not self.running:
            self.start_camera()
        if not self.running:
            return

        name = simpledialog.askstring("Register Face", "Enter the user's name:", parent=self.root)
        if not name:
            return

        self.capture_registration(name.strip())

    def capture_registration(self, name):
        if not self.running or self.cap is None:
            messagebox.showerror("Camera Error", "Start the camera before registering a face.")
            return

        self.overlay_text.set("Remove accessories before registering face")
        self.status_text.set("Registration started. Look straight into the camera with no mask or glasses.")

        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            preview = frame.copy()
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)

            message = "Align one face inside the frame"
            color = (0, 255, 255)

            if len(face_locations) == 1:
                face_box = face_locations[0]
                top, right, bottom, left = face_box
                cv2.rectangle(preview, (left, top), (right, bottom), (0, 255, 255), 2)
                accessories = self.accessory_detector.analyze(frame, face_box)

                if accessories["accessories_clear"]:
                    encodings = face_recognition.face_encodings(rgb_frame, [face_box])
                    if encodings:
                        self.registry.register(name, encodings[0])
                        self.overlay_text.set("Face registration requires a clean face capture.")
                        self.status_text.set(f"{name} registered successfully.")
                        self.recognition_text.set(f"Registered user ready: {name}")
                        self.user_text.set(
                            f"{name}\nRegistered: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
                            "Profile captured with accessory-free registration."
                        )
                        cv2.destroyWindow("Face Registration")
                        messagebox.showinfo("Registration Complete", f"{name} has been registered successfully.")
                        return
                else:
                    message = "Remove accessories before registering face"
                    color = (0, 170, 255)
            elif len(face_locations) > 1:
                message = "Only one face can be registered at a time"
                color = (0, 140, 255)

            cv2.putText(preview, message, (18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(
                preview,
                "Press ESC to cancel registration",
                (18, preview.shape[0] - 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (220, 220, 220),
                2,
            )
            cv2.imshow("Face Registration", preview)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break

        self.overlay_text.set("Face registration requires a clean face capture.")
        self.status_text.set("Registration cancelled.")
        cv2.destroyWindow("Face Registration")

    def show_details_screen(self, name, profile, accessories):
        self.stop_camera()
        self.overlay_text.set("Face registration requires a clean face capture.")

        if self.details_window is not None and self.details_window.winfo_exists():
            self.details_window.destroy()

        weather = self.fetch_weather(self.weather_city.get().strip() or "Delhi")
        recommendations = generate_recommendation(
            weather=weather,
            is_mask=accessories["mask"] == "Mask Detected",
            is_glasses=accessories["glasses"] == "Glasses Detected",
        )

        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"{name} | SmartWear Detail View")
        detail_window.configure(bg=BG_PRIMARY)
        detail_window.geometry("980x720")
        detail_window.minsize(900, 660)
        self.details_window = detail_window

        header = tk.Frame(detail_window, bg=BG_PRIMARY)
        header.pack(fill="x", padx=24, pady=(22, 16))
        tk.Label(
            header,
            text=f"Recognized: {name}",
            font=("Segoe UI Semibold", 24),
            fg=TEXT_PRIMARY,
            bg=BG_PRIMARY,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="User profile, accessory status, and weather-aware recommendations",
            font=("Segoe UI", 11),
            fg=TEXT_SECONDARY,
            bg=BG_PRIMARY,
        ).pack(anchor="w", pady=(4, 0))

        grid = tk.Frame(detail_window, bg=BG_PRIMARY)
        grid.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        grid.grid_rowconfigure(1, weight=1)

        self.detail_card(
            grid,
            "User Details",
            [
                f"Name: {name}",
                f"Registered On: {profile.get('registered_on', 'Unknown')}",
                f"Profile Notes: {profile.get('notes', 'No notes saved')}",
            ],
            0,
            0,
        )
        self.detail_card(
            grid,
            "Face & Accessory Status",
            [
                "Recognition: Registered face matched successfully",
                f"Mask: {accessories['mask']}",
                f"Glasses: {accessories['glasses']}",
                f"Detector Confidence: {accessories['confidence']}",
                f"Detector Source: {accessories.get('source', 'n/a')}",
            ],
            0,
            1,
        )
        self.detail_card(
            grid,
            "Weather Snapshot",
            [
                f"City: {weather['city']}",
                f"Temperature: {weather['temp']} C",
                f"Condition: {weather['condition'].title()}",
                f"Humidity: {weather['humidity']}%",
            ],
            1,
            0,
        )
        self.detail_card(
            grid,
            "Recommendations",
            recommendations,
            1,
            1,
        )

        footer = tk.Frame(detail_window, bg=BG_PRIMARY)
        footer.pack(fill="x", padx=24, pady=(0, 24))
        self.make_button(footer, "Return to Live Camera", self.restart_session).pack(side="left")

    def detail_card(self, parent, title, lines, row, column):
        card = tk.Frame(parent, bg=BG_CARD)
        card.grid(row=row, column=column, sticky="nsew", padx=(0, 16) if column == 0 else (0, 0), pady=(0, 16))
        tk.Label(
            card,
            text=title,
            font=("Segoe UI Semibold", 14),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", padx=18, pady=(18, 10))
        for line in lines:
            tk.Label(
                card,
                text=line,
                font=("Segoe UI", 11),
                fg=TEXT_SECONDARY if "Recommendation" not in title else TEXT_PRIMARY,
                bg=BG_CARD,
                wraplength=390,
                justify="left",
            ).pack(anchor="w", padx=18, pady=(0, 8))

    def restart_session(self):
        if self.details_window is not None and self.details_window.winfo_exists():
            self.details_window.destroy()
        self.details_window = None
        self.start_camera()

    def fetch_weather(self, city):
        try:
            return get_weather(city)
        except Exception:
            return self.build_weather_snapshot(city)

    def build_weather_snapshot(self, city):
        city_key = city.lower()
        presets = {
            "delhi": {"temp": 32, "condition": "sunny", "humidity": 34},
            "mumbai": {"temp": 29, "condition": "humid", "humidity": 76},
            "bangalore": {"temp": 24, "condition": "cloudy", "humidity": 58},
            "london": {"temp": 12, "condition": "cold", "humidity": 72},
        }
        data = presets.get(city_key, {"temp": 26, "condition": "clear", "humidity": 50})
        return {"city": city.title(), **data}

    def on_close(self):
        self.stop_camera()
        try:
            cv2.destroyAllWindows()
        finally:
            self.root.destroy()


def run():
    require_face_recognition()
    root = tk.Tk()
    app = SmartWearApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
