import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Budget, Expense
from stats import build_daily_totals
from budgets import set_budget, list_budgets, budget_status, status_for_category


def _add_expense(db, cents, dt, category, item="test"):
    db.add(Expense(amount_cents=cents, item=item, category=category, timestamp=dt, raw_message="test"))
    db.commit()


def test_set_budget_creates_new(db_session):
    budget = set_budget(db_session, "food", 30000)
    assert budget.category == "food"
    assert budget.amount_cents == 30000
    assert db_session.query(Budget).count() == 1


def test_set_budget_updates_existing_instead_of_duplicating(db_session):
    set_budget(db_session, "food", 30000)
    set_budget(db_session, "food", 50000)

    assert db_session.query(Budget).count() == 1
    assert db_session.query(Budget).one().amount_cents == 50000


def test_set_budget_zero_clears_it(db_session):
    set_budget(db_session, "food", 30000)
    result = set_budget(db_session, "food", 0)

    assert result is None
    assert db_session.query(Budget).count() == 0


def test_set_budget_zero_on_nonexistent_is_a_no_op(db_session):
    result = set_budget(db_session, "food", 0)
    assert result is None
    assert db_session.query(Budget).count() == 0


def test_list_budgets_sorted_by_category(db_session):
    set_budget(db_session, "gas", 10000)
    set_budget(db_session, "food", 30000)

    categories = [b.category for b in list_budgets(db_session)]
    assert categories == ["food", "gas"]


def test_budget_status_computes_spend_and_sorts_by_pct_used_desc(db_session):
    set_budget(db_session, "food", 30000)   # $300 budget
    set_budget(db_session, "gas", 10000)    # $100 budget
    _add_expense(db_session, 27000, datetime(2026, 8, 1, 9, 0), "food")  # 90% of food budget
    _add_expense(db_session, 2000, datetime(2026, 8, 2, 9, 0), "gas")    # 20% of gas budget

    by_date = build_daily_totals(db_session)
    statuses = budget_status(db_session, by_date, today=date(2026, 8, 2))

    assert [s.category for s in statuses] == ["food", "gas"]
    food_status = statuses[0]
    assert food_status.spent_cents == 27000
    assert food_status.is_near is True
    assert food_status.is_over is False
    assert round(food_status.pct_used, 2) == 0.9


def test_budget_status_over_budget(db_session):
    set_budget(db_session, "food", 30000)
    _add_expense(db_session, 35000, datetime(2026, 8, 1, 9, 0), "food")

    by_date = build_daily_totals(db_session)
    status = budget_status(db_session, by_date, today=date(2026, 8, 1))[0]

    assert status.is_over is True
    assert status.is_near is False  # is_near is exclusively for "close but not over"
    assert status.remaining_cents == -5000


def test_budget_status_zero_spend_shows_no_warning(db_session):
    set_budget(db_session, "food", 30000)

    by_date = build_daily_totals(db_session)
    status = budget_status(db_session, by_date, today=date(2026, 8, 1))[0]

    assert status.spent_cents == 0
    assert status.is_over is False
    assert status.is_near is False


def test_status_for_category_none_when_no_budget_set(db_session):
    _add_expense(db_session, 1000, datetime(2026, 8, 1, 9, 0), "food")
    by_date = build_daily_totals(db_session)

    assert status_for_category(db_session, by_date, "food") is None


def test_status_for_category_reflects_current_spend(db_session):
    set_budget(db_session, "food", 30000)
    _add_expense(db_session, 10000, datetime(2026, 8, 1, 9, 0), "food")

    by_date = build_daily_totals(db_session)
    status = status_for_category(db_session, by_date, "food", today=date(2026, 8, 1))

    assert status.spent_cents == 10000
    assert status.budget_cents == 30000
