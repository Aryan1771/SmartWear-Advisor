import os

import requests

HF_API_URL = os.environ.get("HF_API_URL") or os.environ.get("HF_SPACE_URL")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN") or os.environ.get("HF_TOKEN")

HEADERS = {}
if HF_API_TOKEN:
    HEADERS["Authorization"] = f"Bearer {HF_API_TOKEN}"

_session = requests.Session()


def fallback(error=None):
    return {
        "recognized": False,
        "name": "Unknown",
        "mask": "No Mask",
        "glasses": "No Glasses",
        "box": None,
        "error": error,
    }


def normalize_response(data):
    name = data.get("name", "Unknown") or "Unknown"
    return {
        "recognized": name != "Unknown",
        "name": name,
        "mask": data.get("mask", "No Mask"),
        "glasses": data.get("glasses", "No Glasses"),
        "box": data.get("box"),
        "error": None,
    }


def run_inference(image_base64):
    if not HF_API_URL:
        return fallback("hf_not_configured")

    try:
        response = _session.post(
            HF_API_URL,
            json={"image": image_base64},
            headers=HEADERS,
            timeout=5,
        )
        if response.status_code != 200:
            return fallback("hf_request_failed")
        return normalize_response(response.json())
    except Exception:
        return fallback("hf_unreachable")
