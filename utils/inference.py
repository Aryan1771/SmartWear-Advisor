# ===================== inference.py =====================

import os
import requests

# 🔗 Your HF endpoint (SET THIS IN RENDER ENV)
HF_API_URL = os.environ.get("HF_API_URL")

# Optional token (if private space)
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {}
if HF_API_TOKEN:
    HEADERS["Authorization"] = f"Bearer {HF_API_TOKEN}"


# ─────────────────────────────────────────────
# MAIN INFERENCE FUNCTION
# ─────────────────────────────────────────────
def run_inference(image_base64):
    """
    Sends frame to HF Space and returns result
    """

    if not HF_API_URL:
        print("❌ HF_API_URL not set")
        return fallback()

    try:
        payload = {
            "image": image_base64  # already base64 from frontend
        }

        res = requests.post(
            HF_API_URL,
            json=payload,
            headers=HEADERS,
            timeout=5  # IMPORTANT (prevents freeze)
        )

        if res.status_code != 200:
            print("❌ HF Error:", res.text)
            return fallback()

        data = res.json()

        return normalize_response(data)

    except Exception as e:
        print("❌ HF Request Failed:", e)
        return fallback()


# ─────────────────────────────────────────────
# NORMALIZE RESPONSE
# ─────────────────────────────────────────────
def normalize_response(data):
    """
    Convert HF response → your app format
    """

    return {
        "name": data.get("name", "Unknown"),
        "mask": data.get("mask", "No Mask"),
        "glasses": data.get("glasses", "No Glasses"),
        "box": data.get("box", None)
    }


# ─────────────────────────────────────────────
# FALLBACK (NO CRASH)
# ─────────────────────────────────────────────
def fallback():
    return {
        "name": "Unknown",
        "mask": "No Mask",
        "glasses": "No Glasses",
        "box": None
    }
