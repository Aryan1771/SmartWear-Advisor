# mainweb.py - Entry point for SmartWear Advisor
# Run locally: python mainweb.py
# Run on Render: gunicorn mainweb:app

from backend.keepalive import start_keepalive
from web_app.app import app

start_keepalive(ping_hf=True, ping_render=False)

if __name__ == "__main__":
    app.run(debug=True)
