"""
Telegram bot command/message handlers
"""

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database import Expense, SessionLocal
from message_parser import parse_expense
from stats import format_cents, range_stats, build_daily_totals

RANGE_ORDER = ["week", "month", "quarter", "year"]
RANGE_TITLES = {
    "week": "Last 7 days",
    "month": "Last 30 days",
    "quarter": "Last 90 days",
    "year": "Last 365 days",
}


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
            f"Log a purchase by sending its amount, then an optional note:\n"
            f"  $12 lunch\n"
            f"  $45.50 gas\n"
            f"  $8.99\n\n"
            f"Commands:\n"
            f"  /stats - View totals, average per day, and largest purchase\n"
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

        await update.message.reply_text("\n".join(lines).strip())

    @staticmethod
    def _log_expense(amount_cents: int, note: str, raw_message: str) -> None:
        db = SessionLocal()
        try:
            db.add(Expense(
                amount_cents=amount_cents,
                note=note,
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
                "\"$12 lunch\" - amount first (with a $), then an optional note."
            )
            return

        amount_cents, note = parsed
        TelegramHandler._log_expense(amount_cents, note, text)

        note_suffix = f" — {note}" if note else ""
        await update.message.reply_text(f"Logged: {format_cents(amount_cents)}{note_suffix}")
