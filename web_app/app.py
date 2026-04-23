import os, io, csv
import requests
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, Response, flash,
)
from datetime import datetime
from functools import wraps

# ✅ WebSocket
from flask_socketio import SocketIO

from backend.weather_api import (
    get_weather,
    get_hourly_forecast,
    uv_category,
)
from backend.recommendation_engine import generate_recommendation

from backend.db import (
    init_db,
    add_user_to_db,
    log_audit,
    get_all_users,
    get_detection_history,
    get_audit_log,
    log_detection,
    delete_user_from_db
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smartwear-secure-key")

# ✅ SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Config
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SESSION_TIMEOUT = 30 * 60

init_db()

# ── Helpers ─────────────────────────────

def broadcast_analytics():
    history = get_detection_history(limit=200) or []
    total = len(history)
    mask = sum(1 for h in history if h.get("mask") == "Mask")

    socketio.emit("analytics_update", {
        "total": total,
        "mask_rate": (mask / total * 100) if total else 0
    })


def _hf(endpoint: str, payload: dict):
    try:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
        r = requests.post(
            f"{HF_SPACE_URL}{endpoint}",
            json=payload,
            headers=headers,
            timeout=35,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[HF ERROR] {e}")
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

# ── ROUTES ─────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", admin_logged_in=_is_admin())


@app.route("/process_remote_frame", methods=["POST"])
def process_remote_frame():
    data = request.json or {}
    result = _hf("/detect", {"image": data.get("image", "")})
    return jsonify(result or {"name": "Unknown"})


@app.route("/register_remote", methods=["POST"])
def register_remote():
    data = request.json or {}
    name = data.get("name", "").strip()
    image = data.get("image", "")

    if not name or not image:
        return jsonify({"success": False})

    result = _hf("/register", {"image": image, "name": name})

    if result and result.get("success"):
        add_user_to_db(name)
        log_audit("REGISTRATION", name, request.remote_addr)

    return jsonify(result or {"success": False})


@app.route("/detail/<name>")
def detail(name):
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    city = request.args.get("city", "Delhi")
    mask = request.args.get("mask", "No Mask")
    glasses = request.args.get("glasses", "No Glasses")

    query = f"{lat},{lon}" if lat else city
    weather = get_weather(query) or {}

    forecast = get_hourly_forecast(
        weather.get("lat"),
        weather.get("lon")
    ) if weather.get("lat") else []

    recs = generate_recommendation(weather, mask, glasses, forecast)

    uv_label, uv_class = uv_category(weather.get("uv_index", 0))

    users = get_all_users()
    profile = next((u for u in users if u["name"] == name), {})

    try:
        log_detection(name, mask, glasses, weather)

        # 🔥 REAL-TIME EVENT
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

        broadcast_analytics()

    except Exception as e:
        print("[Detail Error]", e)

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

# ── ADMIN ─────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            session["last_active"] = datetime.now().isoformat()
            broadcast_analytics()
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


@app.route("/admin/analytics")
@admin_required
def analytics():
    history = get_detection_history(limit=500) or []

    by_day = {}
    mask_count = {"Mask": 0, "No Mask": 0}
    glasses_count = {"Glasses": 0, "No Glasses": 0}

    for h in history:
        ts = h.get("timestamp")
        if ts:
            day = str(ts)[:10]
            by_day[day] = by_day.get(day, 0) + 1

        mask_count[h.get("mask", "No Mask")] += 1
        glasses_count[h.get("glasses", "No Glasses")] += 1

    days = sorted(by_day.keys())

    return jsonify({
        "days": days,
        "detections": [by_day[d] for d in days],
        "mask": mask_count,
        "glasses": glasses_count
    })


@app.route("/admin/user/<name>/delete", methods=["POST"])
@admin_required
def delete_user(name):
    delete_user_from_db(name)
    return redirect(url_for("admin_dashboard"))


# ── RUN ─────────────────────────────

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
