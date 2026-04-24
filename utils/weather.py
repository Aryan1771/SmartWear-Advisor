# ===================== weather.py =====================

import os
import requests

API_KEY = os.environ.get("OWM_API_KEY")

def get_weather(lat, lon):
    if not lat or not lon or not API_KEY:
        return {}

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        r = requests.get(url, timeout=5).json()

        return {
            "city": r.get("name"),
            "temp": r["main"]["temp"],
            "humidity": r["main"]["humidity"],
            "uv": 5,
            "aqi_label": "Moderate"
        }

    except Exception as e:
        print("Weather error:", e)
        return {}
