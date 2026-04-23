#Render
#keepalive.py
import os
import threading
import time
import requests

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "").rstrip("/")
RENDER_URL   = os.getenv("RENDER_URL", "").rstrip("/")
HF_TOKEN     = os.getenv("HF_TOKEN", "")

HF_PING_INTERVAL     = 20 * 60
RENDER_PING_INTERVAL = 10 * 60
PING_TIMEOUT         = 15

_started = False
_lock    = threading.Lock()


def _ping_hf_loop():
    while True:
        time.sleep(HF_PING_INTERVAL)
        if not HF_SPACE_URL:
            continue
        try:
            headers = {}
            if HF_TOKEN:
                headers["Authorization"] = "Bearer {}".format(HF_TOKEN)

            r = requests.get(
                "{}/ping".format(HF_SPACE_URL),
                headers=headers,
                timeout=PING_TIMEOUT,
            )
            print("[Keepalive] HF → {}".format(r.status_code))
        except Exception as e:
            print("[Keepalive] HF ping failed: {}".format(e))


def _ping_render_loop():
    while True:
        time.sleep(RENDER_PING_INTERVAL)
        if not RENDER_URL:
            continue
        try:
            r = requests.get(
                "{}/ping".format(RENDER_URL),
                timeout=PING_TIMEOUT,
            )
            print("[Keepalive] Render → {}".format(r.status_code))
        except Exception as e:
            print("[Keepalive] Render ping failed: {}".format(e))


def start_keepalive(ping_hf=True, ping_render=False):
    global _started
    with _lock:
        if _started:
            return
        _started = True

        if ping_hf and HF_SPACE_URL:
            threading.Thread(target=_ping_hf_loop, daemon=True).start()
            print("[Keepalive] Render → HF active")

        if ping_render and RENDER_URL:
            threading.Thread(target=_ping_render_loop, daemon=True).start()
            print("[Keepalive] HF → Render active")
