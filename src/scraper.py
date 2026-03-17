import requests
import time
import os
import re
import json
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _retry_get(url, params=None, headers=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers or HEADERS, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            logger.warning(f"Attempt {i+1} failed for {url}: {e}")
            if i < retries - 1:
                time.sleep(2 ** i)
    return None


def scrape_vivid_price(url: str) -> dict | None:
    """Scrape price data from Vivid Seats using __NEXT_DATA__."""
    try:
        r = _retry_get(url)
        if not r:
            return None

        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not m:
            logger.warning("No __NEXT_DATA__ found on Vivid Seats page")
            return None

        nd = json.loads(m.group(1))
        pp = nd.get("props", {}).get("pageProps", {})

        # Get prices from top deals
        deals = pp.get("initialTopDealListingsData", {}).get("data", {}).get("topDeals", [])
        deal_prices = [float(d["price"]) for d in deals if d.get("price")]

        # Get recently sold for context
        sold = pp.get("initialRecentlySoldListingsData", {}).get("data", {}).get("listings", [])
        sold_prices = [float(s["price"]) for s in sold if s.get("price")]

        # Urgency data for listing count
        urgency = pp.get("initialUrgencyVelocityData", {}).get("data", {}).get("items", [])
        listing_count = None
        if urgency:
            udata = urgency[0].get("data", {})
            listing_count = udata.get("uLT")  # listings long-term count

        lowest = min(deal_prices) if deal_prices else (min(sold_prices) if sold_prices else None)
        highest = max(deal_prices) if deal_prices else None
        avg = sum(deal_prices) / len(deal_prices) if deal_prices else None

        if lowest is None:
            return None

        return {
            "lowest_price": lowest,
            "average_price": round(avg, 2) if avg else None,
            "highest_price": highest,
            "listing_count": listing_count,
        }
    except Exception as e:
        logger.error(f"Vivid scrape error for {url}: {e}")
        return None


def fetch_seatgeek(config: dict) -> list[dict]:
    """Fetch from SeatGeek API."""
    results = []
    start = config["date_range"]["start"]
    end = config["date_range"]["end"]

    for team in config["teams"]:
        slug = team["seatgeek_slug"]
        r = _retry_get(
            "https://api.seatgeek.com/2/events",
            params={
                "performers.slug": slug,
                "datetime_utc.gte": f"{start}T00:00:00",
                "datetime_utc.lte": f"{end}T23:59:59",
                "per_page": 25,
            },
            headers=None,
        )
        if not r:
            continue
        data = r.json()
        if not data.get("events"):
            continue

        for ev in data["events"]:
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


def fetch_configured_games(config: dict) -> list[dict]:
    """Fetch prices for hardcoded home games from Vivid Seats."""
    results = []
    for game in config.get("home_games", []):
        vivid_url = game.get("vivid_url", "")
        prices = None
        if vivid_url:
            logger.info(f"Scraping Vivid Seats for {game['title']}...")
            prices = scrape_vivid_price(vivid_url)

        results.append({
            "event_id": game["event_id"],
            "event_title": game["title"],
            "event_date": game["date"],
            "venue": game["venue"],
            "team": game["team"],
            "source": "vividseats",
            "lowest_price": prices["lowest_price"] if prices else None,
            "average_price": prices.get("average_price") if prices else None,
            "highest_price": prices.get("highest_price") if prices else None,
            "listing_count": prices.get("listing_count") if prices else None,
            "url": vivid_url or game.get("espn_url", ""),
        })
    return results


def fetch_all() -> list[dict]:
    config = load_config()
    results = fetch_configured_games(config)
    sg_results = fetch_seatgeek(config)
    existing_ids = {r["event_id"] for r in results}
    for r in sg_results:
        if r["event_id"] not in existing_ids:
            results.append(r)
    return results
