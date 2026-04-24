# ===================== app.py =====================

import os
from flask import Flask, render_template, request, jsonify, redirect, session
from utils.inference import run_inference
from utils.weather import get_weather
from utils.db import init_db, add_user, get_users, log_detection, get_history

app = Flask(__name__)

# 🔐 SECRET KEY (IMPORTANT)
app.secret_key = os.environ.get("SECRET_KEY", "asdf")

# 🔐 ADMIN PASSWORD
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# INIT DB
init_db()


# ===================== ROUTES =====================

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/process_frame", methods=["POST"])
def process_frame():
    data = request.json
    image = data.get("image")

    result = run_inference(image)

    # log only if known
    if result["name"] != "Unknown":
        log_detection(result)

    return jsonify(result)


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    image = data.get("image")

    add_user(name, image)

    return jsonify({"success": True})


@app.route("/detail/<name>")
def detail(name):
    mask = request.args.get("mask")
    glasses = request.args.get("glasses")
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    weather = get_weather(lat, lon)

    return render_template(
        "detail.html",
        name=name,
        mask=mask,
        glasses=glasses,
        weather=weather
    )


# ===================== ADMIN =====================

ADMIN_PASSWORD = "admin123"


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
    return render_template("login.html")


@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/admin/login")

    return render_template(
        "admin.html",
        users=get_users(),
        history=get_history()
    )


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/admin/analytics")
def analytics():
    history = get_history()

    days = []
    detections = []

    return jsonify({
        "days": days,
        "detections": detections
    })


# ===================== RUN =====================

if __name__ == "__main__":
    app.run(debug=True)
