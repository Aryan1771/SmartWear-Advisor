# ===================== app.py =====================

import os
from flask import Flask, render_template, request, jsonify, redirect, session

# Backend modules (your structure)
from backend.weather_api import get_weather
from backend.db import init_db, add_user, get_users, log_detection, get_history

# HF inference (keep this path if exists)
from utils.inference import run_inference


# ===================== APP INIT =====================

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

# 🔐 SECRET KEY
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# 🔐 ADMIN PASSWORD (ENV)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# 🔐 SESSION SECURITY (important for deploy)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# INIT DATABASE
init_db()


# ===================== ROUTES =====================

@app.route("/")
def home():
    return render_template("home.html")


# ─────────────────────────────────────────────
# PROCESS FRAME (Face + Accessories)
# ─────────────────────────────────────────────
@app.route("/process_frame", methods=["POST"])
def process_frame():
    data = request.get_json(silent=True)

    if not data or "image" not in data:
        return jsonify({"error": "Invalid input"}), 400

    image = data["image"]

    try:
        result = run_inference(image)
    except Exception as e:
        print("❌ Inference error:", e)
        return jsonify({"error": "inference_failed"}), 500

    # Log only if recognized
    if result.get("name") and result["name"] != "Unknown":
        try:
            log_detection(result)
        except Exception as e:
            print("⚠️ Logging failed:", e)

    return jsonify(result)


# ─────────────────────────────────────────────
# REGISTER USER
# ─────────────────────────────────────────────
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    if not data or "name" not in data or "image" not in data:
        return jsonify({"success": False}), 400

    name = data["name"].strip()
    image = data["image"]

    # Prevent memory crashes
    if len(image) > 500000:
        return jsonify({"success": False, "error": "Image too large"})

    try:
        add_user(name, image)
    except Exception as e:
        print("❌ Register error:", e)
        return jsonify({"success": False}), 500

    return jsonify({"success": True})


# ─────────────────────────────────────────────
# DETAIL PAGE
# ─────────────────────────────────────────────
@app.route("/detail/<name>")
def detail(name):
    mask = request.args.get("mask")
    glasses = request.args.get("glasses")

    # Safe lat/lon parsing
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except:
        lat, lon = 0, 0

    try:
        weather = get_weather(lat, lon)
    except Exception as e:
        print("⚠️ Weather error:", e)
        weather = {}

    return render_template(
        "detail.html",
        name=name,
        mask=mask,
        glasses=glasses,
        weather=weather
    )


# ===================== ADMIN =====================

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return render_template("login.html", error="Wrong password")

    return render_template("login.html")


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/admin/login")

    try:
        users = get_users()
        history = get_history()
    except Exception as e:
        print("❌ Admin load error:", e)
        users, history = [], []

    return render_template(
        "admin.html",
        users=users,
        history=history
    )


# ─────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────
@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/")


# ─────────────────────────────────────────────
# ANALYTICS (for charts)
# ─────────────────────────────────────────────
@app.route("/admin/analytics")
def analytics():
    try:
        history = get_history()
    except:
        history = []

    day_map = {}

    for h in history:
        day = (h.get("timestamp") or "")[:10]
        if not day:
            continue
        day_map[day] = day_map.get(day, 0) + 1

    days = sorted(day_map.keys())
    detections = [day_map[d] for d in days]

    return jsonify({
        "days": days,
        "detections": detections
    })


# ===================== RUN =====================

if __name__ == "__main__":
    app.run(debug=True)
