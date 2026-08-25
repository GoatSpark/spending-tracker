# Spending Tracker — Project Steering File

A personal Telegram bot that logs misc. spending - amount + an optional
free-text note, e.g. "$12 lunch" - plus a static GitHub Pages dashboard
showing total/average/largest spend over week/month/quarter/year. Single
user, SQLite-backed, runs as a long-lived polling process (`python
main.py`). Same overall shape as the sibling [[chores-assistant]] and
[[wake-work-sleep-logger]] projects, adapted for money instead of
categories/timestamps.

## Architecture

```
main.py                 Entry point. Builds the python-telegram-bot Application,
                         registers handlers, runs polling.
config.py                Env var loading (.env via python-dotenv) + Config.now()
database.py              SQLAlchemy Expense model + backup_database()
message_parser.py        Parses "$<amount> <note>" into (amount_cents, note)
telegram_handler.py      /start, /help, /stats, and free-text message handling
stats.py                 Per-day aggregation + total/avg/largest/smallest over a range
export_stats.py          Dumps docs/data.json for the GitHub Pages dashboard
docs/index.html           Static dashboard (fetches data.json client-side, no build step)
scripts/export_and_push.sh    Runs export_stats.py, commits+pushes docs/data.json if changed
scripts/manual_smoke_test.py  Sends a real Telegram message via the live bot for manual checks
tests/                   pytest suite, isolated in-memory DB (conftest.py fixture)
```

Message flow: an incoming Telegram text message -> `message_parser.
parse_expense` (regex: a leading `$`, an amount, then everything else is
the note) -> if it parses, an `Expense(amount_cents, note, timestamp=
Config.now())` is inserted and the bot replies with a confirmation; if it
doesn't parse (no `$`, non-numeric amount, zero/negative amount), the bot
asks the user to check the format rather than silently dropping the
message.

## Key conventions

- **Money is stored as integer cents, never float.** `Expense.amount_cents`
  is an `Integer`. `message_parser.parse_expense` uses `decimal.Decimal` to
  parse the dollar string, then rounds to the nearest cent
  (`ROUND_HALF_UP`) and converts to int - summing floating-point dollar
  amounts across hundreds of entries drifts by real cents, which matters
  more here than it would have for the timestamp-only sibling projects.
  `stats.format_cents` is the only place that converts back to a display
  string (`$1,234.56`); nothing else should do `cents / 100` and expect a
  precise dollar value out the other end.
- **No expense categories** - this was a deliberate scope decision (the
  user chose "no categories, just totals + notes" over a fixed category
  list like chores-assistant's chore types or a hypothetical category
  enum here). `stats.py` and the dashboard only ever report totals/
  averages/largest/smallest, never a by-category breakdown. If categories
  get added later, that's a real schema change (a `category` column plus
  either a fixed enum or free-text tagging), not just a display tweak -
  revisit `message_parser.parse_expense`'s regex too, since right now
  everything after the amount is swallowed as one opaque `note`.
- **All datetimes are naive local time, always.** Same reasoning as the
  sibling projects: SQLite drops tzinfo on round-trip, so the whole app
  standardizes on naive local datetimes. Use `Config.now()`, never
  `datetime.now()`.
- **Never hardcode secrets** (bot token, GitHub deploy key) outside `.env`
  and `~/.ssh/`. `.env` is gitignored.
- **Never run ad-hoc scripts against the live `spending.db`.**
  `database.SessionLocal()` refuses to open unless `SPENDING_BOT_ALLOW_
  LIVE_DB` is set (`main.py` and `export_stats.py` set it automatically).
  A deliberate one-off production fix should set that env var explicitly
  in the command itself. `init_db()` backs up `spending.db` into
  `backups/` (keeps last 14) on every bot startup as a second line of
  defense. Same guard-rail pattern as chores-assistant and
  wake-work-sleep-logger - copied up front instead of waiting to repeat
  the mistake that motivated it there.
