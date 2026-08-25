"""
Free-text parsing for incoming Telegram messages: logging an expense
("$<amount>, <item>[, <category>]") and setting a budget
("<category> $<amount>").

Expense format is comma-separated so item and category can each be
multiple words without ambiguity (categories are user-defined on the fly,
not a fixed list, so they can't be pinned to a single trailing word the way
the exact-phrase sibling projects do). Category is optional; when omitted
the entry files under "uncategorized". Amounts are parsed with Decimal,
never float, and converted to integer cents.

Because comma is the expense format's field delimiter, the amount itself
can't use a comma as a thousands separator (e.g. "$1,200, rent, bills"
would be ambiguous with the delimiter) - write large amounts as "$1200"
instead.
"""

import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from database import UNCATEGORIZED

_AMOUNT_RE = re.compile(r"^\$\s*(\d+(?:\.\d{1,2})?)$")
_AMOUNT_SEARCH_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")


def _to_cents(amount_str: str) -> int | None:
    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def parse_expense(text: str) -> tuple[int, str, str] | None:
    """Return (amount_cents, item, category) or None if text isn't a
    recognized "$<amount>, <item>[, <category>]" expense message."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return None

    match = _AMOUNT_RE.match(parts[0])
    if not match:
        return None

    cents = _to_cents(match.group(1))
    if not cents:  # None, or zero/negative amount - a real expense must be > 0
        return None

    item = parts[1]
    if not item:
        return None

    # Anything past the 2nd comma is folded into category - a category
    # with its own comma in it is an edge case, not a parse error.
    category = ",".join(parts[2:]).strip().lower() if len(parts) >= 3 else ""
    category = category or UNCATEGORIZED

    return cents, item, category


def parse_budget_command(text: str) -> tuple[str, int] | None:
    """Return (category, amount_cents) from free-form "<category> $<amount>"
    text (the amount can appear anywhere - "food $300" and "$300 food" both
    work). Returns None if there's no dollar amount or no category text left
    once the amount is removed. A $0 amount is valid here (unlike
    parse_expense) - it's how /budget clears an existing budget."""
    match = _AMOUNT_SEARCH_RE.search(text)
    if not match:
        return None

    cents = _to_cents(match.group(1))
    if cents is None:
        return None

    category = (text[:match.start()] + text[match.end():]).strip(" ,").lower()
    if not category:
        return None

    return category, cents
