# CLAUDE.md — ClosingLine execution protocol

You are completing ClosingLine, a platform where AI agents and human
handicappers submit NFL picks, get server-priced against odds snapshots,
and compete on leaderboards ranked by closing line value. The design is
finished and tested; your job is disciplined execution, not redesign.

## The loop — follow it every session

1. **Read state.** Open PROGRESS.md. Find the first task not marked DONE.
   Read the matching task in HANDOFF.md for full specs.
2. **Verify base.** Run `python tests/test_all.py`. If anything fails,
   fixing it IS the current task — never build on a red suite.
3. **Plan small.** Break the task into steps completable this session.
   Prefer shipping half a task working over all of it broken.
4. **Implement.** Small changes, run relevant code after each change.
5. **Test.** Rerun `python tests/test_all.py`. ADD new checks to it for
   every feature you build — the suite must grow with the code.
6. **Record.** Update PROGRESS.md: mark done, note decisions made, list
   anything blocked on the owner. Commit with a clear message.
7. **Loop** to step 1 until the session ends or you hit an owner-blocker.

## Invariants — violating any of these is failure, even if tests pass

1. Picks are immutable. Never add edit/delete endpoints.
2. The server prices every pick from its own snapshot. Never trust
   client-supplied lines or odds.
3. Every data endpoint respects `as_of`. Nothing in backtest mode may see
   data timestamped after its `as_of`.
4. Live and backtest records stay permanently separated.
5. Leaderboards rank CLV first, ROI second.
6. Model work: train on ≤2024, report 2025 blind, publish negative
   results without spin.
7. Nothing commercial (affiliate, sponsor) ever touches rankings, and
   every commercial placement carries its disclosure.
8. All timestamps are UTC. nflverse times are US Eastern — convert
   (see loaders/nflverse_loader.py::to_utc).

## Follow-a-Bot & staking guardrails — read BEFORE building any of it

The "follow a bot" feature (users follow a bot, get notified of its picks,
watch its live record) turns ClosingLine from an AI competition into a
platform whose picks humans stake real money on. That category shift makes
the rules below HARD INVARIANTS — they gate what gets built, not just how.

> ⚠️ NOT LEGAL ADVICE. Sports-pick platforms are regulated and rules vary
> by state. A licensed attorney must review this feature before it earns a
> single dollar. Below are well-known boundaries, not counsel.

1. **Never place, hold, or touch a bet. No auto-betting integrations, EVER**
   — even when users ask (they will). Software placing a bet puts you in a
   different regulatory universe. ClosingLine only notifies + shows records;
   the human bets at their own sportsbook, with their own money.
2. **Picks are suggestions with receipts, not instructions.** The product's
   own voice never says "lock," "can't-miss," or "guaranteed." A board may
   state a bot is 9-2; it never hypes the streak. Let the record talk.
3. **Never delete or edit a bot's graded history.** Reinforces invariant #1
   (picks immutable). The full public, out-of-sample, auditable record vs.
   the Vegas baseline IS the brand — the anti-tout. Curating it kills the
   whole value proposition.
4. **Free-to-follow is the clean default.** Charging for follows/premium
   picks is tout territory with state-by-state legal + reputational weight —
   NEEDS OWNER + a lawyer before any such thing ships. Target revenue via
   sponsor/affiliate (per invariant #7) without ever charging for picks.
5. **Affiliate + picks is the touchiest combo.** If sportsbook affiliate
   links exist, keep them STRUCTURALLY SEPARATE from pick notifications,
   geo-gate to legal states, and disclose everywhere. (Extends invariant #7.)
6. **Responsible-gambling is mandatory at this layer.** 21+, "informational
   only, not financial advice," and 1-800-GAMBLER on the site, on every bot
   page, and in every notification footer. On-brand: the honest platform is
   honest about risk too.

Marketing angles that ride on these (follower leaderboard, milestone posts,
weekly recap) live in MARKETING_PLAYBOOK.md — but the rules above win in any
conflict.

## Owner interaction rules

- The owner delegated all technical decisions. Choose sensible defaults;
  document them in PROGRESS.md instead of asking.
- Only stop for things that genuinely need the owner: account logins
  (Railway/Fly, email provider), API keys, signing legal/affiliate deals,
  and spending money. Batch these into a short "NEEDS OWNER" list in
  PROGRESS.md rather than interrupting per item.
- The owner is non-technical-leaning and often tired after 12-hour
  shifts: anything you ask must be answerable from a phone in one line.

## Orientation (read once)

- `HANDOFF.md` — the task list (source of truth for WHAT to build)
- `PROGRESS.md` — session state (source of truth for WHERE we are)
- `README.md` — quickstart, deploy steps, endpoint map
- `app.py` — entire platform; `tests/test_all.py` — regression suite
- Smoke test: `pip install -r requirements.txt &&
  python loaders/nflverse_loader.py 2025 2026 && python tests/test_all.py`

## Style

Small commits. Plain prose docs. No new frameworks, no rewrites, no
over-engineering — SQLite until deploy, Postgres after. Match the
existing visual style on any UI work (see explorer_page.py). When in
doubt, the boring option that keeps tests green is correct.
