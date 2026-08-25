import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from message_parser import parse_expense


@pytest.mark.parametrize("text,expected_cents,expected_note", [
    ("$12 lunch", 1200, "lunch"),
    ("$12.50 lunch", 1250, "lunch"),
    ("$45.50 gas at Shell", 4550, "gas at Shell"),
    ("$8.99", 899, ""),
    ("  $8.99  ", 899, ""),
    ("$1,200 rent", 120000, "rent"),
    ("$0.50 candy", 50, "candy"),
    ("$12.5 lunch", 1250, "lunch"),  # single decimal digit
])
def test_parse_expense_recognized(text, expected_cents, expected_note):
    result = parse_expense(text)
    assert result == (expected_cents, expected_note)


@pytest.mark.parametrize("text", [
    "lunch $12",       # amount not first
    "12 lunch",        # missing $
    "$0 free sample",  # zero amount
    "$-5 refund",      # negative amount
    "$abc lunch",      # not a number
    "",
    "just chatting",
])
def test_parse_expense_unrecognized_returns_none(text):
    assert parse_expense(text) is None
