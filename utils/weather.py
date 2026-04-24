# ===================== weather.py =====================

import requests

API_KEY = "YOUR_OPENWEATHER_KEY"


def get_weather(lat, lon):
    if not lat or not lon:
        return {}

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        r = requests.get(url).json()

        return {
            "city": r.get("name"),
            "temp": r["main"]["temp"],
            "humidity": r["main"]["humidity"],
            "uv": 5,
            "aqi_label": "Moderate"
        }

    except:
        return {}
