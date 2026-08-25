import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from database import UNCATEGORIZED
from message_parser import parse_expense


@pytest.mark.parametrize("text,expected_cents,expected_item,expected_category", [
    ("$12, lunch, food", 1200, "lunch", "food"),
    ("$12.50, lunch, food", 1250, "lunch", "food"),
    ("$45.50, gas, transportation", 4550, "gas", "transportation"),
    ("$8.99, latte", 899, "latte", UNCATEGORIZED),
    ("  $8.99 ,  latte  ", 899, "latte", UNCATEGORIZED),
    ("$0.50, candy, treats", 50, "candy", "treats"),
    ("$12.5, lunch, Food", 1250, "lunch", "food"),  # category lowercased
    ("$12, lunch at Chipotle, fast food", 1200, "lunch at Chipotle", "fast food"),  # multi-word item/category
])
def test_parse_expense_recognized(text, expected_cents, expected_item, expected_category):
    result = parse_expense(text)
    assert result == (expected_cents, expected_item, expected_category)


@pytest.mark.parametrize("text", [
    "$12 lunch food",   # no commas at all
    "$12",               # amount only, no item
    "$0, lunch, food",   # zero amount
    "$-5, refund, misc", # negative amount
    "$abc, lunch, food", # not a number
    "lunch, $12, food",  # amount not first
    "",
    "just chatting",
])
def test_parse_expense_unrecognized_returns_none(text):
    assert parse_expense(text) is None


def test_comma_thousands_separator_collides_with_delimiter():
    # Documented limitation (see message_parser's module docstring): a
    # comma inside the amount is indistinguishable from the field
    # delimiter, so it silently misparses rather than being rejected.
    # Large amounts must be written without a thousands separator.
    assert parse_expense("$1,200, rent, bills") == (100, "200", "rent,bills")
    assert parse_expense("$1200, rent, bills") == (120000, "rent", "bills")
