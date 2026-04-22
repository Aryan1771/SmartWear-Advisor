# mainweb.py — Entry point for SmartWear Advisor
# Run locally:  python mainweb.py
# Run on Render: gunicorn mainweb:app

from web_app.app import app

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
