from src.db import get_previous, get_first


def _arrow(current, previous):
    if current is None or previous is None:
        return ""
    diff = current - previous
    pct = (diff / previous * 100) if previous else 0
    if abs(pct) < 0.5:
        return "→ unchanged"
    symbol = "📉" if diff < 0 else "📈"
    return f"{symbol} {'+' if diff > 0 else ''}{diff:.0f} ({pct:+.1f}%)"


def format_report(records: list[dict]) -> str:
    if not records:
        return "🏀 No events found yet for the monitored date range. Will check again next cycle."

    lines = ["🏀 **NBA Ticket Price Update**\n"]

    for r in records:
        prev = get_previous(r["event_id"])
        first = get_first(r["event_id"])

        lines.append(f"🎫 **{r['event_title']}**")
        lines.append(f"📅 {r['event_date']}")
        lines.append(f"🏟 {r['venue']}")

        low = r["lowest_price"]
        avg = r["average_price"]

        price_line = f"💰 Lowest: ${low:.0f}" if low else "💰 Lowest: N/A"
        if avg:
            price_line += f" | Avg: ${avg:.0f}"
        lines.append(price_line)

        if r["listing_count"]:
            lines.append(f"📊 {r['listing_count']} listings")

        if prev and prev.get("lowest_price") and low:
            change = _arrow(low, prev["lowest_price"])
            lines.append(f"  vs last check: {change}")

        if first and first.get("lowest_price") and low and first["id"] != (prev or {}).get("id"):
            trend = _arrow(low, first["lowest_price"])
            lines.append(f"  vs first seen: {trend}")

        if r.get("url"):
            lines.append(f"🔗 {r['url']}")

        lines.append("")

    return "\n".join(lines)
