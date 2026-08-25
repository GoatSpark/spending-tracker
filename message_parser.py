"""
Free-text -> (amount_cents, note) parsing for incoming Telegram messages.

Expected format: "$<amount> <note>", e.g. "$12 lunch" or "$45.50 gas at
Shell". The note is optional ("$8.99" alone is valid). Amount is parsed with
Decimal, never float, and converted to integer cents - summing dollar
amounts as float across many entries drifts by real cents over time.
"""

import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

_AMOUNT_RE = re.compile(r"^\$\s*([\d,]+(?:\.\d{1,2})?)\s*(.*)$", re.DOTALL)


def parse_expense(text: str) -> tuple[int, str] | None:
    """Return (amount_cents, note) or None if text isn't a recognized
    "$<amount> <note>" expense message."""
    match = _AMOUNT_RE.match(text.strip())
    if not match:
        return None

    amount_str = match.group(1).replace(",", "")
    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        return None
    if amount <= 0:
        return None

    cents = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
    note = match.group(2).strip()
    return cents, note
