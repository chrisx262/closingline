# PROGRESS.md — session state (Claude Code: keep this current)

## Task board (specs in HANDOFF.md)

- [x] 1. Deploy to Railway/Fly — DONE 2026-07-12: live at
       https://closingline-production.up.railway.app (Railway, Postgres,
       ADMIN_KEY/MIN_PICKS/ODDS_API_KEY env vars, smoke-tested: /, /docs,
       /leaderboard, /data/games=272, register + admin auth verified)
- [ ] 2. Wire owner's real model in via examples/agent_stub.py
- [ ] 3. Friend onboarding verified against the deployed URL
- [x] 4. Odds snapshot cron — DONE 2026-07-13: snapshot_odds() finished
       (32-team map, top-3-book consensus, 36h kickoff matching; live-
       verified: 75/75 events captured). scheduler.py runs the full cadence
       incl. Sun 11:35 post-inactives + Tue 09:00 weekly_update, in-process
       (RUN_SCHEDULER=1), DST-safe, off-season auto-skip. 15 new checks.
- [ ] 4b. /data/injuries feed with as_of
- [ ] 5. Explorer line-movement charts (needs multi-snapshot data)
- [ ] 6. Elo v2: QB-out adjustment + EPA ratings (train ≤2024, blind 2025)
- [ ] 7. Hardening: rate limiting, MIN_PICKS=30, email unsubscribe/delete,
       real accounts to replace browser-stored keys
- [ ] 8. Monetization activation — AFTER a live paper season is underway
- [ ] 9. Futures picks + season-end settlement + explorer futures board
- [x] 10. Best-bet board Phase 1 — DONE 2026-07-13 (flag at submission,
       one/slate-day enforced, /leaderboard/best-bets with 4/8/12 tiers,
       CLV-first, board on /; 12 new checks). Phase 2 (quarter markets on
       single-game days) specced in HANDOFF — build in-season.

## DONE before handoff (v1.8, all tested — see tests/test_all.py)

Platform + trust rules · real 2025 season + 2026 schedule (83 games
priced) · backtest engine (472 real picks validated) · Elo baseline
(honest -24% blind test) · report cards incl. timing buckets · hedge
support · data explorer + real situational trends · human picks page
(one-step signup) · email capture + digest generator · affiliate +
sponsor slots with click tracking · API keys hashed · UTC timezone fix ·
29-check regression suite

## Decisions log

- (Claude Code: append decisions here, dated, one line each)
- 2026-07-12: season preload moved from Docker build to boot.py runtime
  (build-time seeding landed in throwaway sqlite, never in Postgres).
- 2026-07-12: boot seeds per-season [2025, 2026] — odds matching needs the
  coming season's schedule; merge-by-id makes reseeding safe.
- 2026-07-13: cron = in-process scheduler thread (RUN_SCHEDULER=1) instead
  of Railway cron services — zero dashboard config, DST-safe via zoneinfo,
  slot logic unit-tested. Revisit if the service ever runs >1 replica.
- 2026-07-13: Odds API cost verified live: 3 credits/snapshot (markets x
  regions), cadence ~66/month vs 500 free. weekly_update runs Tue 09:00 ET
  per README (cadence doc's Mon 09:00 slot superseded).
- 2026-07-13: best-bet tiers 4/8/12 (owner decision) — sized to ~1-3 best
  bets/week over a 17-week season; low floor is defensible because ranking
  is CLV-first (continuous signal) and sample size is always displayed.
- 2026-07-13: best bet = per SLATE DAY (ET date of kickoff), not per week —
  a ceiling not a quota; weekly-only bettors are naturally compatible.
- 2026-07-13: additive schema changes via _migrate_additive() in app.py
  (try/except ALTER) — create_all can't alter existing Postgres tables.

## Live deployment facts

- URL: https://closingline-production.up.railway.app
- Railway project: closingline (794b7651), service: closingline, region sfo
- Postgres attached; DATABASE_URL referenced into the service
- ADMIN_KEY: in owner's password manager (and ~/closingline/.admin_key_SAVE_THIS.txt)
- ODDS_API_KEY: Railway var + owner's local ~/closingline/.env (never in git)
- Deploys auto-trigger on push to main (GitHub-linked)

## NEEDS OWNER

- Railway or Fly account login (task 1)
- The Odds API free key -> loaders/real_data.py (task 4)
- Email provider choice/key when digest sending goes live (task 7/8)
- Gaming attorney check BEFORE real affiliate links (task 8)
