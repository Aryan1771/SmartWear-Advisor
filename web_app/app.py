import json
import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from backend.db import (
    add_user,
    get_audit_log,
    get_dashboard_stats,
    get_detection_history,
    get_users,
    init_db,
    log_audit,
    log_detection,
)
from backend.recommendation_engine import generate_recommendation
from backend.weather_api import get_weather_bundle
from utils.inference import register_face, run_inference

BASE_DIR = Path(__file__).resolve().parent
MAX_IMAGE_SIZE = 700_000
ADMIN_HISTORY_LIMIT = 200

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

init_db()


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _safe_result_payload(result):
    payload = {
        "recognized": False,
        "name": "Unknown",
        "mask": "No Mask",
        "glasses": "No Glasses",
        "box": None,
        "error": None,
    }
    payload.update(result or {})
    payload["recognized"] = bool(payload.get("recognized") or payload.get("name") != "Unknown")
    return payload


def _admin_required():
    if session.get("admin"):
        return None
    return redirect(url_for("admin_login"))


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "service": "smartwear-web"})


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/process_frame", methods=["POST"])
def process_frame():
    data = request.get_json(silent=True) or {}
    image = data.get("image")

    if not image or not isinstance(image, str):
        return jsonify(_safe_result_payload({"error": "invalid_input"})), 400

    if len(image) > MAX_IMAGE_SIZE:
        return jsonify(_safe_result_payload({"error": "image_too_large"})), 413

    result = _safe_result_payload(run_inference(image))

    if result["recognized"]:
        weather = data.get("weather") or {}
        try:
            log_detection(result["name"], result["mask"], result["glasses"], weather)
        except Exception as exc:
            print(f"[APP] detection log failed: {exc}")

    return jsonify(result)


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    image = data.get("image")

    if not name or not image or not isinstance(image, str):
        return jsonify({"success": False, "error": "missing_name_or_image"}), 400

    if len(name) < 2 or len(name) > 60:
        return jsonify({"success": False, "error": "invalid_name"}), 400

    if len(image) > MAX_IMAGE_SIZE:
        return jsonify({"success": False, "error": "image_too_large"}), 413

    try:
        remote_result = register_face(name, image)
        if not remote_result.get("success"):
            log_audit(
                "user_register_failed",
                f"HF register failed for {name}: {remote_result.get('message', remote_result.get('error'))}",
                _client_ip(),
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": remote_result.get("error", "register_failed"),
                        "message": remote_result.get("message", "Face registration failed."),
                    }
                ),
                502,
            )

        try:
            add_user(name, image)
        except Exception as metadata_exc:
            print(f"[APP] local metadata register failed: {metadata_exc}")

        log_audit("user_registered", f"Registered {name}", _client_ip())
        return jsonify(
            {
                "success": True,
                "name": name,
                "message": remote_result.get("message", "Registered successfully."),
            }
        )
    except Exception as exc:
        print(f"[APP] register failed: {exc}")
        return jsonify({"success": False, "error": "register_failed"}), 500


@app.route("/detail/<name>")
def detail(name):
    mask = request.args.get("mask", "Unknown")
    glasses = request.args.get("glasses", "Unknown")

    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except (TypeError, ValueError):
        lat, lon = None, None

    city = request.args.get("city")

    try:
        weather_bundle = get_weather_bundle(lat=lat, lon=lon, query=city)
    except Exception as exc:
        print(f"[APP] weather bundle failed: {exc}")
        weather_bundle = get_weather_bundle()

    return render_template(
        "detail.html",
        name=name,
        mask=mask,
        glasses=glasses,
        weather=weather_bundle["current"],
        forecast=weather_bundle["forecast"],
        location=weather_bundle["location"],
        recommendations=generate_recommendation(
            weather_bundle["current"],
            mask,
            glasses,
            weather_bundle["forecast"],
        ),
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        supplied = request.form.get("password", "")
        if supplied == ADMIN_PASSWORD:
            session["admin"] = True
            log_audit("admin_login", "Successful admin login", _client_ip())
            return redirect(url_for("admin"))

        log_audit("admin_login_failed", "Failed admin login attempt", _client_ip())
        return render_template("login.html", error="Wrong password")

    return render_template("login.html", error=None)


@app.route("/admin")
def admin():
    guard = _admin_required()
    if guard:
        return guard

    try:
        users = get_users()
        history = get_detection_history(limit=ADMIN_HISTORY_LIMIT)
        audit_logs = get_audit_log(limit=ADMIN_HISTORY_LIMIT)
        stats = get_dashboard_stats()
    except Exception as exc:
        print(f"[APP] admin load failed: {exc}")
        users, history, audit_logs, stats = [], [], [], get_dashboard_stats()

    return render_template(
        "admin.html",
        users=users,
        history=history,
        audit_logs=audit_logs,
        stats=stats,
        admin_payload=json.dumps(
            {
                "users": users,
                "history": history,
                "audit_logs": audit_logs,
                "stats": stats,
            }
        ),
    )


@app.route("/admin/analytics")
def analytics():
    guard = _admin_required()
    if guard:
        return guard

    try:
        history = get_detection_history(limit=ADMIN_HISTORY_LIMIT)
    except Exception:
        history = []

    day_map = {}
    for item in history:
        day = str(item.get("timestamp", ""))[:10]
        if day:
            day_map[day] = day_map.get(day, 0) + 1

    days = sorted(day_map)
    return jsonify({"days": days, "detections": [day_map[day] for day in days]})


@app.route("/admin/logout")
def logout():
    if session.get("admin"):
        log_audit("admin_logout", "Admin logged out", _client_ip())
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
