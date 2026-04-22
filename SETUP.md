# SmartWear Advisor — Complete Setup & Deployment Guide

## Overview

| Part | Platform | What runs there |
|------|----------|-----------------|
| Flask web app | Render.com | UI, routing, weather, admin |
| ML inference | HuggingFace Space | face_recognition, TFLite models |
| Database | Turso | Logs, audit, user records |

---

## Step 0 — Prerequisites

```bash
python --version          # 3.11+
pip install -r requirements.txt
# Generate PWA icons (once)
cd web_app/static && python generate_icons.py && cd ../..
```

---

## Step 1 — Train models locally

```bash
# Put images in data/raw/with_mask/, data/raw/without_mask/,
# data/raw/with_glasses/, data/raw/without_glasses/
python ai_model/train_model.py
# → creates models/*.tflite, models/*.keras, models/*_labels.txt

# Test locally
python ai_model/detect_accessories.py
```

---

## Step 2 — Turso (persistent database)

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth login
turso db create smartwear
turso db show smartwear --url          # copy this → TURSO_URL
turso db tokens create smartwear       # copy this → TURSO_TOKEN
```

---

## Step 3 — HuggingFace Space

1. huggingface.co → New Space → SDK: **Docker** → Visibility: **Public**
2. Upload the entire `hf_space/` folder contents to the Space repo
3. Upload `models/*.tflite` and `models/*_labels.txt` to `models/`
4. Space builds in ~5-10 min. URL: `https://USERNAME-smartwear.hf.space`
5. Test: `curl https://USERNAME-smartwear.hf.space/ping`

---

## Step 4 — Render (Flask app)

1. Push project to GitHub (.gitignore keeps .env and models out)
2. render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn mainweb:app --workers 2 --timeout 120`
5. Add environment variables:

```
SECRET_KEY       = (python -c "import secrets; print(secrets.token_hex(32))")
ADMIN_PASSWORD   = your-admin-password
HF_SPACE_URL     = https://USERNAME-smartwear.hf.space
OWM_API_KEY      = your-openweathermap-key
TURSO_URL        = libsql://smartwear-USERNAME.turso.io
TURSO_TOKEN      = your-turso-token
```

---

## Step 5 — Local development

```bash
cp .env.example .env    # fill in your values
python mainweb.py       # http://localhost:5000

# Run HF Space locally (optional)
cd hf_space && uvicorn app:app --reload --port 8000
# Set HF_SPACE_URL=http://localhost:8000 in .env
```

---

## Step 6 — PWA install

- **Android/Chrome:** Three-dot menu → Add to Home Screen  
- **iOS/Safari:** Share → Add to Home Screen  
- Or tap the "📲 Install App" button in the top bar

---

## Admin

- Login: `/admin/login`  
- Session timeout: 30 minutes (warning at 25 min)  
- Features: registered users, detection history, audit log, CSV export, delete users

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Inference server unavailable" | HF Space cold-starting (~30s). Wait and retry. |
| Registration fails | Check lighting. Blink liveness needs MediaPipe CDN. |
| No bounding box | `box: null` means no face detected — expected. |
| Yellow box | Unknown face. Green box = registered face. |
| Session expired | Sessions last 30 min. Dashboard heartbeat extends it. |
| No Turso configured | App auto-falls back to in-memory storage for local dev. |
