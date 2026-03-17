# 🏀 NBA Ticket Price Tracker

Monitors NBA ticket prices for specific teams and date ranges, tracking price changes over time with notifications.

## Currently Monitoring
- **LA Lakers** & **LA Clippers** home games
- **Date range**: April 3–11, 2026
- **Check interval**: Every 6 hours

## Data Sources
- [SeatGeek](https://seatgeek.com) (free API, no key required)
- [Ticketmaster](https://developer.ticketmaster.com) (optional, set `TICKETMASTER_API_KEY`)

## Setup

```bash
cd nba-ticket-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

## Configuration

Edit `config.json` to change teams, date ranges, or alert thresholds.

## Dashboard

View the live price dashboard at the [GitHub Pages site](https://jovin-cc.github.io/nba-ticket-tracker/).

## How It Works

1. Fetches ticket listings from SeatGeek/Ticketmaster APIs
2. Stores price snapshots in SQLite (`data/prices.db`)
3. Compares with previous checks to show trends (📈📉)
4. Sends formatted updates via Telegram
