# backend/weather_api.py
# Fetches current weather, UV index, and AQI from OpenWeatherMap.
# Fetches hourly forecast (6 hours) from Open-Meteo (free, no API key needed).

import os
import requests
from datetime import datetime

OWM_KEY = os.getenv("OWM_API_KEY", "YOUR_OWM_API_KEY")

AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}

_FALLBACK = {
    "city":       "Unknown",
    "temp":       25,
    "feels_like": 25,
    "humidity":   50,
    "condition":  "clear",
    "uv_index":   0.0,
    "aqi":        1,
    "aqi_label":  "Good",
    "pm25":       0.0,
    "lat":        None,
    "lon":        None,
}


def get_weather(query) -> dict:
    """
    query: either "lat,lon" string or a city name string.
    Returns a weather dict including UV index and AQI.
    """
    params = {"appid": OWM_KEY, "units": "metric"}

    if "," in str(query) and any(c.isdigit() for c in str(query)):
        lat_s, lon_s = str(query).split(",", 1)
        params["lat"] = lat_s.strip()
        params["lon"] = lon_s.strip()
    else:
        params["q"] = str(query)

    result = dict(_FALLBACK)
    result["city"] = str(query)

    # ── Current weather ──────────────────────────────────────────
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params, timeout=6,
        )
        r.raise_for_status()
        p = r.json()

        lat = p["coord"]["lat"]
        lon = p["coord"]["lon"]

        result.update({
            "city":       p.get("name", str(query)),
            "temp":       int(p["main"]["temp"]),
            "feels_like": int(p["main"]["feels_like"]),
            "humidity":   p["main"]["humidity"],
            "condition":  p["weather"][0]["main"].lower(),
            "lat":        lat,
            "lon":        lon,
        })

        # ── UV Index ─────────────────────────────────────────────
        try:
            uv = requests.get(
                "https://api.openweathermap.org/data/2.5/uvi",
                params={"lat": lat, "lon": lon, "appid": OWM_KEY},
                timeout=5,
            )
            uv.raise_for_status()
            result["uv_index"] = round(float(uv.json().get("value", 0)), 1)
        except Exception as e:
            print(f"[Weather] UV error: {e}")

        # ── AQI / Air Pollution ───────────────────────────────────
        try:
            aq = requests.get(
                "https://api.openweathermap.org/data/2.5/air_pollution",
                params={"lat": lat, "lon": lon, "appid": OWM_KEY},
                timeout=5,
            )
            aq.raise_for_status()
            aq_data  = aq.json()["list"][0]
            aqi_val  = aq_data["main"]["aqi"]
            result["aqi"]       = aqi_val
            result["aqi_label"] = AQI_LABELS.get(aqi_val, "Unknown")
            result["pm25"]      = round(aq_data["components"].get("pm2_5", 0.0), 1)
        except Exception as e:
            print(f"[Weather] AQI error: {e}")

    except Exception as e:
        print(f"[Weather] Main call error: {e}")

    return result


def get_hourly_forecast(lat, lon) -> list:
    """
    Returns a list of up to 6 hourly forecast dicts from Open-Meteo.
    No API key required.
    Each dict: { hour, temp, precip_prob, code }
    """
    if not lat or not lon:
        return []

    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":  lat,
                "longitude": lon,
                "hourly":    "temperature_2m,precipitation_probability,weathercode",
                "forecast_days": 1,
                "timezone":  "auto",
            },
            timeout=6,
        )
        r.raise_for_status()
        data   = r.json()["hourly"]
        now_h  = datetime.now().hour
        result = []

        for i in range(now_h, min(now_h + 6, 24)):
            time_str   = data["time"][i]
            hour_label = datetime.fromisoformat(time_str).strftime("%-I%p")  # e.g. 3PM
            result.append({
                "hour":        hour_label,
                "temp":        int(data["temperature_2m"][i]),
                "precip_prob": int(data["precipitation_probability"][i]),
                "code":        int(data["weathercode"][i]),
            })
        return result

    except Exception as e:
        print(f"[Weather] Open-Meteo error: {e}")
        return []


def uv_category(uv: float) -> tuple:
    """Returns (label, colour_class) for a UV index value."""
    if uv <= 2:  return "Low",       "text-green-400"
    if uv <= 5:  return "Moderate",  "text-yellow-400"
    if uv <= 7:  return "High",      "text-orange-400"
    if uv <= 10: return "Very High", "text-red-400"
    return "Extreme", "text-purple-400"
