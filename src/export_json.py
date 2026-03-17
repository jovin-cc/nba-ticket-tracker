"""Export latest price data from SQLite to JSON for GitHub Pages."""
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prices.db")
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "data", "latest.json")


def export():
    if not os.path.exists(DB_PATH):
        print("No database found yet.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get latest check per event
    rows = conn.execute("""
        SELECT p.* FROM price_checks p
        INNER JOIN (
            SELECT event_id, MAX(checked_at) as max_checked
            FROM price_checks GROUP BY event_id
        ) latest ON p.event_id = latest.event_id AND p.checked_at = latest.max_checked
        ORDER BY p.event_date
    """).fetchall()

    games = []
    for r in rows:
        # Get previous price for change calc
        prev = conn.execute(
            """SELECT lowest_price FROM price_checks
               WHERE event_id=? ORDER BY checked_at DESC LIMIT 1 OFFSET 1""",
            (r["event_id"],)
        ).fetchone()

        price_change = None
        if prev and prev["lowest_price"] and r["lowest_price"]:
            price_change = r["lowest_price"] - prev["lowest_price"]

        games.append({
            "title": r["event_title"],
            "date": r["event_date"],
            "venue": r["venue"],
            "team": r["team"],
            "source": r["source"],
            "lowest_price": r["lowest_price"],
            "average_price": r["average_price"],
            "highest_price": r["highest_price"],
            "listing_count": r["listing_count"],
            "url": r["url"],
            "price_change": price_change,
        })

    conn.close()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    data = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "games": games,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported {len(games)} games to {OUT_PATH}")


if __name__ == "__main__":
    export()
