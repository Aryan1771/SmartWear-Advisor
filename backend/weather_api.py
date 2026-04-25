import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger("smartwear.weather")

OWM_KEY = os.getenv("OWM_API_KEY", "")

AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
WEATHER_CODES = {
    0: "Clear",
    1: "Mostly Clear",
    2: "Partly Cloudy",
    3: "Cloudy",
    45: "Foggy",
    48: "Rime Fog",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Heavy Drizzle",
    56: "Freezing Drizzle",
    57: "Heavy Freezing Drizzle",
    61: "Light Rain",
    63: "Rain",
    65: "Heavy Rain",
    66: "Freezing Rain",
    67: "Heavy Freezing Rain",
    71: "Light Snow",
    73: "Snow",
    75: "Heavy Snow",
    77: "Snow Grains",
    80: "Rain Showers",
    81: "Rain Showers",
    82: "Heavy Showers",
    85: "Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm With Hail",
    99: "Severe Thunderstorm",
}

_session = requests.Session()
_cache = {}
CACHE_TTL = 300

_FALLBACK_CURRENT = {
    "city": "Unknown",
    "temp": 25,
    "feels_like": 25,
    "humidity": 50,
    "condition": "clear",
    "description": "Unavailable",
    "uv_index": None,
    "aqi": 1,
    "aqi_label": "Good",
    "pm25": 0.0,
    "lat": None,
    "lon": None,
}


def _round_coord(value):
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _cache_key(lat=None, lon=None, query=None):
    rounded_lat = _round_coord(lat)
    rounded_lon = _round_coord(lon)
    if rounded_lat is not None and rounded_lon is not None:
        return f"coords:{rounded_lat}:{rounded_lon}"
    return f"query:{str(query or '').strip().lower()}"


def _get_cached(key):
    cached = _cache.get(key)
    if not cached:
        return None
    payload, timestamp = cached
    if time.time() - timestamp < CACHE_TTL:
        return payload
    _cache.pop(key, None)
    return None


def _set_cached(key, payload):
    _cache[key] = (payload, time.time())


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _weather_description(code):
    return WEATHER_CODES.get(int(code), "Unavailable")


def _get_open_meteo_uv(lat, lon):
    if _round_coord(lat) is None or _round_coord(lon) is None:
        return None

    last_error = None
    for _ in range(2):
        try:
            response = _session.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": _round_coord(lat),
                    "longitude": _round_coord(lon),
                    "current": "uv_index",
                    "timezone": "auto",
                },
                timeout=4,
            )
            response.raise_for_status()
            value = response.json().get("current", {}).get("uv_index")
            return round(float(value), 1) if value is not None else None
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    logger.warning(
        "Open-Meteo UV fallback failed for lat=%s lon=%s: %s",
        _round_coord(lat),
        _round_coord(lon),
        last_error,
    )
    return None


def _estimate_uv_index(lat, lon):
    rounded_lat = _round_coord(lat)
    rounded_lon = _round_coord(lon)
    if rounded_lat is None or rounded_lon is None:
        return None

    local_time = datetime.now(timezone.utc) + timedelta(hours=rounded_lon / 15)
    hour = local_time.hour + local_time.minute / 60
    if hour < 6 or hour > 18:
        return 0.0

    daylight_position = math.sin(math.pi * (hour - 6) / 12)
    latitude_factor = max(0.45, 1 - abs(rounded_lat) / 90)
    seasonal_factor = 0.75
    estimate = 8.5 * daylight_position * latitude_factor * seasonal_factor
    return round(max(0.0, min(11.0, estimate)), 1)


def _has_coords(lat, lon):
    return _round_coord(lat) is not None and _round_coord(lon) is not None


