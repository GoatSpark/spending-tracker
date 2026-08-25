# Spending Tracker — Project Steering File

A personal Telegram bot that logs misc. spending - amount, item, and a
user-defined category, e.g. "$12, lunch, food" - plus a static GitHub Pages
dashboard showing total/average/largest spend and a by-category breakdown
over week/month/quarter/year. Also supports per-category monthly budgets
with warnings at log time (`/budget`, `/budgets`) - see "Budgets" below.
Single user, SQLite-backed, runs as a long-lived polling process (`python
main.py`). Same overall shape as the sibling [[chores-assistant]] and
[[wake-work-sleep-logger]] projects, adapted for money instead of
chores/timestamps.

## Architecture

```
main.py                 Entry point. Builds the python-telegram-bot Application,
                         registers handlers, runs polling.
config.py                Env var loading (.env via python-dotenv) + Config.now()
database.py              SQLAlchemy Expense model + backup_database()
message_parser.py        Parses "$<amount>, <item>[, <category>]" into (cents, item, category)
entries.py               Lookup/delete/edit the most recent N expenses, by 1-based index
budgets.py               Set/list/clear per-category budgets + month-to-date status against them
telegram_handler.py      /start, /help, /stats, /recent, /delete, /edit, /budget, /budgets, message handling
stats.py                 Per-day aggregation + totals/averages/category breakdown over a range
export_stats.py          Dumps docs/data.json for the GitHub Pages dashboard
docs/index.html           Static dashboard (fetches data.json client-side, no build step)
scripts/export_and_push.sh    Runs export_stats.py, commits+pushes docs/data.json if changed
scripts/manual_smoke_test.py  Sends a real Telegram message via the live bot for manual checks
tests/                   pytest suite, isolated in-memory DB (conftest.py fixture)
RESEARCH.md              Competitive research on other manual/no-bank-link expense trackers -
                         the basis for choosing budgets as the highest-impact feature to add
```

Message flow: an incoming Telegram text message -> `message_parser.
parse_expense` (comma-separated: a leading `$<amount>`, then `<item>`,
then an optional `<category>` - anything past the 2nd comma folds into
category) -> if it parses, an `Expense(amount_cents, item, category,
timestamp=Config.now())` is inserted and the bot replies with a
confirmation; if it doesn't parse (no `$`, missing item, non-numeric or
zero/negative amount), the bot asks the user to check the format rather
than silently dropping the message.

**This format changed mid-project** (see "How the schema evolved" below) -
the very first version only asked for amount + a free-text note, no
category, space-separated (`"$12 lunch"`). If you see that format anywhere
in old notes/history, it's superseded.

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
- **Categories are free-form, not a fixed list.** The user defines a
  category per-message, on the fly ("$12, lunch, food" this time, "$12,
  lunch, dining out" next time would be a *different* category - there's
  no enum or autocomplete). `message_parser.parse_expense` lowercases and
  strips the category so casing doesn't fragment it ("Food" and "food"
  land in the same bucket), but a typo or a differently-worded category
  still creates a new bucket - that's accepted as inherent to "on the fly"
  categorization, not a bug to fix with fuzzy-matching. Omitted category
  files under `database.UNCATEGORIZED` ("uncategorized").
- **Comma is the field delimiter, so it can't also be a thousands
  separator in the amount.** `"$1,200, rent, bills"` silently misparses
  (splits into 4 comma-fields, not 3) rather than being rejected - write
  large amounts as `"$1200"`. This is a real, documented limitation
  (see `message_parser.py`'s module docstring and
  `test_comma_thousands_separator_collides_with_delimiter`), not
  something to "fix" without changing the delimiter scheme entirely.
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
  the mistake that motivated it there. It nonetheless still requires a
  human (or Claude) to remember to back up before a schema migration
  specifically, since `init_db()`'s auto-backup only fires on bot startup,
  not before an ad-hoc migration script - see the Lessons Learned entry
  below, this is exactly what almost got skipped.
- **Average-per-day (in `range_stats`) divides by the fixed range length,
  not by days with data.** `total / 7` for "week", even if you only
  logged on 3 of those days - it reads as an actual daily spending rate,
  not something that jumps around based on logging frequency. The
  dashboard's "all" tab is the one exception - there's no fixed range
  length for "all time", so it divides by the number of days that
  actually have data instead (see `computeStats` in `docs/index.html`).
