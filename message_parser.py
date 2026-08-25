"""
Free-text -> (amount_cents, item, category) parsing for incoming Telegram
messages.

Expected format: "$<amount>, <item>, <category>" - comma-separated so item
and category can each be multiple words without ambiguity (categories are
user-defined on the fly, not a fixed list, so they can't be pinned to a
single trailing word the way the exact-phrase sibling projects do).
Category is optional; when omitted the entry files under "uncategorized".
Amount is parsed with Decimal, never float, and converted to integer cents.

Because comma is the field delimiter, the amount itself can't use a comma
as a thousands separator (e.g. "$1,200, rent, bills" would be ambiguous
with the delimiter) - write large amounts as "$1200" instead.
"""

import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from database import UNCATEGORIZED

_AMOUNT_RE = re.compile(r"^\$\s*(\d+(?:\.\d{1,2})?)$")


def parse_expense(text: str) -> tuple[int, str, str] | None:
    """Return (amount_cents, item, category) or None if text isn't a
    recognized "$<amount>, <item>[, <category>]" expense message."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return None

    match = _AMOUNT_RE.match(parts[0])
    if not match:
        return None

    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    cents = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))

    item = parts[1]
    if not item:
        return None

    # Anything past the 2nd comma is folded into category - a category
    # with its own comma in it is an edge case, not a parse error.
    category = ",".join(parts[2:]).strip().lower() if len(parts) >= 3 else ""
    category = category or UNCATEGORIZED

    return cents, item, category
