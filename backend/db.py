# backend/db.py
import os
import requests
from datetime import datetime

TURSO_URL   = os.getenv("TURSO_URL", "")
if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://", 1)
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")

# ── In-memory fallback for local dev ────────────────────────────
_mem_users     = {}
_mem_detections = []
_mem_audit      = []
_turso_ready    = bool(TURSO_URL and TURSO_TOKEN)


def _sql(sql: str, args: list = None):
    """Execute a SQL statement against Turso and return rows as dicts."""
    if not _turso_ready:
        return []
    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [
                        {"type": "text", "value": str(a)} for a in (args or [])
                    ],
                },
            },
            {"type": "close"},
        ]
    }
    resp = requests.post(
        f"{TURSO_URL}/v2/pipeline",
        headers={
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results or results[0].get("type") != "ok":
        return []
    result = results[0].get("response", {}).get("result", {})
    cols = [c["name"] for c in result.get("cols", [])]
    rows = result.get("rows", [])
    return [dict(zip(cols, [v.get("value") for v in row])) for row in rows]


# ── Table initialisation ─────────────────────────────────────────

def init_db():
    tables = [
        """CREATE TABLE IF NOT EXISTS registered_users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    UNIQUE NOT NULL,
            registered_on   TEXT,
            notes           TEXT,
            detection_count INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS detection_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            timestamp   TEXT,
            mask        TEXT,
            glasses     TEXT,
            city        TEXT,
            temp        INTEGER,
            feels_like  INTEGER,
            aqi         INTEGER,
            aqi_label   TEXT,
            uv_index    REAL
        )""",
        """CREATE TABLE IF NOT EXISTS audit_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            event     TEXT,
            detail    TEXT,
            ip        TEXT,
            timestamp TEXT
        )""",
    ]
    for sql in tables:
        try:
            _sql(sql)
        except Exception as e:
            print(f"[DB] init error: {e}")


# ── Write helpers ────────────────────────────────────────────────

def add_user_to_db(name: str, notes: str = "Mobile Registration"):
    now = datetime.now().strftime("%Y-%m-%d")
    if _turso_ready:
        try:
            _sql(
                "INSERT OR IGNORE INTO registered_users "
                "(name, registered_on, notes, detection_count) VALUES (?,?,?,0)",
                [name, now, notes],
            )
        except Exception as e:
            print(f"[DB] add_user error: {e}")
    else:
        if name not in _mem_users:
            _mem_users[name] = {
                "name": name,
                "registered_on": now,
                "notes": notes,
                "detection_count": 0,
            }


def delete_user_from_db(name: str):
    if _turso_ready:
        try:
            _sql("DELETE FROM registered_users WHERE name = ?", [name])
            _sql("DELETE FROM detection_log    WHERE name = ?", [name])
        except Exception as e:
            print(f"[DB] delete_user error: {e}")
    else:
        _mem_users.pop(name, None)
        global _mem_detections
        _mem_detections = [d for d in _mem_detections if d["name"] != name]


def log_detection(name: str, mask: str, glasses: str, weather: dict):
    row = {
        "name":       name,
        "timestamp":  datetime.now().isoformat(),
        "mask":       mask,
        "glasses":    glasses,
        "city":       weather.get("city", ""),
        "temp":       weather.get("temp", 0),
        "feels_like": weather.get("feels_like", 0),
        "aqi":        weather.get("aqi", 0),
        "aqi_label":  weather.get("aqi_label", ""),
        "uv_index":   weather.get("uv_index", 0),
    }
    if _turso_ready:
        try:
            _sql(
                "INSERT INTO detection_log "
                "(name,timestamp,mask,glasses,city,temp,feels_like,aqi,aqi_label,uv_index) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [row[k] for k in
                 ("name","timestamp","mask","glasses","city","temp",
                  "feels_like","aqi","aqi_label","uv_index")],
            )
            _sql(
                "UPDATE registered_users SET detection_count = detection_count + 1 "
                "WHERE name = ?",
                [name],
            )
        except Exception as e:
            print(f"[DB] log_detection error: {e}")
    else:
        _mem_detections.insert(0, row)
        if name in _mem_users:
            _mem_users[name]["detection_count"] = (
                _mem_users[name].get("detection_count", 0) + 1
            )


def log_audit(event: str, detail: str, ip: str):
    row = {
        "event":     event,
        "detail":    detail,
        "ip":        ip or "unknown",
        "timestamp": datetime.now().isoformat(),
    }
    if _turso_ready:
        try:
            _sql(
                "INSERT INTO audit_log (event,detail,ip,timestamp) VALUES (?,?,?,?)",
                [row["event"], row["detail"], row["ip"], row["timestamp"]],
            )
        except Exception as e:
            print(f"[DB] log_audit error: {e}")
    else:
        _mem_audit.insert(0, row)


# ── Read helpers ─────────────────────────────────────────────────

def get_all_users():
    if _turso_ready:
        try:
            return _sql("SELECT * FROM registered_users ORDER BY registered_on DESC")
        except Exception as e:
            print(f"[DB] get_all_users error: {e}")
            return []
    return list(_mem_users.values())


def get_detection_history(name: str = None, limit: int = 100):
    if _turso_ready:
        try:
            if name:
                return _sql(
                    "SELECT * FROM detection_log WHERE name=? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    [name, limit],
                )
            return _sql(
                "SELECT * FROM detection_log ORDER BY timestamp DESC LIMIT ?",
                [limit],
            )
        except Exception as e:
            print(f"[DB] get_detection_history error: {e}")
            return []
    rows = [d for d in _mem_detections if not name or d["name"] == name]
    return rows[:limit]


def get_audit_log(limit: int = 100):
    if _turso_ready:
        try:
            return _sql(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", [limit]
            )
        except Exception as e:
            print(f"[DB] get_audit_log error: {e}")
            return []
    return _mem_audit[:limit]
