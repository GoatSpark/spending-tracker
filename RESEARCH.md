# Research: manual, non-bank-linked purchase logging apps

Three well-established apps that log spending purely through manual entry -
no bank/card account linking, no transaction sync - researched to inform
what feature would most improve this project. All three explicitly market
"no bank connection" as a feature (privacy/control), not a limitation.

## 1. Monefy

- **Entry**: open app -> tap a category icon -> type an amount -> done.
  Built for speed (sub-5-second logging is the headline pitch).
- **Visualization**: a large interactive donut chart is the primary home
  screen - spending by category, at a glance, no menu required.
- **Multi-currency**: tracks amounts across different currencies natively,
  aimed at frequent travelers.
- **Multiple accounts**: cash, checking, credit card, etc. as separate
  trackable buckets, with a transfer feature to move money between them.
- **Budgets**: supports setting a budget per category/overall and warns
  as you approach or exceed it.
- **Sync**: device-to-device sync via the user's own Google Drive/Dropbox
  (not Monefy's own servers) - stays out of the business of hosting your
  financial data.
- **No bank sync, ever** - manual entry is the only input method.

## 2. Goodbudget

- **Envelope budgeting**: the entire app is built around the classic
  "envelope" method - you allocate a fixed amount to each category
  up front, and once an envelope is empty you either stop spending in
  that category or manually move money in from another envelope.
- **Hard budget periods**: monthly, weekly, semi-monthly, or bi-weekly,
  matching how the user actually gets paid rather than a fixed calendar
  month.
- **Shared budgets**: multiple people (e.g. a couple) can sync to the same
  set of envelopes across devices - the standout feature in every review.
- **Free tier is capped**: 10 envelopes / 1 account for free; unlimited
  envelopes and multi-device sync require a paid plan.
- **No bank sync on the free tier** - manual entry only unless upgrading.

## 3. Fudget

- **Deliberately no categories at all** - the opposite end of the
  spectrum from Monefy/Goodbudget. Just a running list of + (income) and
  - (expense) entries with a running balance.
- **Budget-scoped ledgers**: you can create separate budgets for specific
  purposes (a trip, an event, a project) rather than one global ledger.
- **Search/filter and notes**: entries can carry free-text notes and be
  searched, useful given there's no category to filter by instead.
- **No bank sync** - the app's whole pitch is "simple, manual, nothing to
  configure."

## What this suggests for spending-tracker

The two more fully-featured apps (Monefy, Goodbudget) converge on the same
thing as their headline value beyond "logging": **a budget/limit per
category, with a warning as you approach or cross it.** Goodbudget's entire
product *is* this (envelope budgeting). Monefy treats it as a core feature
alongside its donut-chart visualization. Fudget is the one counterexample,
but it trades this away deliberately in exchange for extreme simplicity -
not a model to copy here, since spending-tracker already has categories
and a dashboard built around them.

spending-tracker currently only does the "record and review" half of what
these apps do - it has no way to say "you're overspending" *before* the
month is already over and you're looking at a dashboard. That's the gap:
this project turns spending into a passive log you can review, not yet an
active tool that helps you not overspend. **Per-category budgets with an
over/near-limit warning at log time** is the highest-impact single feature
to close that gap.

## Sources

- [Monefy: Money Tracker (Google Play)](https://play.google.com/store/apps/details?id=com.monefy.app.lite&hl=en_US)
- [Monefy: Money Tracker (App Store)](https://apps.apple.com/us/app/monefy-money-tracker/id1212024409)
- [App Showcase: Monefy: Money Tracker](https://screensdesign.com/showcase/monefy-money-tracker)
- [Goodbudget Review 2026 | BudgetingApps.org](https://budgetingapps.org/apps/goodbudget/)
- [Goodbudget App Review | Experian](https://www.experian.com/blogs/ask-experian/goodbudget-budgeting-app-review/)
- [Goodbudget Review 2026 — Features, Pricing & Verdict | WalletGrower](https://walletgrower.com/budgeting/reviews/goodbudget)
- [Fudget App - GitHub](https://github.com/fudget-app)
- [Fudget: Monthly Budget Planner (Google Play)](https://play.google.com/store/apps/details?id=com.dannyconnell.fudget2&hl=en_US)
- [Fudget Review: Budget App Pros & Cons | Phroogal](https://www.phroogal.com/product/fudget-app-simple-budgets/)
