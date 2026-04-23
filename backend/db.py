# backend/db.py (PRODUCTION READY)

import os
import requests
import logging
from datetime import datetime
from threading import Lock

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB")

# ── Config ──────────────────────────────────────────────
TURSO_URL = os.getenv("TURSO_URL", "")
if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://", 1)

TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")
_turso_ready = bool(TURSO_URL and TURSO_TOKEN)

# ── Session (IMPORTANT OPTIMIZATION) ─────────────────────
_session = requests.Session()

# ── Fallback memory (thread-safe) ────────────────────────
_mem_users = {}
_mem_detections = []
_mem_audit = []
_lock = Lock()


# ── Core SQL Executor ────────────────────────────────────
def _sql(sql: str, args: list = None, retries: int = 2):
    if not _turso_ready:
        return []

    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [{"type": "text", "value": str(a)} for a in (args or [])],
                },
            },
            {"type": "close"},
        ]
    }

    for attempt in range(retries):
        try:
            resp = _session.post(
                f"{TURSO_URL}/v2/pipeline",
                headers={
                    "Authorization": f"Bearer {TURSO_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=5,  # 🔥 reduced timeout (important)
            )

            resp.raise_for_status()
            results = resp.json().get("results", [])

            if not results or results[0].get("type") != "ok":
                return []

            result = results[0].get("response", {}).get("result", {})
            cols = [c["name"] for c in result.get("cols", [])]
            rows = result.get("rows", [])

            return [dict(zip(cols, [v.get("value") for v in row])) for row in rows]

        except requests.exceptions.RequestException as e:
            logger.warning(f"[DB] Attempt {attempt+1} failed: {e}")

    logger.error("[DB] All retries failed")
    return []


# ── Init ─────────────────────────────────────────────────
def init_db():
    tables = [
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

    for sql in tables:
        try:
            _sql(sql)
        except Exception as e:
            logger.error(f"[DB] init error: {e}")


# ── Writes ───────────────────────────────────────────────
def add_user_to_db(name: str, notes: str = "Mobile Registration"):
    now = datetime.now().strftime("%Y-%m-%d")

    if _turso_ready:
        _sql(
            "INSERT OR IGNORE INTO registered_users "
            "(name, registered_on, notes, detection_count) VALUES (?,?,?,0)",
            [name, now, notes],
        )
    else:
        with _lock:
            if name not in _mem_users:
                _mem_users[name] = {
                    "name": name,
                    "registered_on": now,
                    "notes": notes,
                    "detection_count": 0,
                }


def delete_user_from_db(name: str):
    if _turso_ready:
        _sql("DELETE FROM registered_users WHERE name = ?", [name])
        _sql("DELETE FROM detection_log WHERE name = ?", [name])
    else:
        with _lock:
            _mem_users.pop(name, None)
            global _mem_detections
            _mem_detections = [d for d in _mem_detections if d["name"] != name]


def log_detection(name: str, mask: str, glasses: str, weather: dict):
    row = {
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "mask": mask,
        "glasses": glasses,
        "city": weather.get("city", ""),
        "temp": weather.get("temp", 0),
        "feels_like": weather.get("feels_like", 0),
        "aqi": weather.get("aqi", 0),
        "aqi_label": weather.get("aqi_label", ""),
        "uv_index": weather.get("uv_index", 0),
    }

    if _turso_ready:
        _sql(
            "INSERT INTO detection_log "
            "(name,timestamp,mask,glasses,city,temp,feels_like,aqi,aqi_label,uv_index) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            list(row.values()),
        )

        _sql(
            "UPDATE registered_users SET detection_count = detection_count + 1 WHERE name = ?",
            [name],
        )
    else:
        with _lock:
            _mem_detections.insert(0, row)
            if name in _mem_users:
                _mem_users[name]["detection_count"] += 1


def log_audit(event: str, detail: str, ip: str):
    row = {
        "event": event,
        "detail": detail,
        "ip": ip or "unknown",
        "timestamp": datetime.now().isoformat(),
    }

    if _turso_ready:
        _sql(
            "INSERT INTO audit_log (event,detail,ip,timestamp) VALUES (?,?,?,?)",
            list(row.values()),
        )
    else:
        with _lock:
            _mem_audit.insert(0, row)


# ── Reads ────────────────────────────────────────────────
def get_all_users():
    if _turso_ready:
        return _sql("SELECT * FROM registered_users ORDER BY registered_on DESC")

    with _lock:
        return list(_mem_users.values())


def get_detection_history(name: str = None, limit: int = 100):
    if _turso_ready:
        if name:
            return _sql(
                "SELECT * FROM detection_log WHERE name=? ORDER BY timestamp DESC LIMIT ?",
                [name, limit],
            )
        return _sql(
            "SELECT * FROM detection_log ORDER BY timestamp DESC LIMIT ?",
            [limit],
        )

    with _lock:
        rows = [d for d in _mem_detections if not name or d["name"] == name]
        return rows[:limit]


def get_audit_log(limit: int = 100):
    if _turso_ready:
        return _sql(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", [limit]
        )

    with _lock:
        return _mem_audit[:limit]
