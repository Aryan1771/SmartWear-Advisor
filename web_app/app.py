import os, time, logging
import requests
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for
)
from datetime import datetime
from functools import wraps
from flask_socketio import SocketIO

from backend.weather_api import get_weather, get_hourly_forecast, uv_category
from backend.recommendation_engine import generate_recommendation
from backend.db import (
    init_db, add_user_to_db, log_audit,
    get_all_users, get_detection_history,
    get_audit_log, log_detection, delete_user_from_db
)

# ── INIT ─────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smartwear-secure-key")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APP")

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

SESSION_TIMEOUT = 30 * 60

init_db()

# ── GLOBAL CONTROL ───────────────────
_last_request_time = 0
REQUEST_INTERVAL = 1.2 

_last_result = None
_cache_time = 0
CACHE_TTL = 2  # seconds


# ── HELPERS ──────────────────────────

def _hf(endpoint: str, payload: dict):
    try:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

        r = requests.post(
            f"{HF_SPACE_URL}{endpoint}",
            json=payload,
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    except Exception as e:
        logger.error(f"[HF ERROR] {e}")
        return None


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))

        last = session.get("last_active")
        if last:
            elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
            if elapsed > SESSION_TIMEOUT:
                session.clear()
                return redirect(url_for("admin_login"))

        session["last_active"] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return wrapper


def _is_admin():
    return bool(session.get("admin"))


# ── ROUTES ───────────────────────────

@app.route("/")
def index():
    return render_template("index.html", admin_logged_in=_is_admin())


@app.route("/process_remote_frame", methods=["POST"])
def process_remote_frame():
    global _last_request_time, _last_result, _cache_time

    now = time.time()

    if now - _last_request_time < REQUEST_INTERVAL:
        return jsonify(_last_result or {"name": "Processing"})

    _last_request_time = now

    data = request.json or {}
    image = data.get("image", "")

    if not image or len(image) < 100:
        return jsonify({"name": "No Face", "error": "invalid_image"})

    if _last_result and (now - _cache_time < CACHE_TTL):
        return jsonify(_last_result)

    result = _hf("/detect", {"image": image})

    if not result:
        result = {"name": "Unknown", "mask": "Unknown", "glasses": "Unknown"}

    _last_result = result
    _cache_time = now

    return jsonify(result)


@app.route("/register_remote", methods=["POST"])
def register_remote():
    data = request.json or {}
    name = data.get("name", "").strip()
    image = data.get("image", "")

    if not name or not image:
        return jsonify({"success": False, "error": "invalid_input"})

    result = _hf("/register", {"image": image, "name": name})

    if result and result.get("success"):
        add_user_to_db(name)
        log_audit("REGISTRATION", name, request.remote_addr)

    return jsonify(result or {"success": False})


@app.route("/detail/<name>")
def detail(name):
    try:
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        city = request.args.get("city", "Delhi")
        mask = request.args.get("mask", "No Mask")
        glasses = request.args.get("glasses", "No Glasses")

        query = f"{lat},{lon}" if lat else city
        weather = get_weather(query)

        forecast = get_hourly_forecast(
            weather.get("lat"),
            weather.get("lon")
        ) if weather.get("lat") else []

        recs = generate_recommendation(weather, mask, glasses, forecast)
        uv_label, uv_class = uv_category(weather.get("uv_index", 0))

        users = get_all_users()
        profile = next((u for u in users if u["name"] == name), {})

        log_detection(name, mask, glasses, weather)

        socketio.emit("new_detection", {
            "name": name,
            "mask": mask,
            "glasses": glasses,
            "city": weather.get("city"),
            "temp": weather.get("temp"),
            "aqi": weather.get("aqi_label"),
            "uv": weather.get("uv_index"),
            "time": datetime.now().strftime("%H:%M:%S")
        })

        return render_template(
            "detail.html",
            name=name,
            profile=profile,
            weather=weather,
            recs=recs,
            forecast=forecast,
            uv_label=uv_label,
            uv_class=uv_class,
            admin_logged_in=_is_admin(),
        )

    except Exception as e:
        logger.error(f"[DETAIL ERROR] {e}")
        return "Error loading page", 500


# ── ADMIN ───────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            session["last_active"] = datetime.now().isoformat()
            return redirect(url_for("admin_dashboard"))

    return render_template("login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template(
        "admin.html",
        users=get_all_users(),
        history=get_detection_history(),
        audit=get_audit_log()
    )


@app.route("/admin/user/<name>/delete", methods=["POST"])
@admin_required
def delete_user(name):
    delete_user_from_db(name)
    return redirect(url_for("admin_dashboard"))


# ── RUN ─────────────────────────────

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
