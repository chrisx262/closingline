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
