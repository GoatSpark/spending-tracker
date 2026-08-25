"""
Aggregation of logged Expenses into per-day totals and week/month/quarter/
year summary stats (total spent, average per day, count, largest/smallest
single purchase).
"""

from collections import defaultdict
from datetime import date, timedelta

from database import Expense

RANGE_WEEK = "week"
RANGE_MONTH = "month"
RANGE_QUARTER = "quarter"
RANGE_YEAR = "year"

RANGE_DAYS = {
    RANGE_WEEK: 7,
    RANGE_MONTH: 30,
    RANGE_QUARTER: 90,
    RANGE_YEAR: 365,
}


class DayTotal:
    """Running total + count + largest/smallest single purchase for one day."""
    __slots__ = ("total_cents", "count", "max_cents", "min_cents")

    def __init__(self):
        self.total_cents = 0
        self.count = 0
        self.max_cents = 0
        self.min_cents = None

    def add(self, cents: int) -> None:
        self.total_cents += cents
        self.count += 1
        self.max_cents = max(self.max_cents, cents)
        self.min_cents = cents if self.min_cents is None else min(self.min_cents, cents)


def build_daily_totals(db) -> dict:
    """Return {date: DayTotal} across all logged expenses."""
    by_date = defaultdict(DayTotal)
    for expense in db.query(Expense).order_by(Expense.timestamp.asc()).all():
        by_date[expense.timestamp.date()].add(expense.amount_cents)
    return dict(by_date)


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(round(cents)), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def range_stats(by_date: dict, range_name: str, today: date | None = None) -> dict | None:
    """Total/avg-per-day/count/largest/smallest over the named range.
    Average is total / the range's full day count (e.g. always /7 for
    "week"), not / days-with-data, so it reads as an actual daily spending
    rate rather than skewing up on sparsely-logged ranges."""
    today = today or date.today()
    days = RANGE_DAYS[range_name]
    since = today - timedelta(days=days - 1)

    days_in_range = [day for day in by_date if since <= day <= today]
    if not days_in_range:
        return None

    total_cents = sum(by_date[day].total_cents for day in days_in_range)
    return {
        "total_cents": total_cents,
        "count": sum(by_date[day].count for day in days_in_range),
        "avg_per_day_cents": round(total_cents / days),
        "largest_cents": max(by_date[day].max_cents for day in days_in_range),
        "smallest_cents": min(by_date[day].min_cents for day in days_in_range),
    }
