# keepalive.py (PRODUCTION READY)

import os
import threading
import time
import requests
import logging

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KEEPALIVE")

# ── Config ──────────────────────────────────────────────
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").rstrip("/")
RENDER_URL   = os.getenv("RENDER_URL", "").rstrip("/")
HF_TOKEN     = os.getenv("HF_TOKEN", "")

HF_PING_INTERVAL     = 20 * 60
RENDER_PING_INTERVAL = 10 * 60
PING_TIMEOUT         = 10  # reduced slightly

# ── Session (IMPORTANT) ─────────────────────────────────
_session = requests.Session()

_started = False
_lock = threading.Lock()


# ── Internal Ping Function ──────────────────────────────
def _safe_ping(url, headers=None, name="Service"):
    try:
        r = _session.get(url, headers=headers or {}, timeout=PING_TIMEOUT)
        logger.info(f"[Keepalive] {name} → {r.status_code}")
    except Exception as e:
        logger.warning(f"[Keepalive] {name} ping failed: {e}")


# ── HF Loop ─────────────────────────────────────────────
def _ping_hf_loop():
    time.sleep(10)  # 🔥 startup delay
    while True:
        time.sleep(HF_PING_INTERVAL)

        if not HF_SPACE_URL:
            continue

        headers = {}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"

        _safe_ping(f"{HF_SPACE_URL}/ping", headers, "HF")


# ── Render Loop ─────────────────────────────────────────
def _ping_render_loop():
    time.sleep(10)
    while True:
        time.sleep(RENDER_PING_INTERVAL)

        if not RENDER_URL:
            continue

        _safe_ping(f"{RENDER_URL}/ping", name="Render")


# ── Public Starter ──────────────────────────────────────
def start_keepalive(ping_hf=True, ping_render=False):
    global _started

    with _lock:
        if _started:
            return
        _started = True

        if ping_hf and HF_SPACE_URL:
            threading.Thread(target=_ping_hf_loop, daemon=True).start()
            logger.info("[Keepalive] Render → HF active")

        if ping_render and RENDER_URL:
            threading.Thread(target=_ping_render_loop, daemon=True).start()
            logger.info("[Keepalive] HF → Render active")
