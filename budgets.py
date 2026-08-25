"""
Per-category budget limits and month-to-date status against them.

A budget is a monthly (trailing-30-day, same "month" as stats.py uses
everywhere else) spending cap for one category. Setting a budget with a
$0 amount clears it - there's no separate "delete" command, since $0 isn't
a meaningful budget on its own and this keeps /budget as the one command
that both sets and clears.
"""

from dataclasses import dataclass
from datetime import date

from database import Budget
from stats import RANGE_MONTH, category_breakdown

# Warn once spending crosses this fraction of the budget, even if not yet
# over it - catching it at 80% is more useful than only finding out at 100%.
WARNING_THRESHOLD = 0.8


@dataclass
class BudgetStatus:
    category: str
    budget_cents: int
    spent_cents: int

    @property
    def pct_used(self) -> float:
        return self.spent_cents / self.budget_cents if self.budget_cents else 0.0

    @property
    def remaining_cents(self) -> int:
        return self.budget_cents - self.spent_cents

    @property
    def is_over(self) -> bool:
        return self.spent_cents > self.budget_cents

    @property
    def is_near(self) -> bool:
        return not self.is_over and self.pct_used >= WARNING_THRESHOLD


def set_budget(db, category: str, amount_cents: int) -> Budget | None:
    """Create or update the budget for `category`. A $0 amount deletes the
    budget instead (see module docstring) and this returns None in that
    case; otherwise returns the created/updated Budget."""
    existing = db.query(Budget).filter(Budget.category == category).one_or_none()

    if amount_cents == 0:
        if existing is not None:
            db.delete(existing)
            db.commit()
        return None

    if existing is not None:
        existing.amount_cents = amount_cents
        db.commit()
        return existing

    budget = Budget(category=category, amount_cents=amount_cents)
    db.add(budget)
    db.commit()
    return budget


def list_budgets(db) -> list[Budget]:
    return db.query(Budget).order_by(Budget.category.asc()).all()


def budget_status(db, by_date: dict, today: date | None = None) -> list[BudgetStatus]:
    """Month-to-date status for every set budget, most-used first."""
    spent_by_category = category_breakdown(by_date, RANGE_MONTH, today=today)
    statuses = [
        BudgetStatus(
            category=budget.category,
            budget_cents=budget.amount_cents,
            spent_cents=spent_by_category.get(budget.category, 0),
        )
        for budget in list_budgets(db)
    ]
    return sorted(statuses, key=lambda s: s.pct_used, reverse=True)


def status_for_category(db, by_date: dict, category: str, today: date | None = None) -> BudgetStatus | None:
    """Month-to-date status for one category, or None if it has no budget set."""
    budget = db.query(Budget).filter(Budget.category == category).one_or_none()
    if budget is None:
        return None
    spent_by_category = category_breakdown(by_date, RANGE_MONTH, today=today)
    return BudgetStatus(
        category=category,
        budget_cents=budget.amount_cents,
        spent_cents=spent_by_category.get(category, 0),
    )