- **Average-per-day divides by the fixed range length, not by days with
  data.** `stats.range_stats`'s `avg_per_day_cents` for "week" is always
  `total / 7`, even if you only logged on 3 of those days - it reads as
  an actual daily spending rate ("you're averaging $X/day this month"),
  not something that jumps around based on logging frequency. The
  dashboard's "all" tab is the one exception - there's no fixed range
  length for "all time", so it divides by the number of days that
  actually have data instead (see `computeStats` in `docs/index.html`).
- **The bot restricts itself to `TELEGRAM_USER_ID` once configured**,
  same as wake-work-sleep-logger - optional at first boot (unset =
  accept from anyone) so `/start` can reveal the ID to put in `.env`.

## The GitHub Pages data pipeline

Same push-from-server design as wake-work-sleep-logger, because the
constraint is identical: the bot's DB lives on a home server with no
public inbound access, so a static dashboard can only ever pull a file
the server already pushed somewhere public.

```
Linux box (systemd timer, every 15 min)
  -> scripts/export_and_push.sh
       -> export_stats.py reads spending.db, writes docs/data.json
       -> git commit + git push (only if data.json changed)
  -> GitHub Pages redeploys docs/ automatically on push to main
```

- The repo (`GoatSpark/spending-tracker`) is **public**, same choice as
  wake-work-sleep-logger - the user was comfortable with spend *amounts*
  and notes being publicly visible (no account/merchant/card details are
  ever collected in the first place, so there's nothing more sensitive
  than the note text to weigh).
- Push auth uses a **dedicated deploy key**
  (`~/.ssh/spending_tracker_deploy` on the Linux box, distinct from
  wake-work-sleep-logger's own key), added to this repo only with write
  access - not a personal access token. The `origin` remote URL uses the
  `github-spend` alias in `~/.ssh/config`, so plain `git push origin`
  "just works" without extra flags.
- `export_stats.py` only writes JSON - it never touches git, same
  separation of concerns as the sibling project.
- `docs/data.json`'s per-day rows are `{date, total_cents, count,
  max_cents, min_cents}` - enough for the dashboard to compute total/avg/
  largest/smallest for any selected range client-side without needing
  every individual transaction (which would also leak note text per-
  transaction into the public JSON - the per-day rollup deliberately
  keeps notes off the public dashboard entirely).

## Running the bot / working preferences

Lives on the same always-on Linux box as chores-assistant and
wake-work-sleep-logger (Ubuntu 24.04, `192.168.0.44`, user `plexbot2`) at
`/home/plexbot2/dev/spending-tracker`, also reachable from Windows at
`\\192.168.0.44\claudeshare\spending-tracker` (same files). Runs as a
systemd **user** service, same lingering setup as the sibling projects.

```bash
# Bot service
systemctl --user status spending-tracker.service
systemctl --user restart spending-tracker.service   # after a code change
journalctl --user -u spending-tracker.service -n 100 --no-pager

# Export/push timer (updates the public dashboard)
systemctl --user status spending-tracker-export.timer
systemctl --user start spending-tracker-export.service   # force a push now
journalctl --user -u spending-tracker-export.service -n 50 --no-pager
```

- venv is Linux-native at `/home/plexbot2/dev/spending-tracker/venv`
  (`python3 -m venv`, Python 3.12.3) - a venv never survives a cross-OS
  move, always recreate at the destination if this project ever gets
  copied elsewhere.
- **Claude cannot simulate a live end-to-end test of the running bot** -
  confirmed on both sibling projects, a bot's own `sendMessage` calls
  never come back through `getUpdates`. Verifying the actual live bot
  requires the user to send a real message from their Telegram client.
  `pytest` and direct `message_parser`/`stats` calls in isolation are how
  Claude verifies logic changes; `scripts/manual_smoke_test.py` is an
  opt-in manual round-trip prompt, not an automated test.
