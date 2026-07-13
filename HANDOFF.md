# HANDOFF.md — brief for Claude Code (autonomous execution)

You are continuing the build of **ClosingLine**, a platform where AI agents
and human handicappers submit NFL picks, get server-priced against odds
snapshots, and compete on a leaderboard ranked by closing line value.
Work through the task list in order. Test after every task. Commit often.

## Current state (v1.1, verified working)
- `app.py` — FastAPI platform: registration, server-priced immutable picks,
  point-in-time `/data/*` endpoints (`as_of`), grading engine with CLV,
  live/backtest leaderboards, per-segment report cards, leaderboard UI at `/`.
- `loaders/nflverse_loader.py` — loads real seasons (tested 2021-2025,
  1359 games) with real closing lines. No API keys.
- `loaders/real_data.py` — skeleton for in-season odds snapshots
  (The Odds API) with the cron cadence documented.
- `systems/elo_agent.py` — Elo baseline. Train 2023-24: +3.7% ROI;
  frozen-parameter blind test 2025: -24% ROI. Conclusion: closing line
  already contains Elo-level info. Kept as the honest baseline to beat.
- `examples/agent_stub.py` — the integration contract for external systems.
- `backtest.py`, `weekly_update.py`, `Dockerfile`, env config
  (`DATABASE_URL`, `ADMIN_KEY`, `MIN_PICKS`).

Smoke test: `pip install -r requirements.txt && python loaders/nflverse_loader.py 2025 && python backtest.py`

## Invariants — never violate these, they are the product
1. Picks are immutable. Never add edit/delete endpoints.
2. The server prices every pick from its own snapshot. Never trust
   client-supplied lines or odds.
3. Every data endpoint must respect `as_of`. Nothing in backtest mode may
   ever see data timestamped after its `as_of`.
4. Live and backtest records stay permanently separated.
5. Leaderboard ranks CLV first, ROI second.
6. Train/test discipline for any model work: tune on ≤2024, report 2025
   blind. Report negative results without spin.

## Task list (in order)
1. **Deploy.** Railway or Fly.io using the existing Dockerfile. Needs the
   owner's account login — prepare everything, ask the owner only for the
   final auth step. Set `ADMIN_KEY`, add Postgres, verify `/` and `/docs`
   from the public URL. Done = external URL serving the 2025 board.
2. **Wire in the owner's real model.** Adapt `examples/agent_stub.py` to
   call their system's prediction function. Run it against 2025 in backtest
   mode; produce its report card. Done = their agent on the backtest board.
3. **Onboarding doc for the friend.** One markdown page: register, env vars,
   stub, submit, read your report card. Done = friend integrates unassisted.
4. **Odds snapshot cron.** Finish `loaders/real_data.py::snapshot_odds`
   (team-name mapping to our game_id convention; average top 3 books).
   Schedule per the cadence in that file — including the post-inactives
   snapshot (Sun ~11:35 ET), which is what prices QB-out news into CLV.
   Done = multiple snapshots per game appearing in-season → real CLV.
4b. **Injuries/inactives feed.** Add `/data/injuries?game_id&as_of` serving
   timestamped injury-report and inactives data (nflverse injuries data or
   ESPN's public API), respecting `as_of` like every other endpoint. This
   lets bots auto-react in the post-news window (a second, hedging pick —
   never a revision; picks stay immutable). Done = a bot can query who's
   inactive 90 min before kickoff and fire a late pick.
5. **Data explorer UI — DONE in v1.2** (line-movement charts still pending, need in-season snapshots). Original spec: New page: per-game line movement chart (from
   snapshots), weekly slate table, situational filters (division, home dog,
   rest advantage — rest/roof/temp/wind columns are available in nflverse;
   extend the loader + Game model to store them). Keep the existing visual
   style. Done = a bettor can browse this week without touching the API.
6. **Elo v2 (baseline #2).** Add QB-out adjustment and EPA-based ratings
   (nflverse play-by-play). Same discipline: train ≤2024, blind 2025.
   Done = documented comparison vs elo_edge_v1, whatever the result.
7. **Hardening.** Rate-limit pick submission, `MIN_PICKS=30`, pagination on
   boards, basic request logging.
8. **Monetization — only after a live paper season is underway.** Stripe
   subscriptions gating real-time pick feeds; delayed picks stay free.

## Style
- Small commits, plain prose docs, no over-engineering. SQLite fine until
  deploy; Postgres after. Ask the owner nothing that a sensible default
  can answer — they explicitly delegated decisions.

9. **Futures picks & grading.** FuturesOdds table + /data/futures exist
   (seeded with the verified July 2026 championship board; conference/
   division lists scaffolded in loaders/futures_seed.py). Add: futures
   pick submission (server-priced from latest snapshot, immutable, same
   rules), a season-end settlement admin endpoint, and a futures section
   on the explorer. Automate board capture weekly if a feed is found;
   otherwise manual seed updates are fine — futures move slowly.

10. **Best-bet board** (owner's idea, 2026-07-13). A separate leaderboard
   tracking each agent's declared pick-of-the-day only — a bot mediocre
   overall can be elite on its top play, and that's the followable
   (and eventually subscribable, task 8) signal.
   **Phase 1 — DONE 2026-07-13:** `best_bet: true` flag on pick
   submission; server enforces one per agent per ET slate day (per mode),
   declared at submit time + immutable (no retroactive cherry-picking).
   `/leaderboard/best-bets` ranks CLV-first with qualification tiers
   sized to a 17-week season: 4 graded = provisional (visible, badged),
   8 = ranked, 12 = proven. Sample size always shown. Board section on `/`.
   **Phase 2 — in-season upgrade (spec):** on single-game days (Thu/Mon)
   one game-level market is a weak "best bet of the day", so add
   quarter/period markets (e.g. 1Q spread, 3Q total) for those days only:
   per-event Odds API calls cost extra credits, so fetching them just for
   single-game days (~60 credits/month) keeps the free tier viable.
   Needs: OddsSnapshot columns per period market, pricing paths in
   price_from_snapshot, quarter scores for grading (nflverse pbp has
   them), same CLV-per-market discipline. Build once the season starts
   and snapshot data is flowing.

11. **Trash talk — SPEC ONLY, owner deciding (2026-07-13).** Bounded
   banter, never a chat room (lesson from moltbot-style toxicity):
   - v1 (zero moderation risk): PLATFORM-generated smack from the data —
     auto-lines like "X has beaten the close 6 straight" on boards.
   - v2 (earned mic): free-text `taunt` field on pick submission,
     ~140 chars, ONLY for ranked+ agents, immutable like the pick,
     word-filtered, rate-limited, always rendered next to the agent's
     live record, TAUNTS_ENABLED env kill switch. No threads/replies/
     @-mentions ever. Commercial invariant applies: never affects
     rankings. Do not build until the owner green-lights.

12. **Board redesign — direction CHOSEN by owner 2026-07-13, build on
   green-light.** White "broadcast" board + auto-smack ticker, with a
   dark theme option (owner-approved mockup: white analytics layout,
   PFF-style color-graded CLV pills — teal elite / blue good / red poor —
   leader-spotlight cards, monogram chips, rank-movement arrows, streak
   pills W6🔥/L3🧊, ticker of PLATFORM-generated smack lines = task 11 v1).
   Light default + dark via prefers-color-scheme AND a manual toggle,
   token-based CSS. Needs small backend additions: weekly rank history
   (for ▲▼ movement), streak calc, smack-line generator from graded
   picks. Keep current UI until built; reference mockup lives in the
   owner's Claude artifacts ("final-combo-v1").
