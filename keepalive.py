# hf_space/keepalive.py
# Runs as a background thread inside the Render process.
# Sends an authenticated GET /ping to the private HuggingFace Space 
# every 20 minutes to prevent the Space from going to sleep.

import os
import threading
import time
import requests

# Configuration from Environment Variables
HF_SPACE_URL    = os.getenv("HF_SPACE_URL", "").rstrip("/")
HF_TOKEN        = os.getenv("HF_TOKEN")  # Your hf_... access token
PING_INTERVAL_S = 20 * 60                # 20 minutes
PING_TIMEOUT_S  = 15

_started        = False
_lock           = threading.Lock()

def _ping_loop():
    """Background loop that executes the ping."""
    while True:
        # Wait at the start of the loop
        time.sleep(PING_INTERVAL_S)
        
        if not HF_SPACE_URL:
            print("[Keepalive] Error: HF_SPACE_URL is empty. Skipping ping.")
            continue

        try:
            # Prepare Authorization header for Private Repo access
            headers = {}
            if HF_TOKEN:
                headers["Authorization"] = f"Bearer {HF_TOKEN}"
            else:
                print("[Keepalive] Warning: HF_TOKEN not set. Pings to private spaces may fail.")

            # Execute the ping
            response = requests.get(
                f"{HF_SPACE_URL}/ping", 
                headers=headers, 
                timeout=PING_TIMEOUT_S
            )
            
            # Log the result
            if response.status_code == 200:
                print(f"[Keepalive] Success: HF Space is awake → {response.json()}")
            else:
                print(f"[Keepalive] Warning: HF ping returned {response.status_code}. Space might be private or offline.")

        except Exception as e:
            print(f"[Keepalive] Critical: HF ping failed due to network/error: {e}")

def start_keepalive():
    """
    Initializes the keepalive thread. 
    Call this once in your main app.py startup.
    """
    global _started
    with _lock:
        if _started:
            return
        
        if not HF_SPACE_URL:
            print("[Keepalive] HF_SPACE_URL not set — Keepalive disabled.")
            return

        # Create a daemon thread so it closes when the main app closes
        t = threading.Thread(target=_ping_loop, daemon=True, name="hf-keepalive")
        t.start()
        _started = True
        
        mask_token = f"{HF_TOKEN[:5]}***" if HF_TOKEN else "None"
        print(f"[Keepalive] System Active.")
        print(f"[Keepalive] Target: {HF_SPACE_URL}/ping")
        print(f"[Keepalive] Auth: Token {mask_token} loaded.")
