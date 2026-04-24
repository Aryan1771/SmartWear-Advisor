import os
from datetime import datetime

import requests

TURSO_URL = os.getenv("TURSO_URL", "")
if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://", 1)
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")

_mem_users = {}
_mem_detections = []
_mem_audit = []
_turso_ready = bool(TURSO_URL and TURSO_TOKEN)


def _sql(sql: str, args: list = None):
    if not _turso_ready:
        return []

    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [{"type": "text", "value": str(arg)} for arg in (args or [])],
                },
            },
            {"type": "close"},
        ]
    }
    response = requests.post(
        f"{TURSO_URL}/v2/pipeline",
        headers={
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results or results[0].get("type") != "ok":
        return []

    result = results[0].get("response", {}).get("result", {})
    columns = [column["name"] for column in result.get("cols", [])]
    rows = result.get("rows", [])
    return [dict(zip(columns, [value.get("value") for value in row])) for row in rows]


def init_db():
    statements = [
        """CREATE TABLE IF NOT EXISTS registered_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            registered_on TEXT,
            notes TEXT,
            detection_count INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS detection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            timestamp TEXT,
            mask TEXT,
            glasses TEXT,
            city TEXT,
            temp INTEGER,
            feels_like INTEGER,
            aqi INTEGER,
            aqi_label TEXT,
            uv_index REAL
        )""",
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            detail TEXT,
            ip TEXT,
            timestamp TEXT
        )""",
    ]

    for statement in statements:
        try:
            _sql(statement)
        except Exception as exc:
            print(f"[DB] init error: {exc}")


def add_user_to_db(name: str, notes: str = "Web Registration"):
    now = datetime.now().strftime("%Y-%m-%d")

    if _turso_ready:
        try:
            _sql(
                "INSERT OR IGNORE INTO registered_users (name, registered_on, notes, detection_count) VALUES (?,?,?,0)",
                [name, now, notes],
            )
        except Exception as exc:
            print(f"[DB] add_user error: {exc}")
        return

    if name not in _mem_users:
        _mem_users[name] = {
            "name": name,
            "registered_on": now,
            "notes": notes,
            "detection_count": 0,
        }


def add_user(name, image=None):
    add_user_to_db(name)


def log_detection(name: str, mask: str, glasses: str, weather: dict):
    row = {
        "name": name or "Unknown",
        "timestamp": datetime.now().isoformat(),
        "mask": mask or "Unknown",
        "glasses": glasses or "Unknown",
        "city": weather.get("city", ""),
        "temp": int(weather.get("temp", 0) or 0),
        "feels_like": int(weather.get("feels_like", 0) or 0),
        "aqi": int(weather.get("aqi", 0) or 0),
        "aqi_label": weather.get("aqi_label", ""),
        "uv_index": float(weather.get("uv_index", 0) or 0),
    }

    if _turso_ready:
        try:
            _sql(
                "INSERT INTO detection_log (name,timestamp,mask,glasses,city,temp,feels_like,aqi,aqi_label,uv_index) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    row["name"],
                    row["timestamp"],
                    row["mask"],
                    row["glasses"],
                    row["city"],
                    row["temp"],
                    row["feels_like"],
                    row["aqi"],
                    row["aqi_label"],
                    row["uv_index"],
                ],
            )
            _sql(
                "UPDATE registered_users SET detection_count = detection_count + 1 WHERE name = ?",
                [row["name"]],
            )
        except Exception as exc:
            print(f"[DB] log_detection error: {exc}")
        return

    _mem_detections.insert(0, row)
    if row["name"] in _mem_users:
        _mem_users[row["name"]]["detection_count"] = (
            _mem_users[row["name"]].get("detection_count", 0) + 1
        )


def log_detection_legacy(result):
    log_detection(
        name=result.get("name"),
        mask=result.get("mask"),
        glasses=result.get("glasses"),
        weather=result.get("weather", {}),
    )


def log_audit(event: str, detail: str, ip: str):
    row = {
        "event": event,
        "detail": detail,
        "ip": ip or "unknown",
        "timestamp": datetime.now().isoformat(),
    }

    if _turso_ready:
        try:
            _sql(
                "INSERT INTO audit_log (event,detail,ip,timestamp) VALUES (?,?,?,?)",
                [row["event"], row["detail"], row["ip"], row["timestamp"]],
            )
        except Exception as exc:
            print(f"[DB] log_audit error: {exc}")
        return

    _mem_audit.insert(0, row)


def get_all_users():
    if _turso_ready:
        try:
            return _sql(
                "SELECT * FROM registered_users ORDER BY registered_on DESC, name ASC"
            )
        except Exception as exc:
            print(f"[DB] get_all_users error: {exc}")
            return []
    return list(_mem_users.values())


def get_detection_history(name: str = None, limit: int = 100):
    if _turso_ready:
        try:
            if name:
                return _sql(
                    "SELECT * FROM detection_log WHERE name = ? ORDER BY timestamp DESC LIMIT ?",
                    [name, limit],
                )
            return _sql(
                "SELECT * FROM detection_log ORDER BY timestamp DESC LIMIT ?",
                [limit],
            )
        except Exception as exc:
            print(f"[DB] get_detection_history error: {exc}")
            return []

    rows = [row for row in _mem_detections if not name or row["name"] == name]
    return rows[:limit]


def get_audit_log(limit: int = 100):
    if _turso_ready:
        try:
            return _sql("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", [limit])
        except Exception as exc:
            print(f"[DB] get_audit_log error: {exc}")
            return []
    return _mem_audit[:limit]


def get_users():
    return get_all_users()


def get_history(limit: int = 100):
    return get_detection_history(limit=limit)


def get_dashboard_stats():
    users = get_all_users()
    history = get_detection_history(limit=200)
    audits = get_audit_log(limit=200)

    return {
        "total_users": len(users),
        "total_detections": len(history),
        "recent_activity": history[0]["timestamp"] if history else None,
        "audit_events": len(audits),
    }
