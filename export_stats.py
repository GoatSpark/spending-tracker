"""
Export logged expenses to docs/data.json for the GitHub Pages dashboard.

Run periodically (see scripts/export_and_push.sh + the systemd timer) - this
script only writes the JSON file, it does not touch git. Format is one row
per day: total spent, count of purchases, the largest/smallest single
purchase that day, and a per-category subtotal (all in integer cents) -
enough for the dashboard to compute total/avg/largest/smallest/by-category
over any selected range without re-deriving them from individual
transactions client-side. Per-transaction `item` text is deliberately left
out of the export - only category subtotals are public, not what you
actually bought.
"""

import json
import os

os.environ.setdefault("SPENDING_BOT_ALLOW_LIVE_DB", "1")

from config import Config
from database import SessionLocal
from stats import build_daily_totals

DATA_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data.json")


def build_export() -> dict:
    db = SessionLocal()
    try:
        by_date = build_daily_totals(db)
    finally:
        db.close()

    days = []
    for day in sorted(by_date.keys()):
        totals = by_date[day]
        days.append({
            "date": day.isoformat(),
            "total_cents": totals.total_cents,
            "count": totals.count,
            "max_cents": totals.max_cents,
            "min_cents": totals.min_cents,
            "categories": dict(totals.categories),
        })

    return {
        "generated_at": Config.now().isoformat(),
        "timezone": str(Config.TIMEZONE),
        "days": days,
    }


def main():
    export = build_export()
    os.makedirs(os.path.dirname(DATA_JSON_PATH), exist_ok=True)
    with open(DATA_JSON_PATH, "w") as f:
        json.dump(export, f, indent=2)
    print(f"Wrote {len(export['days'])} day(s) to {DATA_JSON_PATH}")


if __name__ == "__main__":
    main()