def get_weather(lat=None, lon=None, query=None) -> dict:
    cache_key = _cache_key(lat=lat, lon=lon, query=query)
    cached = _get_cached(cache_key)
    if cached:
        return dict(cached)

    result = dict(_FALLBACK_CURRENT)
    params = {"appid": OWM_KEY, "units": "metric"}

    if _has_coords(lat, lon):
        params["lat"] = _round_coord(lat)
        params["lon"] = _round_coord(lon)
    elif query:
        params["q"] = str(query).strip()
        result["city"] = str(query).strip()
    else:
        _set_cached(cache_key, result)
        return result

    if not OWM_KEY:
        logger.warning("OWM_API_KEY is not configured; returning fallback weather data.")
        fallback_uv = _get_open_meteo_uv(lat, lon)
        if fallback_uv is not None:
            result["uv_index"] = fallback_uv
        elif _estimate_uv_index(lat, lon) is not None:
            result["uv_index"] = _estimate_uv_index(lat, lon)
        _set_cached(cache_key, result)
        return result

    try:
        weather_response = _session.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params,
            timeout=5,
        )
        weather_response.raise_for_status()
        weather_payload = weather_response.json()

        lat = weather_payload["coord"]["lat"]
        lon = weather_payload["coord"]["lon"]
        main = weather_payload.get("main", {})
        condition = (weather_payload.get("weather") or [{}])[0]

        result.update(
            {
                "city": weather_payload.get("name", result["city"]),
                "temp": int(round(main.get("temp", result["temp"]))),
                "feels_like": int(round(main.get("feels_like", result["feels_like"]))),
                "humidity": int(main.get("humidity", result["humidity"])),
                "condition": str(condition.get("main", result["condition"])).lower(),
                "description": str(condition.get("description", "")).title() or result["description"],
                "lat": lat,
                "lon": lon,
            }
        )

        uv_response = _session.get(
            "https://api.openweathermap.org/data/3.0/onecall",
            params={
                "lat": lat,
                "lon": lon,
                "appid": OWM_KEY,
                "exclude": "minutely,hourly,daily,alerts",
            },
            timeout=4,
        )
        if uv_response.ok:
            uvi = uv_response.json().get("current", {}).get("uvi")
            if uvi is not None:
                result["uv_index"] = round(float(uvi), 1)

        if result.get("uv_index") is None:
            fallback_uv = _get_open_meteo_uv(lat, lon)
            if fallback_uv is not None:
                result["uv_index"] = fallback_uv

        if result.get("uv_index") is None:
            estimated_uv = _estimate_uv_index(lat, lon)
            if estimated_uv is not None:
                result["uv_index"] = estimated_uv

        aqi_response = _session.get(
            "https://api.openweathermap.org/data/2.5/air_pollution",
            params={"lat": lat, "lon": lon, "appid": OWM_KEY},
            timeout=4,
        )
        if aqi_response.ok:
            aqi_payload = (aqi_response.json().get("list") or [{}])[0]
            aqi_value = int(aqi_payload.get("main", {}).get("aqi", result["aqi"]))
            result["aqi"] = aqi_value
            result["aqi_label"] = AQI_LABELS.get(aqi_value, "Unknown")
            result["pm25"] = round(
                float(aqi_payload.get("components", {}).get("pm2_5", 0.0)), 1
            )
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)

    _set_cached(cache_key, result)
    return dict(result)


def get_six_day_forecast(lat, lon) -> list:
    if _round_coord(lat) is None or _round_coord(lon) is None:
        logger.warning(
            "Forecast unavailable because coordinates are missing or invalid. lat=%s lon=%s",
            lat,
            lon,
        )
        return []

    cache_key = f"forecast:{_round_coord(lat)}:{_round_coord(lon)}"
    cached = _get_cached(cache_key)
    if cached:
        return list(cached)

    try:
        response = _session.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": _round_coord(lat),
                "longitude": _round_coord(lon),
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_probability_max",
                "forecast_days": 6,
                "timezone": "auto",
            },
            timeout=5,
        )
        response.raise_for_status()
        daily = response.json().get("daily", {})

        forecast = []
        for idx, date_text in enumerate(daily.get("time", [])):
            parsed_date = datetime.fromisoformat(date_text)
            forecast.append(
                {
                    "date": date_text,
                    "label": parsed_date.strftime("%a"),
                    "full_label": parsed_date.strftime("%d %b"),
                    "condition": _weather_description(daily.get("weathercode", [0])[idx]),
                    "temp_max": int(round(daily.get("temperature_2m_max", [0])[idx])),
                    "temp_min": int(round(daily.get("temperature_2m_min", [0])[idx])),
                    "uv_max": round(float(daily.get("uv_index_max", [0])[idx]), 1),
                    "precip_probability": int(
                        round(daily.get("precipitation_probability_max", [0])[idx])
                    ),
                }
            )

        _set_cached(cache_key, forecast)
        return forecast
    except Exception as exc:
        logger.warning(
            "Forecast fetch failed for lat=%s lon=%s: %s",
            _round_coord(lat),
            _round_coord(lon),
            exc,
        )
        return []


def get_weather_bundle(lat=None, lon=None, query=None) -> dict:
    current = get_weather(lat=lat, lon=lon, query=query)
    resolved_lat = current.get("lat", lat)
    resolved_lon = current.get("lon", lon)
    forecast = get_six_day_forecast(resolved_lat, resolved_lon)

    return {
        "current": current,
        "forecast": forecast,
        "location": {
            "city": current.get("city", "Unknown"),
            "lat": resolved_lat,
            "lon": resolved_lon,
        },
    }
