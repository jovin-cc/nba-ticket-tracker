import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prices.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    event_title TEXT,
    event_date TEXT,
    venue TEXT,
    team TEXT,
    source TEXT,
    lowest_price REAL,
    average_price REAL,
    highest_price REAL,
    listing_count INTEGER,
    url TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_event_checked ON price_checks(event_id, checked_at);
"""


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_prices(records: list[dict]):
    conn = get_conn()
    for r in records:
        conn.execute(
            """INSERT INTO price_checks
               (event_id, event_title, event_date, venue, team, source,
                lowest_price, average_price, highest_price, listing_count, url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["event_id"], r["event_title"], r["event_date"], r["venue"],
                r["team"], r["source"], r["lowest_price"], r["average_price"],
                r["highest_price"], r["listing_count"], r["url"],
            ),
        )
    conn.commit()
    conn.close()


def get_previous(event_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        """SELECT * FROM price_checks WHERE event_id=?
           ORDER BY checked_at DESC LIMIT 1 OFFSET 1""",
        (event_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_first(event_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        """SELECT * FROM price_checks WHERE event_id=?
           ORDER BY checked_at ASC LIMIT 1""",
        (event_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
