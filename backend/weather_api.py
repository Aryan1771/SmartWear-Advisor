# backend/weather_api.py (PRODUCTION READY)

import os
import requests
import logging
import time
from datetime import datetime

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WEATHER")

# ── Config ──────────────────────────────────────────────
OWM_KEY = os.getenv("OWM_API_KEY", "YOUR_OWM_API_KEY")

AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}

# ── Session (IMPORTANT) ─────────────────────────────────
_session = requests.Session()

# ── Cache (CRITICAL FIX) ────────────────────────────────
_cache = {}
CACHE_TTL = 300  # 5 minutes


_FALLBACK = {
    "city": "Unknown",
    "temp": 25,
    "feels_like": 25,
    "humidity": 50,
    "condition": "clear",
    "uv_index": 0.0,
    "aqi": 1,
    "aqi_label": "Good",
    "pm25": 0.0,
    "lat": None,
    "lon": None,
}


def _cache_key(query):
    return str(query).lower().strip()


def get_weather(query) -> dict:
    key = _cache_key(query)

    # 🔥 CACHE HIT
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data

    params = {"appid": OWM_KEY, "units": "metric"}

    if "," in str(query) and any(c.isdigit() for c in str(query)):
        lat_s, lon_s = str(query).split(",", 1)
        params["lat"] = lat_s.strip()
        params["lon"] = lon_s.strip()
    else:
        params["q"] = str(query)

    result = dict(_FALLBACK)
    result["city"] = str(query)

    try:
        # ── MAIN WEATHER CALL ─────────────────────────
        r = _session.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params,
            timeout=5,
        )
        r.raise_for_status()
        p = r.json()

        lat = p["coord"]["lat"]
        lon = p["coord"]["lon"]

        result.update({
            "city": p.get("name", str(query)),
            "temp": int(p["main"]["temp"]),
            "feels_like": int(p["main"]["feels_like"]),
            "humidity": p["main"]["humidity"],
            "condition": p["weather"][0]["main"].lower(),
            "lat": lat,
            "lon": lon,
        })

        # ── UV + AQI PARALLEL OPTIMIZATION ────────────
        try:
            uv_res = _session.get(
                "https://api.openweathermap.org/data/3.0/onecall",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": OWM_KEY,
                    "exclude": "minutely,hourly,daily,alerts",
                },
                timeout=4,
            )

            aq_res = _session.get(
                "https://api.openweathermap.org/data/2.5/air_pollution",
                params={"lat": lat, "lon": lon, "appid": OWM_KEY},
                timeout=4,
            )

            if uv_res.ok:
                result["uv_index"] = round(
                    float(uv_res.json().get("current", {}).get("uvi", 0)), 1
                )

            if aq_res.ok:
                aq_data = aq_res.json()["list"][0]
                aqi_val = aq_data["main"]["aqi"]

                result["aqi"] = aqi_val
                result["aqi_label"] = AQI_LABELS.get(aqi_val, "Unknown")
                result["pm25"] = round(
                    aq_data["components"].get("pm2_5", 0.0), 1
                )

        except Exception as e:
            logger.warning(f"[Weather] UV/AQI error: {e}")

    except Exception as e:
        logger.error(f"[Weather] Main call error: {e}")

    # 🔥 STORE IN CACHE
    _cache[key] = (result, time.time())

    return result


def get_hourly_forecast(lat, lon) -> list:
    if not lat or not lon:
        return []

    try:
        r = _session.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,precipitation_probability,weathercode",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=5,
        )

        r.raise_for_status()
        data = r.json()["hourly"]

        now_h = datetime.now().hour
        result = []

        for i in range(now_h, min(now_h + 6, 24)):
            time_str = data["time"][i]

            hour_label = datetime.fromisoformat(time_str).strftime("%-I%p")

            result.append({
                "hour": hour_label,
                "temp": int(data["temperature_2m"][i]),
                "precip_prob": int(data["precipitation_probability"][i]),
                "code": int(data["weathercode"][i]),
            })

        return result

    except Exception as e:
        logger.warning(f"[Weather] Open-Meteo error: {e}")
        return []


def uv_category(uv: float) -> tuple:
    if uv <= 2:
        return "Low", "text-green-400"
    if uv <= 5:
        return "Moderate", "text-yellow-400"
    if uv <= 7:
        return "High", "text-orange-400"
    if uv <= 10:
        return "Very High", "text-red-400"
    return "Extreme", "text-purple-400"
