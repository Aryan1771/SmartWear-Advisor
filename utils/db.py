# ===================== db.py =====================

import sqlite3

DB = "smartwear.db"


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        name TEXT,
        image TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        name TEXT,
        mask TEXT,
        glasses TEXT
    )
    """)

    conn.commit()
    conn.close()


def add_user(name, image):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("INSERT INTO users VALUES (?, ?)", (name, image))

    conn.commit()
    conn.close()


def get_users():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute("SELECT name FROM users").fetchall()

    conn.close()

    return [{"name": r[0]} for r in rows]


def log_detection(data):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "INSERT INTO history VALUES (?, ?, ?)",
        (data["name"], data["mask"], data["glasses"])
    )

    conn.commit()
    conn.close()


def get_history():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute("SELECT * FROM history").fetchall()

    conn.close()

    return [
        {
            "name": r[0],
            "mask": r[1],
            "glasses": r[2],
            "timestamp": "-"
        }
        for r in rows
    ]
