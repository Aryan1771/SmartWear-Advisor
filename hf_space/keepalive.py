# hf_space/keepalive.py
# Runs as a background thread inside the Render Flask process.
# Sends a GET /ping to the HuggingFace Space every 20 minutes so the Space
# never goes cold while Render itself is receiving traffic.
#
# Usage (called once from web_app/app.py at startup):
#   from keepalive import start_keepalive
#   start_keepalive()

import os
import threading
import time
import requests

HF_SPACE_URL    = os.getenv("HF_SPACE_URL", "").rstrip("/")
PING_INTERVAL_S = 20 * 60   # 20 minutes
PING_TIMEOUT_S  = 15
_started        = False
_lock           = threading.Lock()


def _ping_loop():
    while True:
        time.sleep(PING_INTERVAL_S)
        if not HF_SPACE_URL:
            continue
        try:
            r = requests.get(f"{HF_SPACE_URL}/ping", timeout=PING_TIMEOUT_S)
            print(f"[Keepalive] HF ping → {r.status_code} {r.json()}")
        except Exception as e:
            print(f"[Keepalive] HF ping failed: {e}")


def start_keepalive():
    """
    Start the keepalive background thread.
    Safe to call multiple times — only one thread is ever created.
    """
    global _started
    with _lock:
        if _started:
            return
        if not HF_SPACE_URL:
            print("[Keepalive] HF_SPACE_URL not set — keepalive disabled.")
            return
        t = threading.Thread(target=_ping_loop, daemon=True, name="hf-keepalive")
        t.start()
        _started = True
        print(f"[Keepalive] Started — pinging {HF_SPACE_URL}/ping every 20 min.")