- **`spend_rate_stats`'s weekly/monthly/quarterly averages are derived
  from the trailing-**year** total** (÷52, ÷12, ÷4), not from each
  range's own total - a single week of data would otherwise make
  "average quarterly spend" swing wildly. This is a *different* number
  from "total spent in the last 7/30/90 days" (which `/stats` also shows,
  separately, unsmoothed) - don't conflate the two or collapse them into
  one number, they answer different questions ("what did I actually
  spend recently" vs "what's my steady-state rate").
- **The bot restricts itself to `TELEGRAM_USER_ID` once configured**,
  same as wake-work-sleep-logger - optional at first boot (unset =
  accept from anyone) so `/start` can reveal the ID to put in `.env`.

## /recent, /delete, /edit - correcting entries after the fact

Added alongside the item/category rework, since typos are a lot costlier
to catch in a spending log than a wake-up time. All three live in
`entries.py` (decoupled from `telegram_handler.py`'s Update/Context
objects, so they're directly unit-testable) and share one convention:

- Indexes are **1-based, 1 = most recent**, and always **re-derived fresh
  from the DB** on every call - there's no server-side "memory" of what
  `/recent` last showed. If you log a new expense between `/recent` and
  `/delete 2`, `#2` now refers to the current 2nd-most-recent entry, not
  whatever was `#2` a message ago. This is a deliberate simplicity choice
  (no per-chat session state to manage) - if it ever causes a "deleted the
  wrong thing" complaint, revisit before adding session state to fix it.
- `entries.delete_recent` and `entries.edit_recent` return an
  `EntrySnapshot` (plain dataclass), not the SQLAlchemy `Expense` object.
  Reading ORM attributes off an instance *after* `db.commit()` triggers a
  refresh query - which raises `ObjectDeletedError` for a just-deleted row.
  Both functions capture the display fields into the snapshot **before**
  `db.commit()` runs, specifically to avoid that.
- `/edit <n> $amount, item, category` reuses `message_parser.parse_expense`
  on everything after the index, so it's the exact same format/validation
  as logging a new expense - no separate parser to keep in sync.
- `/edit` overwrites amount/item/category but **leaves `timestamp`
  untouched** - it's a correction to what was logged, not a re-log at a
  new time. (Contrast with wake-work-sleep-logger's backfill feature,
  which is the opposite case - a new event at a specified past time, not a
  correction to an existing one.)

## Budgets - /budget, /budgets, and log-time warnings

Added after researching three well-known manual/no-bank-link expense apps
(Monefy, Goodbudget, Fudget - see `RESEARCH.md`). The two more full-featured
of the three (Monefy, Goodbudget) converge on the same thing beyond basic
logging: a spending limit per category with a warning as you approach or
cross it. That was the identified gap - this project could review spending
after the fact but had no way to say "you're overspending" *in the
moment* - so it became the #1 feature to add.

- **A budget is a trailing-30-day cap per category** (`database.Budget`,
  one row per category, `category` is `unique`). "Monthly" here means the
  exact same window `stats.RANGE_MONTH` already uses everywhere else as
  "month" - not a calendar month - specifically so budget percentages stay
  consistent with what `/stats`' "Last 30 days" section already shows.
  Don't redefine "month" differently for budgets alone.
- **`/budget <category> $<amount>` both sets and clears** - a `$0` amount
  deletes the budget (`budgets.set_budget` returns `None` in that case).
  There's deliberately no separate `/unbudget` or `/deletebudget` command;
  `parse_budget_command` in `message_parser.py` accepts `$0` explicitly
  (unlike `parse_expense`, which rejects zero/negative amounts as not a
  real purchase).
- **Warning thresholds live in `budgets.WARNING_THRESHOLD` (0.8) and
  `BudgetStatus.is_near`/`is_over`** - "near" is 80-100% and *exclusive* of
  "over" (a category that's over budget is `is_over=True, is_near=False`),
  so a caller only ever needs to check one or the other, not both. Every
  place that displays budget status (`/budgets`, the post-log warning in
  `handle_message`, the dashboard's `renderBudgets`) reimplements the same
  two-state logic independently - if the threshold or semantics change,
  all three need updating together, there's no single shared formatter.
- **The post-log warning only fires at 80%+** - under that, `handle_message`
  adds nothing to the "Logged: ..." reply. This was a deliberate choice to
  avoid alert fatigue; don't make it chattier (e.g. showing budget status
  on every single logged expense) without the user asking for that.
- **`/budgets` and the dashboard's budget list both sort by `pct_used`
  descending** - the most over/closest-to-over category shows first, on
  the theory that's the one you'd actually act on. Keep this sort order in
  sync between the two surfaces if either changes.
- **Budget targets (not just category subtotals) are now part of the
  public `docs/data.json` export** (`export_stats.py`'s `budgets` key).
  This extends the pre-existing "aggregates are public, individual
  transactions are private" line from the data-pipeline section below - a
  target number like "food budget: $300/month" is the same kind of
  aggregate the category subtotals already are, not a new category of
  exposure. If a future feature wanted to publish something more granular
  than a target or a subtotal, that's a fresh privacy call to flag to the
  user, not an extension of this one.
- **Verifying the dashboard's budget math**: rather than trust the
  JS-in-a-browser by eye, the functions that compute budget rows
  (`computeCategoryTotals`, `monthToDateCategoryTotals`, the row-building
  logic in `renderBudgets`) were copied verbatim into a standalone Node
  script and run directly against the real exported `docs/data.json`,
  cross-checked against the same scenario computed independently in Python
  via `budgets.status_for_category`. Both surfaces agreed exactly (spent/
  budget/pct/state). This is a reusable technique for this project - Claude
  can't screenshot/click the live dashboard, but Node is available on the
  Linux box and locally, so pure-data (non-DOM) JS functions in
  `docs/index.html` can be verified this way instead of only by inspection.

## How the schema evolved (read this before assuming the current shape is final)

This project's schema and message format changed twice in its first day,
both times mid-session while the user was already sending real messages to
the live bot:

1. **Initial build**: amount + free-text note, no category
   (`"$12 lunch"`), space-delimited. Deliberate scope decision at the
   time - the user explicitly chose "no categories, just totals + notes"
   when asked.
2. **Same-day pivot**: the user changed their mind and asked for a 3rd
   field (category), user-defined "on the fly". Space-delimiting broke
   down once item/category could each be multiple words, so the format
   became comma-delimited (`"$12, lunch, food"`) instead - this is *not*
   backwards compatible with the old format's messages.
3. **Live data existed when the pivot happened.** The user logged one real
   expense (`"$50, Yummy Pho, food"`, parsed under the *old* 2-field
   parser as amount=$50 + note="Yummy Pho, food") in the gap between the
   category feature being requested and being deployed. Migrating the
   schema (`note` column -> `item` + `category` columns) meant either
   discarding that row or recovering it - it was recovered by re-running
   the *new* `parse_expense` against the row's saved `raw_message`
   (`"$50, Yummy Pho, food"`), which happened to already be in
   comma-format because the user had started typing the new format before
   the code caught up. Lesson: `raw_message` being preserved verbatim
   (not just the parsed fields) is what made this recovery possible at
   all - don't stop storing it as "redundant" with `item`/`category`,
   it's the only way to re-derive data after a parser change.

If a 4th field or another schema change gets requested, expect this same
pattern: back up first (an extra explicit backup beyond the automatic
startup one, right before touching the schema), check for live rows before
assuming a clean slate, and prefer re-parsing `raw_message` under the new
rules over discarding data that predates a format change.

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
  wake-work-sleep-logger.
- Push auth uses a **dedicated deploy key**
  (`~/.ssh/spending_tracker_deploy` on the Linux box, distinct from
  wake-work-sleep-logger's own key), added to this repo only with write
  access - not a personal access token. The `origin` remote URL uses the
  `github-spend` alias in `~/.ssh/config`, so plain `git push origin`
  "just works" without extra flags.
- `export_stats.py` only writes JSON - it never touches git, same
  separation of concerns as the sibling project.
- `docs/data.json`'s per-day rows are `{date, total_cents, count,
  max_cents, min_cents, categories: {category: total_cents}}`, plus a
  top-level `budgets: [{category, amount_cents}]` (current budget targets,
  not day-scoped) - enough for the dashboard to compute total/avg/largest/
  smallest/by-category/budget-status for any selected range client-side.
  **Per-transaction `item` text is deliberately never exported** - only
  category *subtotals* and budget *targets* are public, so the dashboard
  can show "you spent $340 on food this month, budget $300" without also
  publishing "you bought Yummy Pho for $50 on Aug 24". If a future feature
  wants per-transaction detail on the dashboard, that's a privacy-relevant
  decision to flag to the user, not just a data-shape change.

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
  `pytest` and direct `message_parser`/`stats`/`entries` calls in
  isolation are how Claude verifies logic changes; `scripts/
  manual_smoke_test.py` is an opt-in manual round-trip prompt, not an
  automated test. **In practice this session, the user kept using the
  live bot while development was happening in the same conversation** -
  don't assume the live DB is empty/inert just because a feature is
  mid-build; check row counts before any schema-touching operation, every
  time, even if it was empty minutes ago.
