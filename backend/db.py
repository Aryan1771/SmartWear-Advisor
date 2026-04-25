import os
from datetime import datetime, timedelta

import requests

TURSO_URL = os.getenv("TURSO_URL", "")
if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://", 1)
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")

RETENTION_DAYS = 30

_mem_users = {}
_mem_detections = []
_mem_audit = []
_mem_detection_summary = {}
_mem_audit_summary = {}
_turso_ready = bool(TURSO_URL and TURSO_TOKEN)


def _sql(sql: str, args: list = None):
    if not _turso_ready:
        return []

    def _arg(value):
        if value is None:
            return {"type": "null"}
        return {"type": "text", "value": str(value)}

    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [_arg(arg) for arg in (args or [])],
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


def _cutoff_datetime():
    return (datetime.now() - timedelta(days=RETENTION_DAYS)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _cutoff_iso():
    return _cutoff_datetime().isoformat()


def _day_from_timestamp(value: str):
    return str(value or "")[:10]


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=None):
    try:
        if value is None or value == "" or str(value).strip().lower() in {"none", "null"}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_admin_timestamp(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    return raw.replace("T", " ").split(".")[0]


def _apply_query_filter(rows, query: str, keys):
    normalized = str(query or "").strip().lower()
    if not normalized:
        return rows

    filtered = []
    for row in rows:
        haystack = " ".join(str(row.get(key, "")) for key in keys).lower()
        if normalized in haystack:
            filtered.append(row)
    return filtered


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
        """CREATE TABLE IF NOT EXISTS detection_daily_summary (
            day TEXT PRIMARY KEY,
            total_count INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS audit_daily_summary (
            day TEXT PRIMARY KEY,
            total_count INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_detection_log_timestamp ON detection_log(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_detection_log_name ON detection_log(name)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
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
    weather = weather or {}
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
        "uv_index": _to_float(weather.get("uv_index")),
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


def _summary_total(table_name: str):
    if _turso_ready:
        try:
            rows = _sql(f"SELECT COALESCE(SUM(total_count), 0) AS total FROM {table_name}")
            return _to_int(rows[0].get("total") if rows else 0)
        except Exception as exc:
            print(f"[DB] summary total error for {table_name}: {exc}")
            return 0

    if table_name == "detection_daily_summary":
        return sum(_mem_detection_summary.values())
    return sum(_mem_audit_summary.values())


def get_dashboard_stats():
    users = get_all_users()
    history = get_detection_history(limit=1)

    if _turso_ready:
        detection_rows = _sql("SELECT COUNT(*) AS total FROM detection_log")
        audit_rows = _sql("SELECT COUNT(*) AS total FROM audit_log")
        detection_recent_total = _to_int(detection_rows[0].get("total") if detection_rows else 0)
        audit_recent_total = _to_int(audit_rows[0].get("total") if audit_rows else 0)
    else:
        detection_recent_total = len(_mem_detections)
        audit_recent_total = len(_mem_audit)

    detection_total = _summary_total("detection_daily_summary") + detection_recent_total
    audit_total = _summary_total("audit_daily_summary") + audit_recent_total

    return {
        "total_users": len(users),
        "total_detections": detection_total,
        "recent_activity": _format_admin_timestamp(history[0]["timestamp"]) if history else None,
        "audit_events": audit_total,
        "retention_days": RETENTION_DAYS,
    }


def maintain_log_retention():
    cutoff_iso = _cutoff_iso()

    if _turso_ready:
        try:
            detection_rows = _sql(
                """
                SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS total_count
                FROM detection_log
                WHERE timestamp < ?
                GROUP BY substr(timestamp, 1, 10)
                """,
                [cutoff_iso],
            )
            for row in detection_rows:
                _sql(
                    """
                    INSERT INTO detection_daily_summary (day, total_count)
                    VALUES (?, ?)
                    ON CONFLICT(day) DO UPDATE SET total_count = total_count + excluded.total_count
                    """,
                    [row.get("day"), _to_int(row.get("total_count"))],
                )

            audit_rows = _sql(
                """
                SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS total_count
                FROM audit_log
                WHERE timestamp < ?
                GROUP BY substr(timestamp, 1, 10)
                """,
                [cutoff_iso],
            )
            for row in audit_rows:
                _sql(
                    """
                    INSERT INTO audit_daily_summary (day, total_count)
                    VALUES (?, ?)
                    ON CONFLICT(day) DO UPDATE SET total_count = total_count + excluded.total_count
                    """,
                    [row.get("day"), _to_int(row.get("total_count"))],
                )

            _sql("DELETE FROM detection_log WHERE timestamp < ?", [cutoff_iso])
            _sql("DELETE FROM audit_log WHERE timestamp < ?", [cutoff_iso])
        except Exception as exc:
            print(f"[DB] retention error: {exc}")
        return

    cutoff = _cutoff_datetime()

    retained_detection = []
    for row in _mem_detections:
        timestamp = datetime.fromisoformat(row["timestamp"])
        if timestamp < cutoff:
            day = _day_from_timestamp(row["timestamp"])
            _mem_detection_summary[day] = _mem_detection_summary.get(day, 0) + 1
        else:
            retained_detection.append(row)
    _mem_detections[:] = retained_detection

    retained_audit = []
    for row in _mem_audit:
        timestamp = datetime.fromisoformat(row["timestamp"])
        if timestamp < cutoff:
            day = _day_from_timestamp(row["timestamp"])
            _mem_audit_summary[day] = _mem_audit_summary.get(day, 0) + 1
        else:
            retained_audit.append(row)
    _mem_audit[:] = retained_audit


def get_detection_chart_data():
    day_map = {}

    if _turso_ready:
        try:
            for row in _sql("SELECT day, total_count FROM detection_daily_summary ORDER BY day ASC"):
                day_map[row.get("day")] = day_map.get(row.get("day"), 0) + _to_int(row.get("total_count"))

            recent_rows = _sql(
                """
                SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS total_count
                FROM detection_log
                GROUP BY substr(timestamp, 1, 10)
                ORDER BY day ASC
                """
            )
            for row in recent_rows:
                day_map[row.get("day")] = day_map.get(row.get("day"), 0) + _to_int(row.get("total_count"))
        except Exception as exc:
            print(f"[DB] chart data error: {exc}")
            return {"days": [], "detections": []}
    else:
        day_map.update(_mem_detection_summary)
        for row in _mem_detections:
            day = _day_from_timestamp(row["timestamp"])
            day_map[day] = day_map.get(day, 0) + 1

    days = sorted(day for day in day_map if day)
    return {"days": days, "detections": [day_map[day] for day in days]}


def prepare_history_export_rows(rows):
    return [
        {
            "name": row.get("name", ""),
            "timestamp": row.get("timestamp", ""),
            "mask": row.get("mask", ""),
            "glasses": row.get("glasses", ""),
            "city": row.get("city", ""),
            "temp": row.get("temp", ""),
            "feels_like": row.get("feels_like", ""),
            "aqi": row.get("aqi", ""),
            "aqi_label": row.get("aqi_label", ""),
            "uv_index": row.get("uv_index", ""),
        }
        for row in rows
    ]


def prepare_audit_export_rows(rows):
    return [
        {
            "timestamp": row.get("timestamp", ""),
            "event": row.get("event", ""),
            "detail": row.get("detail", ""),
            "ip": row.get("ip", ""),
        }
        for row in rows
    ]


def filter_history_rows(rows, query: str = "", user: str = ""):
    filtered = rows
    if user:
        filtered = [row for row in filtered if row.get("name") == user]
    return _apply_query_filter(
        filtered,
        query,
        ["name", "mask", "glasses", "city", "timestamp", "aqi_label"],
    )


def filter_audit_rows(rows, query: str = ""):
    return _apply_query_filter(rows, query, ["timestamp", "event", "detail", "ip"])


def clear_detection_history(name: str = None):
    if _turso_ready:
        try:
            if name:
                _sql("DELETE FROM detection_log WHERE name = ?", [name])
                _sql(
                    "UPDATE registered_users SET detection_count = 0 WHERE name = ?",
                    [name],
                )
            else:
                _sql("DELETE FROM detection_log")
                _sql("DELETE FROM detection_daily_summary")
                _sql("UPDATE registered_users SET detection_count = 0")
            return True
        except Exception as exc:
            print(f"[DB] clear detection history error: {exc}")
            return False

    if name:
        _mem_detections[:] = [row for row in _mem_detections if row.get("name") != name]
        if name in _mem_users:
            _mem_users[name]["detection_count"] = 0
        return True

    _mem_detections.clear()
    _mem_detection_summary.clear()
    for user in _mem_users.values():
        user["detection_count"] = 0
    return True


def clear_audit_history():
    if _turso_ready:
        try:
            _sql("DELETE FROM audit_log")
            _sql("DELETE FROM audit_daily_summary")
            return True
        except Exception as exc:
            print(f"[DB] clear audit history error: {exc}")
            return False

    _mem_audit.clear()
    _mem_audit_summary.clear()
    return True
