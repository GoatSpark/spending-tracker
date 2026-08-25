"""
Telegram bot command/message handlers
"""

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database import Expense, SessionLocal
from entries import RECENT_LIMIT, delete_recent, edit_recent, get_recent
from message_parser import parse_expense
from stats import category_breakdown, format_cents, range_stats, spend_rate_stats, build_daily_totals

RANGE_ORDER = ["week", "month", "quarter", "year"]
RANGE_TITLES = {
    "week": "Last 7 days",
    "month": "Last 30 days",
    "quarter": "Last 90 days",
    "year": "Last 365 days",
}
TOP_CATEGORIES_LIMIT = 5


class TelegramHandler:
    """Handle Telegram bot interactions"""

    @staticmethod
    def _is_authorized(update: Update) -> bool:
        if Config.TELEGRAM_USER_ID is None:
            return True
        return update.effective_user.id == Config.TELEGRAM_USER_ID

    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        await update.message.reply_text(
            f"\U0001F4B0 Welcome to Spending Tracker!\n\n"
            f"Your Telegram ID: {user_id}\n\n"
            f"Add this to your .env file as TELEGRAM_USER_ID so only you "
            f"can log expenses, then restart the bot.\n\n"
            f"Log a purchase with amount, item, and category (comma-"
            f"separated) - category is optional and files under "
            f"\"uncategorized\" if left out. Categories are whatever you "
            f"type, on the fly - there's no fixed list:\n"
            f"  $12, lunch, food\n"
            f"  $45.50, gas, transportation\n"
            f"  $8.99, latte\n\n"
            f"Commands:\n"
            f"  /stats - View totals, average per day, largest purchase, and top categories\n"
            f"  /recent - Show the last {RECENT_LIMIT} entries, numbered\n"
            f"  /delete <n> - Delete entry n from /recent\n"
            f"  /edit <n> $amount, item, category - Overwrite entry n\n"
            f"  /help - Show this message"
        )

    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await TelegramHandler.start(update, context)

    @staticmethod
    async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not TelegramHandler._is_authorized(update):
            return

        db = SessionLocal()
        try:
            by_date = build_daily_totals(db)
        finally:
            db.close()

        if not by_date:
            await update.message.reply_text("No expenses logged yet.")
            return

        lines = []

        week_total = range_stats(by_date, "week")
        month_total = range_stats(by_date, "month")
        quarter_total = range_stats(by_date, "quarter")
        lines.append("\U0001F4B0 Total spent")
        lines.append(f"  Last 7 days: {format_cents(week_total['total_cents']) if week_total else '$0.00'}")
        lines.append(f"  Last 30 days: {format_cents(month_total['total_cents']) if month_total else '$0.00'}")
        lines.append(f"  Last 90 days: {format_cents(quarter_total['total_cents']) if quarter_total else '$0.00'}")
        lines.append("")

        rate = spend_rate_stats(by_date)
        lines.append("\U0001F4C8 Average spend rate (based on the last year)")
        if rate is None:
            lines.append("  No data")
        else:
            lines.append(f"  Weekly: {format_cents(rate['weekly_cents'])}")
            lines.append(f"  Monthly: {format_cents(rate['monthly_cents'])}")
            lines.append(f"  Quarterly: {format_cents(rate['quarterly_cents'])}")
        lines.append("")

        for range_name in RANGE_ORDER:
            stats = range_stats(by_date, range_name)
            lines.append(f"\U0001F4B0 {RANGE_TITLES[range_name]}")
            if stats is None:
                lines.append("  No data")
            else:
                lines.append(
                    f"  Total: {format_cents(stats['total_cents'])}  "
                    f"(avg {format_cents(stats['avg_per_day_cents'])}/day, n={stats['count']})"
                )
                lines.append(
                    f"  Largest: {format_cents(stats['largest_cents'])}  "
                    f"Smallest: {format_cents(stats['smallest_cents'])}"
                )
            lines.append("")

        categories = category_breakdown(by_date, "month")
        lines.append("\U0001F3F7 Top categories (last 30 days)")
        if not categories:
            lines.append("  No data")
        else:
            for category, cents in list(categories.items())[:TOP_CATEGORIES_LIMIT]:
                lines.append(f"  {category}: {format_cents(cents)}")
            remaining = len(categories) - TOP_CATEGORIES_LIMIT
            if remaining > 0:
                lines.append(f"  ...and {remaining} more")

        await update.message.reply_text("\n".join(lines).strip())

    @staticmethod
    async def show_recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not TelegramHandler._is_authorized(update):
            return

        db = SessionLocal()
        try:
            recent = get_recent(db)
        finally:
            db.close()

        if not recent:
            await update.message.reply_text("No expenses logged yet.")
            return

        lines = ["Last entries:"]
        for i, expense in enumerate(recent, start=1):
            when = expense.timestamp.strftime("%b %-d, %-I:%M %p")
            lines.append(
                f"{i}. {format_cents(expense.amount_cents)} — "
                f"{expense.item} [{expense.category}]  ({when})"
            )
        lines.append("")
        lines.append("/delete <n> to remove one, /edit <n> $amount, item, category to fix one")

        await update.message.reply_text("\n".join(lines))

    @staticmethod
    async def delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not TelegramHandler._is_authorized(update):
            return

        parts = (update.message.text or "").split(None, 1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            await update.message.reply_text(f"Usage: /delete <n> - n is 1-{RECENT_LIMIT} from /recent")
            return
        index = int(parts[1].strip())

        db = SessionLocal()
        try:
            deleted = delete_recent(db, index)
        finally:
            db.close()

        if deleted is None:
            await update.message.reply_text(f"No entry #{index} - check /recent for the current list.")
            return

        await update.message.reply_text(
            f"Deleted: {format_cents(deleted.amount_cents)} — {deleted.item} [{deleted.category}]"
        )

    @staticmethod
    async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not TelegramHandler._is_authorized(update):
            return

        parts = (update.message.text or "").split(None, 2)
        if len(parts) < 3 or not parts[1].strip().isdigit():
            await update.message.reply_text(
                f"Usage: /edit <n> $amount, item, category - n is 1-{RECENT_LIMIT} from /recent"
            )
            return
        index = int(parts[1].strip())

        parsed = parse_expense(parts[2].strip())
        if parsed is None:
            await update.message.reply_text(
                "That doesn't look like \"$amount, item, category\" - check the format."
            )
            return
        amount_cents, item, category = parsed

        db = SessionLocal()
        try:
            updated = edit_recent(db, index, amount_cents, item, category)
        finally:
            db.close()

        if updated is None:
            await update.message.reply_text(f"No entry #{index} - check /recent for the current list.")
            return

        await update.message.reply_text(
            f"Updated #{index}: {format_cents(updated.amount_cents)} — {updated.item} [{updated.category}]"
        )

    @staticmethod
    def _log_expense(amount_cents: int, item: str, category: str, raw_message: str) -> None:
        db = SessionLocal()
        try:
            db.add(Expense(
                amount_cents=amount_cents,
                item=item,
                category=category,
                timestamp=Config.now(),
                raw_message=raw_message,
            ))
            db.commit()
        finally:
            db.close()

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not TelegramHandler._is_authorized(update):
            await update.message.reply_text(
                "This bot is private and isn't set up to log expenses for you."
            )
            return

        text = update.message.text or ""
        parsed = parse_expense(text)

        if parsed is None:
            await update.message.reply_text(
                "I didn't recognize that as an expense. Send it like "
                "\"$12, lunch, food\" - amount, item, and an optional "
                "category, comma-separated."
            )
            return

        amount_cents, item, category = parsed
        TelegramHandler._log_expense(amount_cents, item, category, text)

        await update.message.reply_text(
            f"Logged: {format_cents(amount_cents)} — {item} [{category}]"
        )
