import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Expense, UNCATEGORIZED
from stats import (
    build_daily_totals,
    range_stats,
    spend_rate_stats,
    category_breakdown,
    format_cents,
    RANGE_DAYS,
)


def _add_expense(db, cents, dt, item="test", category=UNCATEGORIZED, raw="test"):
    expense = Expense(amount_cents=cents, item=item, category=category, timestamp=dt, raw_message=raw)
    db.add(expense)
    db.commit()
    return expense


def test_format_cents():
    assert format_cents(1200) == "$12.00"
    assert format_cents(899) == "$8.99"
    assert format_cents(120000) == "$1,200.00"
    assert format_cents(5) == "$0.05"
    assert format_cents(-500) == "-$5.00"


def test_build_daily_totals_sums_same_day_entries(db_session):
    day = date(2026, 8, 1)
    _add_expense(db_session, 1200, datetime(2026, 8, 1, 12, 0), category="food")
    _add_expense(db_session, 899, datetime(2026, 8, 1, 18, 0), category="coffee")

    by_date = build_daily_totals(db_session)

    assert by_date[day].total_cents == 2099
    assert by_date[day].count == 2
    assert by_date[day].max_cents == 1200
    assert by_date[day].min_cents == 899
    assert by_date[day].categories == {"food": 1200, "coffee": 899}


def test_range_stats_totals_across_days(db_session):
    _add_expense(db_session, 1000, datetime(2026, 8, 1, 9, 0))
    _add_expense(db_session, 2000, datetime(2026, 8, 2, 9, 0))
    _add_expense(db_session, 500, datetime(2026, 8, 3, 9, 0))

    by_date = build_daily_totals(db_session)
    stats = range_stats(by_date, "week", today=date(2026, 8, 3))

    assert stats["total_cents"] == 3500
    assert stats["count"] == 3
    assert stats["largest_cents"] == 2000
    assert stats["smallest_cents"] == 500
    assert stats["avg_per_day_cents"] == round(3500 / 7)


def test_range_stats_none_when_no_data(db_session):
    by_date = build_daily_totals(db_session)
    assert range_stats(by_date, "week") is None


def test_range_stats_since_filters_out_old_days(db_session):
    _add_expense(db_session, 100000, datetime(2020, 1, 1, 9, 0))  # far in the past
    _add_expense(db_session, 1000, datetime(2026, 8, 1, 9, 0))

    by_date = build_daily_totals(db_session)
    stats = range_stats(by_date, "week", today=date(2026, 8, 1))

    assert stats["total_cents"] == 1000
    assert stats["count"] == 1


def test_range_days_ordering():
    assert RANGE_DAYS["week"] < RANGE_DAYS["month"] < RANGE_DAYS["quarter"] < RANGE_DAYS["year"]


def test_spend_rate_stats_derived_from_year_total(db_session):
    _add_expense(db_session, 36500 * 100, datetime(2026, 1, 1, 9, 0))  # $36,500 in the trailing year

    by_date = build_daily_totals(db_session)
    rate = spend_rate_stats(by_date, today=date(2026, 8, 1))

    assert rate["weekly_cents"] == round(36500 * 100 / 52)
    assert rate["monthly_cents"] == round(36500 * 100 / 12)
    assert rate["quarterly_cents"] == round(36500 * 100 / 4)


def test_spend_rate_stats_none_when_no_data(db_session):
    by_date = build_daily_totals(db_session)
    assert spend_rate_stats(by_date) is None


def test_category_breakdown_sums_and_sorts_descending(db_session):
    _add_expense(db_session, 1000, datetime(2026, 8, 1, 9, 0), category="food")
    _add_expense(db_session, 500, datetime(2026, 8, 2, 9, 0), category="food")
    _add_expense(db_session, 2000, datetime(2026, 8, 3, 9, 0), category="gas")

    by_date = build_daily_totals(db_session)
    breakdown = category_breakdown(by_date, "week", today=date(2026, 8, 3))

    assert list(breakdown.items()) == [("gas", 2000), ("food", 1500)]


def test_category_breakdown_empty_when_no_data(db_session):
    by_date = build_daily_totals(db_session)
    assert category_breakdown(by_date, "week") == {}
