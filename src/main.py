import sys
import os
import logging

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "error.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

from src.scraper import fetch_all
from src.db import save_prices
from src.notifier import format_report


def main():
    try:
        records = fetch_all()
        if records:
            save_prices(records)
        report = format_report(records)
        print(report)
    except Exception as e:
        logging.exception("Fatal error")
        print(f"❌ Error checking prices: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
