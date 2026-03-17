from src.db import get_previous


def _arrow(current, previous):
    if current is None or previous is None:
        return ""
    diff = current - previous
    pct = (diff / previous * 100) if previous else 0
    if abs(pct) < 0.5:
        return ""
    symbol = "📉" if diff < 0 else "📈"
    return f" {symbol}{diff:+.0f} ({pct:+.1f}%)"


def format_report(games: list[dict]) -> str:
    if not games:
        return "🏀 No events found yet. Will check again next cycle."

    lines = ["🏀 **NBA Ticket Price Update**\n"]

    for g in games:
        lines.append(f"🎫 **{g['event_title']}**")
        lines.append(f"📅 {g['event_date'][:10]} | 🏟 {g['venue']}")

        vivid = g.get("vivid")
        stubhub = g.get("stubhub")

        # Source comparison
        source_prices = []
        if vivid:
            ov = vivid["overall"]
            prev = get_previous(f"{g['event_id']}_vividseats")
            change = _arrow(ov["min_price"], prev["lowest_price"]) if prev and prev.get("lowest_price") else ""
            source_prices.append(("Vivid Seats", ov["min_price"], change, ov.get("listing_count")))
        if stubhub:
            prev = get_previous(f"{g['event_id']}_stubhub")
            change = _arrow(stubhub["low_price"], prev["lowest_price"]) if prev and prev.get("lowest_price") else ""
            source_prices.append(("StubHub", stubhub["low_price"], change, None))

        if source_prices:
            lines.append("")
            lines.append("  **Lowest by source:**")
            for name, price, change, count in sorted(source_prices, key=lambda x: x[1]):
                count_str = f" ({count} listings)" if count else ""
                lines.append(f"  • {name}: **${price:.0f}**{change}{count_str}")

        # Section-level listings from Vivid Seats (deals + recently sold)
        if vivid and vivid.get("listings"):
            lines.append("")
            lines.append("  **Available deals (section / row / price):**")
            for item in vivid["listings"]["deals"]:
                lines.append(f"  • {item['section']} · Row {item['row']} — **${item['price']:.0f}**")

            if vivid["listings"]["recent_sold"]:
                lines.append("")
                lines.append("  **Recently sold:**")
                # Deduplicate and show unique section/row combos
                seen = set()
                for item in vivid["listings"]["recent_sold"]:
                    key = f"{item['section']}_{item['row']}_{item['price']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    zone_str = f" ({item['zone']})" if item.get("zone") and item["zone"] != item["section"] else ""
                    lines.append(f"  • Sec {item['section']}{zone_str} · Row {item['row']} — ${item['price']:.0f}")

        # Overall stats
        if vivid:
            ov = vivid["overall"]
            lines.append("")
            lines.append(f"  📊 Median: ${ov.get('median_price', 0):.0f} | "
                        f"Avg: ${ov.get('avg_price', 0):.0f} | "
                        f"{ov.get('ticket_count', 0)} tickets available")

        # Links
        if vivid:
            lines.append(f"  🔗 VividSeats: {vivid['url']}")
        if stubhub and stubhub.get("url"):
            lines.append(f"  🔗 StubHub: {stubhub['url']}")

        lines.append("")

    return "\n".join(lines)
