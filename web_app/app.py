import json
import os
from csv import DictWriter
from datetime import datetime
from io import StringIO
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

from backend.db import (
    add_user,
    clear_audit_history,
    clear_detection_history,
    filter_audit_rows,
    filter_history_rows,
    get_audit_log,
    get_detection_chart_data,
    get_dashboard_stats,
    get_detection_history,
    get_users,
    init_db,
    log_audit,
    log_detection,
    maintain_log_retention,
    prepare_audit_export_rows,
    prepare_history_export_rows,
)
from backend.recommendation_engine import generate_recommendation
from backend.weather_api import get_weather, get_weather_bundle
from utils.inference import register_face, run_inference

BASE_DIR = Path(__file__).resolve().parent
MAX_IMAGE_SIZE = 700_000
ADMIN_DETAIL_LIMIT = 20

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


def _admin_password_valid(password: str):
    return bool(password) and password == ADMIN_PASSWORD


def _csv_response(filename: str, fieldnames: list, rows: list):
    buffer = StringIO()
    writer = DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_float(value):
    try:
        if value is None or value == "" or str(value).strip().lower() in {"none", "null"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _detection_weather_from_request(data: dict):
    weather = dict(data.get("weather") or {})
    coords = data.get("coords") or {}

    lat = _safe_float(coords.get("lat") or weather.get("lat"))
    lon = _safe_float(coords.get("lon") or weather.get("lon"))
    city = str(weather.get("city") or "").strip()
    uv_index = _safe_float(weather.get("uv_index"))
    missing_weather = not city or city.lower() == "unknown" or uv_index is None

    if missing_weather and (lat is not None and lon is not None or city):
        try:
            fresh = get_weather_bundle(
                lat=lat,
                lon=lon,
                query=city if city and city.lower() != "unknown" else None,
            )["current"]
            for key, value in weather.items():
                if value in (None, ""):
                    continue
                if key == "city" and str(value).strip().lower() == "unknown":
                    continue
                if key == "uv_index" and _safe_float(value) is None:
                    continue
                existing = fresh.get(key)
                if existing in (None, "") or str(existing).strip().lower() == "unknown":
                    fresh[key] = value
            weather = fresh
        except Exception as exc:
            print(f"[APP] detection weather enrichment failed: {exc}")

    if not weather.get("city"):
        try:
            weather = get_weather_bundle()["current"]
        except Exception as exc:
            print(f"[APP] detection weather fallback failed: {exc}")
            weather = {}

    return weather


def _detail_log_key(name: str, mask: str, glasses: str, weather: dict):
    timestamp_bucket = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return "|".join(
        [
            timestamp_bucket,
            str(name or "Unknown"),
            str(mask or "Unknown"),
            str(glasses or "Unknown"),
            str((weather or {}).get("city") or "Unknown"),
        ]
    )


def _has_resolved_weather(weather: dict):
    weather = weather or {}
    city = str(weather.get("city") or "").strip().lower()
    return bool(city and city != "unknown")


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "service": "smartwear-web"})


@app.route("/api/sidebar-weather")
def sidebar_weather():
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except (TypeError, ValueError):
        lat, lon = None, None

    city = request.args.get("city")

    current = get_weather(lat=lat, lon=lon, query=city)
    return jsonify(
        {
            "city": current.get("city", "Unknown"),
            "temp": current.get("temp"),
            "condition": current.get("description") or current.get("condition", "Unavailable"),
            "humidity": current.get("humidity"),
            "aqi_label": current.get("aqi_label"),
            "uv_index": current.get("uv_index"),
        }
    )


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

    log_token = request.args.get("log") or _detail_log_key(
        name,
        mask,
        glasses,
        weather_bundle["current"],
    )
    if _has_resolved_weather(weather_bundle["current"]) and session.get("last_detection_log_token") != log_token:
        try:
            log_detection(name, mask, glasses, weather_bundle["current"])
            session["last_detection_log_token"] = log_token
        except Exception as exc:
            print(f"[APP] detail detection log failed: {exc}")

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
        maintain_log_retention()
        users = get_users()
        history = get_detection_history(limit=ADMIN_DETAIL_LIMIT)
        audit_logs = get_audit_log(limit=ADMIN_DETAIL_LIMIT)
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
                "detail_limit": ADMIN_DETAIL_LIMIT,
            }
        ),
    )


@app.route("/admin/analytics")
def analytics():
    guard = _admin_required()
    if guard:
        return guard

    try:
        maintain_log_retention()
        chart_data = get_detection_chart_data()
    except Exception as exc:
        print(f"[APP] analytics load failed: {exc}")
        chart_data = {"days": [], "detections": []}

    return jsonify(chart_data)


@app.route("/admin/export/history", methods=["POST"])
def export_history():
    guard = _admin_required()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    rows = prepare_history_export_rows(filter_history_rows(data.get("rows") or [], data.get("query"), data.get("user")))
    return _csv_response(
        "smartwear-history.csv",
        ["name", "timestamp", "mask", "glasses", "city", "temp", "feels_like", "aqi", "aqi_label", "uv_index"],
        rows,
    )


@app.route("/admin/export/audit", methods=["POST"])
def export_audit():
    guard = _admin_required()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    rows = prepare_audit_export_rows(filter_audit_rows(data.get("rows") or [], data.get("query")))
    return _csv_response(
        "smartwear-audit.csv",
        ["timestamp", "event", "detail", "ip"],
        rows,
    )


@app.route("/admin/history/delete-all", methods=["POST"])
def delete_all_history():
    guard = _admin_required()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    if not _admin_password_valid(data.get("password", "")):
        return jsonify({"success": False, "error": "invalid_password"}), 403

    if not clear_detection_history():
        return jsonify({"success": False, "error": "delete_failed"}), 500

    log_audit("admin_history_cleared", "Admin cleared all detection history", _client_ip())
    return jsonify({"success": True})


@app.route("/admin/history/delete-user", methods=["POST"])
def delete_user_history():
    guard = _admin_required()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    if not _admin_password_valid(data.get("password", "")):
        return jsonify({"success": False, "error": "invalid_password"}), 403

    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "missing_name"}), 400

    if not clear_detection_history(name=name):
        return jsonify({"success": False, "error": "delete_failed"}), 500

    log_audit("admin_user_history_cleared", f"Admin cleared detection history for {name}", _client_ip())
    return jsonify({"success": True, "name": name})


@app.route("/admin/audit/delete-all", methods=["POST"])
def delete_all_audit():
    guard = _admin_required()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    if not _admin_password_valid(data.get("password", "")):
        return jsonify({"success": False, "error": "invalid_password"}), 403

    if not clear_audit_history():
        return jsonify({"success": False, "error": "delete_failed"}), 500

    print(f"[ADMIN] Audit history cleared by {_client_ip()}")
    return jsonify({"success": True})


@app.route("/admin/retention/run", methods=["POST"])
def run_retention():
    guard = _admin_required()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    if not _admin_password_valid(data.get("password", "")):
        return jsonify({"success": False, "error": "invalid_password"}), 403

    maintain_log_retention()
    log_audit("admin_retention_run", "Admin triggered retention cleanup", _client_ip())
    return jsonify({"success": True})


@app.route("/admin/logout")
def logout():
    if session.get("admin"):
        log_audit("admin_logout", "Admin logged out", _client_ip())
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
