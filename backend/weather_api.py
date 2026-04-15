import os
import requests
def get_weather(city):
    api_key = os.getenv("48011be42f7f029c2a46a46a2df97124", "").strip()
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY is not set.")
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": api_key, "units": "metric"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    weather_items = payload.get("weather", [])
    main_data = payload.get("main", {})
    return {
        "city": payload.get("name", city),
        "temp": main_data.get("temp", 25),
        "humidity": main_data.get("humidity", 50),
        "condition": weather_items[0].get("main", "clear").lower() if weather_items else "clear",
    }