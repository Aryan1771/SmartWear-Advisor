# SmartWear Advisor

SmartWear Advisor is a Flask web app that captures a face, sends lightweight frames to a Hugging Face inference endpoint, detects mask and glasses usage, and combines that result with weather data to present safer accessory recommendations.

## What is in this repo

- Render-hosted Flask frontend and admin dashboard
- Weather integration using OpenWeatherMap and Open-Meteo
- Turso-backed registration, detection history, and audit logs
- PWA-ready mobile frontend with camera capture flow

## Core behavior

- Recognition requests are throttled to reduce Render memory pressure.
- If a face is not recognized within the live scan window, inference stops and remains paused until `Register` is used.
- Registration is a one-shot capture flow with payload size checks.
- Admin can export CSV files, clear logs with password confirmation, and keep long-term analytics through 30-day rollups.

## Important environment variables

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `HF_API_URL` or `HF_SPACE_URL` set to the Hugging Face Space base URL
- `HF_API_TOKEN` or `HF_TOKEN`
- `OWM_API_KEY`
- `TURSO_URL`
- `TURSO_TOKEN`

## Local run

```bash
pip install -r requirements.txt
python mainweb.py
```

Production entrypoint:

```bash
gunicorn mainweb:app --workers 2 --timeout 120
```
