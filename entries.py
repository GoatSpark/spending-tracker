"""
Lookup/delete/edit operations on the most recently logged expenses, used by
the /recent, /delete, and /edit commands. Indexes are always 1-based and
re-derived fresh from the DB on every call (1 = most recent) - there's no
persisted "last shown list", so if a new expense gets logged between
/recent and /delete, the numbering reflects the current most-recent
entries, not a stale snapshot from an earlier /recent call.
"""

from dataclasses import dataclass
from datetime import datetime

from database import Expense

RECENT_LIMIT = 3


@dataclass
class EntrySnapshot:
    """Plain-value copy of an Expense's display fields, taken before a
    delete/edit commits. Reading ORM attributes off a deleted instance
    after commit raises (SQLAlchemy expires instances on commit and tries
    to re-fetch a row that's now gone), so callers that need to show what
    changed capture the values first and return this instead of the ORM
    object."""
    amount_cents: int
    item: str
    category: str
    timestamp: datetime


def _snapshot(expense: Expense) -> EntrySnapshot:
    return EntrySnapshot(expense.amount_cents, expense.item, expense.category, expense.timestamp)


def get_recent(db, limit: int = RECENT_LIMIT) -> list[Expense]:
    """Most recent expenses, newest first."""
    return db.query(Expense).order_by(Expense.timestamp.desc(), Expense.id.desc()).limit(limit).all()


def delete_recent(db, index: int) -> EntrySnapshot | None:
    """Delete the `index`-th (1-based, 1=most recent) of the recent
    expenses. Returns a snapshot of what was deleted, or None if index is
    out of range (including "no expenses logged at all")."""
    recent = get_recent(db)
    if not (1 <= index <= len(recent)):
        return None
    target = recent[index - 1]
    snapshot = _snapshot(target)
    db.delete(target)
    db.commit()
    return snapshot


def edit_recent(db, index: int, amount_cents: int, item: str, category: str) -> EntrySnapshot | None:
    """Overwrite the `index`-th (1-based) recent expense's amount/item/
    category in place - timestamp is left untouched, since this corrects
    what was logged, not when it happened. Returns a snapshot of the
    updated entry, or None if index is out of range."""
    recent = get_recent(db)
    if not (1 <= index <= len(recent)):
        return None
    target = recent[index - 1]
    target.amount_cents = amount_cents
    target.item = item
    target.category = category
    snapshot = EntrySnapshot(amount_cents, item, category, target.timestamp)
    db.commit()
    return snapshot
