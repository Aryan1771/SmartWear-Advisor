import os
import requests


def get_weather(city):
    # Read API key from environment. Set OPENWEATHER_API_KEY in your Render/host settings.
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not api_key:
        return {
            "city": city,
            "temp": 25,
            "humidity": 50,
            "condition": "clear"
        }
    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": api_key, "units": "metric"},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "city": payload.get("name", city),
            "temp": payload.get("main", {}).get("temp", 25),
            "humidity": payload.get("main", {}).get("humidity", 50),
            "condition": payload.get("weather", [{}])[0].get("main", "clear").lower(),
        }
    except Exception:
        return {
            "city": city,
            "temp": 25,
            "humidity": 50,
            "condition": "clear"
        }