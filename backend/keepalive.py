import logging
import os
import threading
import time

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KEEPALIVE")

HF_SPACE_URL = os.getenv("HF_SPACE_URL", os.getenv("HF_API_URL", "")).rstrip("/")
RENDER_URL = os.getenv("RENDER_URL", "").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HF_API_TOKEN", ""))

KEEPALIVE_ENABLED = os.getenv("ENABLE_KEEPALIVE", "true").lower() in {"1", "true", "yes", "on"}
HF_PING_INTERVAL = int(os.getenv("HF_PING_INTERVAL_SECONDS", str(12 * 60)))
RENDER_PING_INTERVAL = int(os.getenv("RENDER_PING_INTERVAL_SECONDS", str(12 * 60)))
PING_TIMEOUT = int(os.getenv("KEEPALIVE_TIMEOUT_SECONDS", "10"))

_session = requests.Session()
_started = False
_lock = threading.Lock()


def _safe_ping(url, headers=None, name="Service"):
    try:
        response = _session.get(url, headers=headers or {}, timeout=PING_TIMEOUT)
        logger.info("[Keepalive] %s ping -> %s", name, response.status_code)
    except Exception as exc:
        logger.warning("[Keepalive] %s ping failed: %s", name, exc)


def _loop(url, interval, name, headers=None):
    while True:
        _safe_ping(url, headers=headers, name=name)
        time.sleep(interval)


def start_keepalive(ping_hf=True, ping_render=False):
    global _started

    if not KEEPALIVE_ENABLED:
        logger.info("[Keepalive] disabled by ENABLE_KEEPALIVE")
        return

    with _lock:
        if _started:
            return
        _started = True

        if ping_hf and HF_SPACE_URL:
            headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
            threading.Thread(
                target=_loop,
                args=(f"{HF_SPACE_URL}/ping", HF_PING_INTERVAL, "HF", headers),
                daemon=True,
                name="keepalive-hf",
            ).start()
            logger.info("[Keepalive] Render -> HF active every %ss", HF_PING_INTERVAL)

        if ping_render and RENDER_URL:
            threading.Thread(
                target=_loop,
                args=(f"{RENDER_URL}/ping", RENDER_PING_INTERVAL, "Render", None),
                daemon=True,
                name="keepalive-render",
            ).start()
            logger.info("[Keepalive] Service -> Render active every %ss", RENDER_PING_INTERVAL)
