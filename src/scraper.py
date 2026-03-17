import requests
import time
import os
import json
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _retry_get(url, params=None, headers=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Attempt {i+1} failed: {e}")
            if i < retries - 1:
                time.sleep(2 ** i)
    return None


def fetch_seatgeek(config: dict) -> list[dict]:
    results = []
    start = config["date_range"]["start"]
    end = config["date_range"]["end"]

    for team in config["teams"]:
        slug = team["seatgeek_slug"]
        data = _retry_get(
            "https://api.seatgeek.com/2/events",
            params={
                "performers.slug": slug,
                "datetime_utc.gte": f"{start}T00:00:00",
                "datetime_utc.lte": f"{end}T23:59:59",
                "venue.city": "Los Angeles",
                "per_page": 25,
            },
        )
        if not data or "events" not in data:
            # Try without venue.city filter (Clippers play in Inglewood)
            data = _retry_get(
                "https://api.seatgeek.com/2/events",
                params={
                    "performers.slug": slug,
                    "datetime_utc.gte": f"{start}T00:00:00",
                    "datetime_utc.lte": f"{end}T23:59:59",
                    "per_page": 25,
                },
            )
        if not data or "events" not in data:
            logger.info(f"No SeatGeek events for {team['name']}")
            continue

        for ev in data["events"]:
            # Only home games: team should be in the home performers
            is_home = False
            for p in ev.get("performers", []):
                if p.get("slug") == slug and p.get("home_team", False):
                    is_home = True
                    break
            # Fallback: check venue city
            venue_city = ev.get("venue", {}).get("city", "")
            if not is_home and venue_city.lower() not in ("los angeles", "inglewood"):
                continue

            stats = ev.get("stats", {})
            results.append({
                "event_id": f"sg_{ev['id']}",
                "event_title": ev.get("title", ""),
                "event_date": ev.get("datetime_local", ""),
                "venue": ev.get("venue", {}).get("name", ""),
                "team": team["name"],
                "source": "seatgeek",
                "lowest_price": stats.get("lowest_sg_base_price") or stats.get("lowest_price"),
                "average_price": stats.get("average_price"),
                "highest_price": stats.get("highest_price"),
                "listing_count": stats.get("listing_count"),
                "url": ev.get("url", ""),
            })
    return results


def fetch_ticketmaster(config: dict) -> list[dict]:
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        return []

    results = []
    start = config["date_range"]["start"]
    end = config["date_range"]["end"]

    for team in config["teams"]:
        data = _retry_get(
            "https://app.ticketmaster.com/discovery/v2/events.json",
            params={
                "keyword": team["tm_keyword"],
                "startDateTime": f"{start}T00:00:00Z",
                "endDateTime": f"{end}T23:59:59Z",
                "classificationName": "Basketball",
                "size": 25,
                "apikey": api_key,
            },
        )
        if not data:
            continue

        events = data.get("_embedded", {}).get("events", [])
        for ev in events:
            price_ranges = ev.get("priceRanges", [{}])
            pr = price_ranges[0] if price_ranges else {}
            results.append({
                "event_id": f"tm_{ev['id']}",
                "event_title": ev.get("name", ""),
                "event_date": ev.get("dates", {}).get("start", {}).get("localDate", ""),
                "venue": ev.get("_embedded", {}).get("venues", [{}])[0].get("name", ""),
                "team": team["name"],
                "source": "ticketmaster",
                "lowest_price": pr.get("min"),
                "average_price": None,
                "highest_price": pr.get("max"),
                "listing_count": None,
                "url": ev.get("url", ""),
            })
    return results


def fetch_all() -> list[dict]:
    config = load_config()
    results = fetch_seatgeek(config)
    results.extend(fetch_ticketmaster(config))
    return results
