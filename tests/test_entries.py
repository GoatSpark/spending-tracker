import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Expense
from entries import get_recent, delete_recent, edit_recent, RECENT_LIMIT


def _add_expense(db, cents, dt, item, category="misc"):
    expense = Expense(amount_cents=cents, item=item, category=category, timestamp=dt, raw_message="test")
    db.add(expense)
    db.commit()
    return expense


def test_get_recent_returns_newest_first_limited_to_three(db_session):
    for i in range(5):
        _add_expense(db_session, 100 * (i + 1), datetime(2026, 8, 1 + i, 9, 0), item=f"item{i}")

    recent = get_recent(db_session)

    assert len(recent) == RECENT_LIMIT
    assert [e.item for e in recent] == ["item4", "item3", "item2"]


def test_get_recent_empty_when_no_expenses(db_session):
    assert get_recent(db_session) == []


def test_delete_recent_removes_the_right_entry_and_returns_snapshot(db_session):
    _add_expense(db_session, 100, datetime(2026, 8, 1, 9, 0), item="oldest")
    _add_expense(db_session, 200, datetime(2026, 8, 2, 9, 0), item="middle")
    _add_expense(db_session, 300, datetime(2026, 8, 3, 9, 0), item="newest")

    deleted = delete_recent(db_session, 2)  # "middle" - index 2 of [newest, middle, oldest]

    assert deleted.item == "middle"
    assert deleted.amount_cents == 200
    remaining_items = {e.item for e in db_session.query(Expense).all()}
    assert remaining_items == {"oldest", "newest"}


def test_delete_recent_out_of_range_returns_none_and_deletes_nothing(db_session):
    _add_expense(db_session, 100, datetime(2026, 8, 1, 9, 0), item="only")

    assert delete_recent(db_session, 2) is None
    assert delete_recent(db_session, 0) is None
    assert db_session.query(Expense).count() == 1


def test_delete_recent_on_empty_db_returns_none(db_session):
    assert delete_recent(db_session, 1) is None


def test_edit_recent_overwrites_fields_and_preserves_timestamp(db_session):
    original = _add_expense(db_session, 100, datetime(2026, 8, 1, 9, 30), item="old item", category="old cat")
    original_timestamp = original.timestamp

    updated = edit_recent(db_session, 1, amount_cents=999, item="new item", category="new cat")

    assert updated.amount_cents == 999
    assert updated.item == "new item"
    assert updated.category == "new cat"
    assert updated.timestamp == original_timestamp

    row = db_session.query(Expense).one()
    assert row.amount_cents == 999
    assert row.item == "new item"
    assert row.category == "new cat"
    assert row.timestamp == original_timestamp


def test_edit_recent_out_of_range_returns_none(db_session):
    _add_expense(db_session, 100, datetime(2026, 8, 1, 9, 0), item="only")
    assert edit_recent(db_session, 5, amount_cents=1, item="x", category="y") is None
