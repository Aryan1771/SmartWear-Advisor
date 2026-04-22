# web_app/app.py
# Flask web application for SmartWear Advisor.
# All ML inference is proxied to the HuggingFace Space FastAPI server.
# UI: index, detail, admin dashboard, admin login.

import os, io, csv
import requests
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, Response, flash,
)
from pathlib import Path
from datetime import datetime
from functools import wraps

from backend.db import (
    init_db, add_user_to_db, delete_user_from_db,
    log_detection, log_audit,
    get_all_users, get_detection_history, get_audit_log,
)
from backend.weather_api import get_weather, get_hourly_forecast, uv_category
from backend.recommendation_engine import generate_recommendation
from keepalive import start_keepalive

# ── App setup ────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smartwear-change-this-in-prod")

HF_SPACE_URL   = os.getenv("HF_SPACE_URL", "http://localhost:8000").rstrip("/")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SESSION_TIMEOUT = 1800  # seconds (30 min)

# Initialise database tables on startup
init_db()

# Start HuggingFace Space keepalive background thread
start_keepalive()


# ── Helpers ───────────────────────────────────────────────────────

def _hf(endpoint: str, payload: dict):
    """POST to HuggingFace Space and return parsed JSON, or None on error."""
    try:
        r = requests.post(
            f"{HF_SPACE_URL}{endpoint}",
            json=payload,
            timeout=35,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[HF] {endpoint} error: {e}")
        return None


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in as admin.", "warning")
            return redirect(url_for("admin_login"))
        # Session timeout check
        last = session.get("last_active")
        if last:
            elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
            if elapsed > SESSION_TIMEOUT:
                session.clear()
                flash("Session timed out after 30 minutes of inactivity.", "warning")
                return redirect(url_for("admin_login"))
        session["last_active"] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated


def _is_admin():
    return bool(session.get("admin"))


# ── Public routes ─────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", admin_logged_in=_is_admin())


@app.route("/process_remote_frame", methods=["POST"])
def process_remote_frame():
    """Proxy camera frame to HF Space for face detection and accessory analysis."""
    data  = request.json or {}
    image = data.get("image", "")
    if not image:
        return jsonify({"name": "Unknown", "box": None})

    result = _hf("/detect", {"image": image})
    if not result:
        return jsonify({"name": "Unknown", "box": None,
                        "error": "Inference server unavailable"})
    return jsonify(result)


@app.route("/register_remote", methods=["POST"])
def register_remote():
    """Proxy registration frame + name to HF Space, then persist user in DB."""
    data  = request.json or {}
    name  = data.get("name", "").strip()
    image = data.get("image", "")

    if not name:
        return jsonify({"success": False, "message": "Name cannot be empty."})
    if not image:
        return jsonify({"success": False, "message": "No image received."})

    result = _hf("/register", {"image": image, "name": name})
    if result is None:
        return jsonify({"success": False,
                        "message": "Could not reach inference server. Try again."})

    if result.get("success"):
        add_user_to_db(name)
        log_audit("REGISTRATION", f"User '{name}' registered", request.remote_addr)

    return jsonify(result)


@app.route("/detail/<name>")
def detail(name):
    lat     = request.args.get("lat")
    lon     = request.args.get("lon")
    city    = request.args.get("city", "Ghaziabad")
    mask    = request.args.get("mask",    "No Mask")
    glasses = request.args.get("glasses", "No Glasses")

    # Weather (use GPS coords if available, else city name)
    query   = f"{lat},{lon}" if lat and lat not in ("null", "None", "") else city
    weather = get_weather(query)

    # Hourly forecast (Open-Meteo)
    w_lat    = weather.get("lat") or lat
    w_lon    = weather.get("lon") or lon
    forecast = get_hourly_forecast(w_lat, w_lon)

    # Recommendations
    recs = generate_recommendation(weather, mask, glasses, forecast)

    # UV label
    uv_label, uv_class = uv_category(weather.get("uv_index", 0))

    # User profile from DB
    users   = get_all_users()
    profile = next((u for u in users if u.get("name") == name),
                   {"registered_on": "N/A", "notes": "Mobile Registration",
                    "detection_count": 0})

    # Log this detection
    log_detection(name, mask, glasses, weather)

    return render_template(
        "detail.html",
        name          = name,
        profile       = profile,
        acc           = {"mask": mask, "glasses": glasses},
        weather       = weather,
        forecast      = forecast,
        recs          = recs,
        uv_label      = uv_label,
        uv_class      = uv_class,
        admin_logged_in = _is_admin(),
    )


# ── Admin routes ──────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["admin"]       = True
            session["last_active"] = datetime.now().isoformat()
            log_audit("ADMIN_LOGIN", "Admin logged in", request.remote_addr)
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect password. Try again.", "danger")
    return render_template("login.html", admin_logged_in=False)


@app.route("/admin/logout")
def admin_logout():
    if session.get("admin"):
        log_audit("ADMIN_LOGOUT", "Admin logged out", request.remote_addr)
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    users   = get_all_users()
    history = get_detection_history(limit=50)
    audit   = get_audit_log(limit=30)
    return render_template(
        "admin.html",
        users           = users,
        history         = history,
        audit           = audit,
        admin_logged_in = True,
    )


@app.route("/admin/user/<name>/delete", methods=["POST"])
@admin_required
def delete_user(name):
    # Remove encoding from HF Space
    try:
        requests.delete(f"{HF_SPACE_URL}/user/{name}", timeout=10)
    except Exception as e:
        print(f"[HF] delete user error: {e}")
    delete_user_from_db(name)
    log_audit("DELETE_USER", f"User '{name}' deleted", request.remote_addr)
    flash(f"User '{name}' deleted successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/export_csv")
@admin_required
def export_csv():
    users  = get_all_users()
    buf    = io.StringIO()
    fields = ["name", "registered_on", "notes", "detection_count"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(users)
    buf.seek(0)
    log_audit("EXPORT_CSV", "Admin exported registered users CSV", request.remote_addr)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=registered_users.csv"},
    )


@app.route("/admin/history_json")
@admin_required
def history_json():
    name    = request.args.get("name")
    history = get_detection_history(name=name or None, limit=100)
    return jsonify(history)


# Session heartbeat — called every minute from JS to reset timeout
@app.route("/admin/heartbeat", methods=["POST"])
@admin_required
def heartbeat():
    return jsonify({"ok": True})


# ── Keepalive — start HuggingFace Space ping thread ──────────────
# Imported here so it runs once when gunicorn loads the app module.
try:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hf_space"))
    from keepalive import start_keepalive
    start_keepalive()
except Exception as _ke:
    print(f"[App] Keepalive not started: {_ke}")
