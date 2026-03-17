import requests
import time
import os
import re
import json
import logging
from collections import defaultdict

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


def _classify_section(section_name: str) -> str:
    """Classify a section name into a tier."""
    s = section_name.lower()
    if any(x in s for x in ["courtside", "floor", "vip", "premier", "a1", "a2", "a3", "a4"]):
        return "Courtside/Floor"
    if any(x in s for x in ["loge", "lower", "100", "10"]):
        return "Lower Level"
    if any(x in s for x in ["middle", "mid", "200", "20", "club"]):
        return "Mid Level"
    if any(x in s for x in ["upper", "300", "30", "balcony"]):
        return "Upper Level"
    # Section numbers: 100s=lower, 200s=mid, 300s=upper
    num = re.search(r"(\d+)", section_name)
    if num:
        n = int(num.group(1))
        if n < 100:
            return "Courtside/Floor"
        elif n < 200:
            return "Lower Level"
        elif n < 300:
            return "Mid Level"
        else:
            return "Upper Level"
    return "Other"


def scrape_vivid_seats(url: str) -> dict | None:
    """Scrape full price data including section breakdown from Vivid Seats."""
    try:
        r = _retry_get(url)
        if not r:
            return None
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not m:
            return None
        pp = json.loads(m.group(1)).get("props", {}).get("pageProps", {})

        # Production details - overall stats
        prod = pp.get("initialProductionDetailsData", {}).get("data", {})
        overall = {
            "min_price": prod.get("minPrice"),
            "max_price": prod.get("maxPrice"),
            "avg_price": prod.get("avgPrice"),
            "median_price": prod.get("medianPrice"),
            "listing_count": prod.get("listingCount"),
            "ticket_count": prod.get("ticketCount"),
        }

        # Build section breakdown from top deals + recently sold
        section_prices = defaultdict(list)

        # Raw listing data: deals and recently sold with section codes
        deals_raw = []
        deals = pp.get("initialTopDealListingsData", {}).get("data", {}).get("topDeals", [])
        for d in deals:
            if d.get("section") and d.get("price"):
                deals_raw.append({
                    "section": d["section"],
                    "row": d.get("row", ""),
                    "price": float(d["price"]),
                })

        sold_raw = []
        sold = pp.get("initialRecentlySoldListingsData", {}).get("data", {}).get("listings", [])
        for s in sold:
            if s.get("section") and s.get("price"):
                sold_raw.append({
                    "section": s["section"],
                    "zone": s.get("zone", ""),
                    "row": s.get("row", ""),
                    "price": float(s["price"]),
                    "quantity": s.get("quantity"),
                })

        listings = {"deals": deals_raw, "recent_sold": sold_raw}

        return {"overall": overall, "listings": listings, "source": "vividseats", "url": url}
    except Exception as e:
        logger.error(f"Vivid scrape error: {e}")
        return None


def scrape_stubhub_grouping(grouping_url: str, target_date: str) -> dict | None:
    """Get lowPrice from StubHub grouping page JSON-LD for a specific date."""
    try:
        r = _retry_get(grouping_url)
        if not r:
            return None
        ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
        for block in ld_blocks:
            try:
                d = json.loads(block)
                for item in d.get("@graph", [d] if not isinstance(d, list) else d):
                    if item.get("@type") != "SportsEvent":
                        continue
                    if target_date not in str(item.get("startDate", "")):
                        continue
                    if "PARKING" in item.get("name", ""):
                        continue
                    offers = item.get("offers", {})
                    low = offers.get("lowPrice")
                    if low:
                        return {
                            "low_price": float(low),
                            "url": item.get("url", ""),
                            "source": "stubhub",
                        }
            except (json.JSONDecodeError, ValueError):
                continue
        return None
    except Exception as e:
        logger.error(f"StubHub scrape error: {e}")
        return None


def fetch_all() -> list[dict]:
    config = load_config()
    results = []

    # StubHub grouping URLs to batch-fetch
    stubhub_groupings = {
        "lakers_vs_thunder": "https://www.stubhub.com/lakers-vs-thunder-tickets/grouping/431702",
        "lakers_vs_suns": "https://www.stubhub.com/lakers-vs-suns-tickets/grouping/431704",
        "mavericks_vs_clippers": "https://www.stubhub.com/mavericks-vs-clippers-tickets/grouping/430402",
        "thunder_vs_clippers": "https://www.stubhub.com/thunder-vs-clippers-tickets/grouping/430398",
    }

    stubhub_map = {
        "lakers_okc_apr7": ("lakers_vs_thunder", "2026-04-07"),
        "lakers_suns_apr10": ("lakers_vs_suns", "2026-04-10"),
        "clippers_mavs_apr7": ("mavericks_vs_clippers", "2026-04-07"),
        "clippers_okc_apr8": ("thunder_vs_clippers", "2026-04-08"),
    }

    # Pre-fetch StubHub grouping pages
    stubhub_cache = {}
    for key, url in stubhub_groupings.items():
        stubhub_cache[key] = _retry_get(url)

    for game in config.get("home_games", []):
        game_id = game["event_id"]
        sources = game.get("sources", {})

        game_result = {
            "event_id": game_id,
            "event_title": game["title"],
            "event_date": game["date"],
            "venue": game["venue"],
            "team": game["team"],
            "vivid": None,
            "stubhub": None,
            "seatgeek": None,
        }

        # Vivid Seats
        vivid_url = sources.get("vividseats")
        if vivid_url:
            game_result["vivid"] = scrape_vivid_seats(vivid_url)

        # StubHub - from cached grouping pages
        sh_info = stubhub_map.get(game_id)
        if sh_info:
            grouping_key, target_date = sh_info
            cached_resp = stubhub_cache.get(grouping_key)
            if cached_resp:
                # Parse from cached response
                ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', cached_resp.text, re.DOTALL)
                for block in ld_blocks:
                    try:
                        d = json.loads(block)
                        for item in d.get("@graph", [d] if not isinstance(d, list) else d):
                            if item.get("@type") != "SportsEvent":
                                continue
                            if target_date not in str(item.get("startDate", "")):
                                continue
                            if "PARKING" in item.get("name", ""):
                                continue
                            offers = item.get("offers", {})
                            low = offers.get("lowPrice")
                            if low:
                                game_result["stubhub"] = {
                                    "low_price": float(low),
                                    "url": item.get("url", ""),
                                    "source": "stubhub",
                                }
                    except (json.JSONDecodeError, ValueError):
                        continue

        # SeatGeek API (may not have events yet)
        # Will be populated from the API when available

        results.append(game_result)

    # Also store flat records for DB compatibility
    flat_records = []
    for g in results:
        if g["vivid"]:
            v = g["vivid"]
            flat_records.append({
                "event_id": f"{g['event_id']}_vividseats",
                "event_title": g["event_title"],
                "event_date": g["event_date"],
                "venue": g["venue"],
                "team": g["team"],
                "source": "vividseats",
                "lowest_price": v["overall"]["min_price"],
                "average_price": v["overall"]["avg_price"],
                "highest_price": v["overall"]["max_price"],
                "listing_count": v["overall"]["listing_count"],
                "url": v["url"],
            })
        if g["stubhub"]:
            s = g["stubhub"]
            flat_records.append({
                "event_id": f"{g['event_id']}_stubhub",
                "event_title": g["event_title"],
                "event_date": g["event_date"],
                "venue": g["venue"],
                "team": g["team"],
                "source": "stubhub",
                "lowest_price": s["low_price"],
                "average_price": None,
                "highest_price": None,
                "listing_count": None,
                "url": s["url"],
            })

    return results, flat_records
