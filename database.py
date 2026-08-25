"""
Database models and setup for Spending Tracker
"""

import glob
import os
import shutil
from sqlalchemy import create_engine, Column, Integer, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import get_database_url, Config

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
BACKUPS_TO_KEEP = 14

DATABASE_URL = get_database_url()
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

_SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

LIVE_DB_ENV_VAR = "SPENDING_BOT_ALLOW_LIVE_DB"


def SessionLocal():
    """
    Open a session against the live spending.db.

    Requires the SPENDING_BOT_ALLOW_LIVE_DB env var to be set - main.py and
    export_stats.py both set it automatically before importing anything
    else, so normal operation is unaffected. This guard exists to stop an
    ad-hoc/debug script from accidentally running a destructive query
    against real logged expenses (same pattern as chores-assistant and
    wake-work-sleep-logger, both bitten by exactly this before). If you're
    deliberately making a targeted, one-off fix to production data, set the
    env var explicitly right in that command - that makes the intent
    visible instead of implicit. For anything exploratory or destructive,
    use an isolated database instead (see tests/conftest.py's db_session
    fixture).
    """
    if not os.environ.get(LIVE_DB_ENV_VAR):
        raise RuntimeError(
            f"Refusing to open a session against the live spending.db: "
            f"{LIVE_DB_ENV_VAR} is not set. If this is a deliberate, "
            f"targeted fix to production data, set {LIVE_DB_ENV_VAR}=1 "
            f"explicitly. For testing/exploration, use an isolated "
            f"database instead - never the live one."
        )
    return _SessionFactory()


Base = declarative_base()


class Expense(Base):
    """One logged purchase"""
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    # Stored as integer cents, never float - summing floating point dollar
    # amounts across hundreds of entries drifts by real cents. Parsed via
    # Decimal in message_parser.parse_expense, formatted back to "$X.XX"
    # via stats.format_cents.
    amount_cents = Column(Integer, nullable=False)
    note = Column(Text, nullable=False, default="")
    timestamp = Column(DateTime, nullable=False, default=Config.now, index=True)
    raw_message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=Config.now)

    def __repr__(self):
        return f"<Expense id={self.id} amount_cents={self.amount_cents} timestamp={self.timestamp}>"


def backup_database():
    """
    Copy the SQLite database file into backups/ before touching it further.
    A no-op for non-SQLite databases or if the file doesn't exist yet (first run).
    Keeps only the most recent BACKUPS_TO_KEEP backups.
    """
    if not DATABASE_URL.startswith("sqlite:///"):
        return

    db_path = DATABASE_URL.removeprefix("sqlite:///")
    if not os.path.exists(db_path):
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = Config.now().strftime("%Y%m%d_%H%M%S")
    db_name = os.path.splitext(os.path.basename(db_path))[0]
    backup_path = os.path.join(BACKUP_DIR, f"{db_name}_{timestamp}.db")
    shutil.copy2(db_path, backup_path)

    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, f"{db_name}_*.db")))
    for stale_backup in backups[:-BACKUPS_TO_KEEP]:
        os.remove(stale_backup)


def init_db():
    """Initialize database tables"""
    backup_database()
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault(LIVE_DB_ENV_VAR, "1")
    init_db()
