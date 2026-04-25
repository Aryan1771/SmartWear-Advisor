import os
from urllib.parse import quote
from urllib.parse import urlsplit, urlunsplit

import requests

HF_API_URL = os.environ.get("HF_API_URL") or os.environ.get("HF_SPACE_URL")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN") or os.environ.get("HF_TOKEN")

HEADERS = {}
if HF_API_TOKEN:
    HEADERS["Authorization"] = f"Bearer {HF_API_TOKEN}"

_session = requests.Session()
_KNOWN_ENDPOINTS = {"detect", "register", "registered", "ping"}


def _base_space_url():
    if not HF_API_URL:
        return None

    parsed = urlsplit(HF_API_URL.strip())
    path = parsed.path.rstrip("/")
    segments = [segment for segment in path.split("/") if segment]

    if segments and segments[-1] in _KNOWN_ENDPOINTS:
        path = "/" + "/".join(segments[:-1]) if len(segments) > 1 else ""

    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _endpoint_url(endpoint_name):
    base = _base_space_url()
    if not base:
        return None
    return f"{base}/{endpoint_name.lstrip('/')}"


def _parse_json(response):
    try:
        return response.json()
    except ValueError:
        return {}


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
    endpoint = _endpoint_url("detect")
    if not endpoint:
        return fallback("hf_not_configured")

    try:
        response = _session.post(
            endpoint,
            json={"image": image_base64},
            headers=HEADERS,
            timeout=5,
        )
        payload = _parse_json(response)
        if response.status_code != 200:
            return fallback(payload.get("message") or f"hf_request_failed_{response.status_code}")
        return normalize_response(payload)
    except Exception:
        return fallback("hf_unreachable")


def register_face(name, image_base64):
    endpoint = _endpoint_url("register")
    if not endpoint:
        return {"success": False, "error": "hf_not_configured", "message": "HF service is not configured."}

    try:
        response = _session.post(
            endpoint,
            json={"name": name, "image": image_base64},
            headers=HEADERS,
            timeout=12,
        )
        payload = _parse_json(response)
        success = bool(payload.get("success"))

        if response.status_code != 200 or not success:
            return {
                "success": False,
                "error": payload.get("error") or f"hf_register_failed_{response.status_code}",
                "message": payload.get("message") or "Face registration failed on the ML service.",
            }

        return {
            "success": True,
            "message": payload.get("message") or "Registered successfully.",
            "name": name,
        }
    except Exception:
        return {"success": False, "error": "hf_unreachable", "message": "HF service is unreachable."}


def delete_face(name):
    endpoint = _endpoint_url(f"user/{quote(str(name or ''), safe='')}")
    if not endpoint:
        return {"success": False, "error": "hf_not_configured"}

    try:
        response = _session.delete(endpoint, headers=HEADERS, timeout=8)
        payload = _parse_json(response)
        if response.status_code != 200:
            return {
                "success": False,
                "error": payload.get("error") or f"hf_delete_failed_{response.status_code}",
            }
        return {"success": bool(payload.get("success")), "name": name}
    except Exception:
        return {"success": False, "error": "hf_unreachable"}
