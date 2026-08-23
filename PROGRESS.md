# PROGRESS.md — session state (Claude Code: keep this current)

## Task board (specs in HANDOFF.md)

- [x] SURVIVOR HELPER — DONE 2026-08-10 (owner use case: he + friend Mark have
       3 Circa Survivor 2026 entries; $20M pool, straight-up/moneyline,
       tie=elimination, one team per entry). New page /survivor + endpoint
       /data/survivor + helpers devig_two_way()/wp_from_spread(). Ranks teams
       by DE-VIGGED MARKET win probability (moneyline; spread fallback) — the
       market beat our model at picking winners, so market is the primary
       survivor signal. Features: 3-entry manager w/ used-team tracking
       (localStorage), win% tier pills (SAFE/SOLID/LEAN/RISKY), future-value
       "save for Wk X" flags, estimated pick-popularity bars (labeled est.,
       no field data yet), 3-entry diversified portfolio suggestion, multi-week
       planner, Sep-12 reg countdown, + a HOME-FIELD LEAN slider (0-5%, default
       +1.5%) that re-ranks home favorites above road favorites while the honest
       market win% still shows on each pill (labeled a subjective lean, not an
       edge — market already prices HFA). Matches board's broadcast/Vegas-dark
       theme. RG footer + no-hype guard enforced. 2026-08-13 added: HOLIDAY-LEG
       PROTECTION (Circa Thanksgiving Wk12 / Christmas Wk16) — panel with real
       matchups + each team's market win% (favorite highlighted, fetched for
       weeks 12/16), per-entry "still open" counter, ★ for both-leg teams, and
       weekly-board RED outline/flag + toast on holiday-leg teams so you don't
       burn them early. 18 new tests in test_all.py
       (ALL PASS). Private design preview (mock data) artifact shared w/ owner.
       NOT deployed yet — awaiting owner OK (push to main auto-deploys to prod).
       NEXT: moneyline leaderboard (rank picks/agents by ML win prob); real
       pick-popularity feed; optional EndZone model win-prob as a cross-check column.
- [x] 1. Deploy to Railway/Fly — DONE 2026-07-12: live at
       https://closingline-production.up.railway.app (Railway, Postgres,
       ADMIN_KEY/MIN_PICKS/ODDS_API_KEY env vars, smoke-tested: /, /docs,
       /leaderboard, /data/games=272, register + admin auth verified)
- [~] MONEYLINE LEADERBOARD (branch `moneyline-leaderboard`, 2026-08-23) —
       endpoint DONE, page pending. `GET /leaderboard/moneyline?mode=` ranks
       agents on moneyline picks by **de-vigged win-probability CLV** (CLV
       first, ROI second per invariant 5). This is the survivor-relevant
       market and the one EndZone Edge now targets.
       WHY DE-VIG: the generic `clv_prob` differences two RAW implied probs,
       which each include the hold. It mostly cancels but not exactly, and on
       a board whose whole premise is honest measurement that is not good
       enough. `_ml_fair_probs()` pulls BOTH sides from the same snapshot via
       snapshot_at()/closing_snapshot() and runs devig_two_way(), so it also
       inherits the anti-lookahead guarantee instead of creating a second path
       to prices.
       CLV SIGN: market moving TOWARD your side after you bet = positive.
       CONTEXT COLUMNS, never ranking inputs: avg_fair_winprob and
       underdog_rate. An agent that only picks heavy chalk is not "better"
       than one taking live dogs — it is playing a different game, and the
       reader should see that rather than have it hidden in one number.
       20 new checks (ALL PASS), incl. devig correctness, CLV sign, and that
       spread picks are excluded from the board.
       NOTE: seed/backtest agents only place spread+total picks, so the board
       is EMPTY against seeded data — tests populate it by submitting real
       moneyline picks through /picks. Real rows need an agent actually
       picking moneylines (that is task 2, EndZone Edge).
       NEXT: surface it in the UI (board page section or /moneyline page,
       matching explorer_page.py style) + wire into the survivor page as the
       cross-check column noted in the SURVIVOR HELPER entry.
- [ ] 2. Wire owner's real model in via examples/agent_stub.py
- [ ] 3. Friend onboarding verified against the deployed URL
- [x] 4. Odds snapshot cron — DONE 2026-07-13: snapshot_odds() finished
       (32-team map, top-3-book consensus, 36h kickoff matching; live-
       verified: 75/75 events captured). scheduler.py runs the full cadence
       incl. Sun 11:35 post-inactives + Tue 09:00 weekly_update, in-process
       (RUN_SCHEDULER=1), DST-safe, off-season auto-skip. 15 new checks.
- [ ] 4b. /data/injuries feed with as_of
- [x] 12. Board redesign — DONE 2026-07-19: broadcast light + Vegas-dark
       theme toggle, spotlight cards, monogram chips, CLV grade pills,
       rank-movement arrows (RankSnapshot weekly via weekly_update),
       streak pills, motion (CSS-only, reduced-motion safe). Includes
       task 11 v1: data-driven smack ticker (platform-generated only).
       SEO: canonical -> closinglinehq.com, OG/Twitter cards. 67 checks.
- [x] DOMAIN: closinglinehq.com live on Railway (custom domain + DNS
       verified 2026-07-19); canonical URL for SEO.
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
