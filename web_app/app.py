# web_app/app.py
# Flask web application for SmartWear Advisor.
# All ML inference is proxied to the HuggingFace Space FastAPI server.
# UI: index, detail, admin dashboard, admin login.

import os, io, csv
import requests
import base64
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, Response, flash,
)
from datetime import datetime
from functools import wraps
from backend.db import init_db, add_user_to_db, log_audit
from keepalive import start_keepalive

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smartwear-secure-key")

# Configuration
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN") # Your hf_... token

init_db()
start_keepalive()
@app.route("/ping")
def ping():
#     Health-check for keepalive services.
#     Register this URL at uptimerobot.com (free, 5-min interval)
#     to prevent Render free tier from sleeping.
#     Also pinged by HF Space every 10 min as mutual keepalive.
    return jsonify({"status": "alive", "service": "SmartWear Render"})

# ── Helpers ───────────────────────────────────────────────────────

def _hf(endpoint: str, payload: dict):
    """Authenticated proxy to the Private Hugging Face Space."""
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
        print(f"[HF Proxy Error] {endpoint}: {e}")
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
    return render_template("index.html", admin_logged_in=bool(session.get("admin")))


@app.route("/process_remote_frame", methods=["POST"])
def process_remote_frame():
    data = request.json or {}
    result = _hf("/detect", {"image": data.get("image", "")})
    return jsonify(result if result else {"name": "Unknown", "box": None})


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
    if result and result.get("success"):
        add_user_to_db(name)
        log_audit("REGISTRATION", f"User '{name}' registered", request.remote_addr)
    return jsonify(result if result else {"success": False, "message": "Backend Unreachable"})

@app.route("/detail/<name>")
def detail(name):
    lat     = request.args.get("lat")
    lon     = request.args.get("lon")
    city    = request.args.get("city", "Ghaziabad")
    mask    = request.args.get("mask", "No Mask")
    glasses = request.args.get("glasses", "No Glasses")

    # ── Weather ─────────────────────────────
    query = f"{lat},{lon}" if lat and lat not in ("null", "None", "") else city
    weather = get_weather(query) or {}

    # ── Forecast ────────────────────────────
    w_lat = weather.get("lat") or lat
    w_lon = weather.get("lon") or lon

    if w_lat and w_lon:
        forecast = get_hourly_forecast(w_lat, w_lon)
    else:
        forecast = []

    # ── Recommendations ─────────────────────
    try:
        recs = generate_recommendation(weather, mask, glasses, forecast)
    except Exception as e:
        print("[Detail] Recommendation error:", e)
        recs = []

    # ── UV ──────────────────────────────────
    try:
        uv_label, uv_class = uv_category(weather.get("uv_index", 0))
    except:
        uv_label, uv_class = "Unknown", "low"

    # ── Profile ─────────────────────────────
    users = get_all_users()
    profile = next(
        (u for u in users if u.get("name") == name),
        {
            "registered_on": "N/A",
            "notes": "Mobile Registration",
            "detection_count": 0
        }
    )

    # ── Log detection ───────────────────────
    try:
        log_detection(name, mask, glasses, weather)
    except Exception as e:
        print("[Detail] Log error:", e)

    return render_template(
        "detail.html",
        name=name,
        profile=profile,
        acc={"mask": mask, "glasses": glasses},
        weather=weather,
        forecast=forecast,
        recs=recs,
        uv_label=uv_label,
        uv_class=uv_class,
        admin_logged_in=_is_admin(),
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
     start_keepalive(ping_hf=True, ping_render=False)
except Exception as _ke:
     print("[App] Keepalive not started: {}".format(_ke))
