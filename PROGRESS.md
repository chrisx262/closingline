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
       NOT deployed yet — awaiting owner OK (deploys are MANUAL).
       DEPLOYED — verified live 2026-08-21 at https://www.closinglinehq.com/survivor
       (200, holiday-leg panel + RG footer + home-field lean all present in prod).
       NEXT: moneyline leaderboard (rank picks/agents by ML win prob); real
       pick-popularity feed; optional EndZone model win-prob as a cross-check column.
- [x] SURVIVOR: VARIABLE ENTRY COUNT (1-10) — DONE 2026-08-24. Mark actually
       entered **10** Circa Survivor entries ($10k), not 3, and we want to
       invite him to use the helper — so the 3-entry hardcoding had to go.
       Entry count is now user-set (default 3, cap 10 = Circa's per-person
       limit), persisted per browser in `survivor_count_v1`. All the
       ['1','2','3'] loops became entryIds(); the weekly board, holiday-leg
       counters and planner all follow.
       PORTFOLIO REWRITTEN for N entries, then rewritten AGAIN after Chris
       pointed out the real behaviour: **Mark reuses the same team across
       several entries** — multi-entry players STACK. The first attempt put a
       block on the top team then forced every other entry onto a distinct
       team, which produced "4 on one team + 6 singletons" at N=10. Nobody
       plays that way.
       Now: candidate teams (wp>=.60) are weighted by (wp-0.5) and entries are
       handed out by LARGEST REMAINDER, giving a tapered stack. Verified by
       simulation — N=10 on a normal week gives 3xKC(88%) 2xBUF(82%) 2xSF(78%)
       1xPHI 1xDET 1xBAL; on a week with one dominant team, 5xKC(93%) 3xBUF
       2xSF. HARD RULE: no team may take more than floor(N/2) entries, so one
       upset can never wipe the portfolio. Assignment is a MATCHING problem,
       not a slice, because an entry cannot reuse a team it already burned. When a large entry count forces a sub-60% team into the split it
       says so explicitly — "a real risk of losing an entry, not a
       recommendation to like it" — rather than presenting a forced pick as a
       good one. 9 new checks (ALL PASS).
- [x] 1. Deploy to Railway/Fly — DONE 2026-07-12: live at
       https://closingline-production.up.railway.app (Railway, Postgres,
       ADMIN_KEY/MIN_PICKS/ODDS_API_KEY env vars, smoke-tested: /, /docs,
       /leaderboard, /data/games=272, register + admin auth verified)
- [x] MONEYLINE LEADERBOARD (branch `moneyline-leaderboard`) — endpoint DONE
       2026-08-23, PAGE DONE 2026-08-24 at /moneyline (moneyline_page.py,
       broadcast-light + Vegas-dark, RG footer, no-hype guard, linked from the
       board nav and the survivor nav). Empty-state copy explains the sample
       gate and how an agent qualifies, since the board stays empty until an
       agent actually picks moneylines. 32 checks total (ALL PASS). `GET /leaderboard/moneyline?mode=` ranks
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
       NEXT: wire the model win-prob into the survivor page as the
       cross-check column noted in the SURVIVOR HELPER entry (needs task 2).
- [x] SCHEDULER HEALTH CHECK — DONE 2026-08-24 (branch `scheduler-health`).
       WHY: the scheduler runs INSIDE the web process, so a redeploy, crash or
       platform restart (e.g. the Sat/Sun Postgres patch window) takes the
       thread with it and a missed Tuesday left NO trace. Verified live that
       RUN_SCHEDULER=1 and the thread starts, but there was no way to know if
       it later died — it would have surfaced as stale data in October.
       WHAT: new `JobRun` table records EVERY scheduled attempt (job,
       started_at, ok, detail) incl. a startup heartbeat; scheduler._record()
       writes it and deliberately swallows its own errors so health
       bookkeeping can never be the reason a real job fails. `GET /health`
       grades staleness (weekly_update > 8 days, snapshots > 84h while a game
       is within 8 days) and surfaces recent failures WITH the recorded error.
       Every issue carries what / why / FIX (an exact command) — a health
       check that only says "unhealthy" just creates worry. Off-season
       snapshot pausing is reported as intentional, not as a fault.
       Board shows a banner ONLY when something is wrong (hidden otherwise).
       ADMIN-GATED 2026-08-25: the detailed report names env vars, deploy
       commands and raw error text — an operator runbook, NOT something to
       print on a public homepage beside a leaderboard. `/health` is public
       but vague by default (status + "data may be delayed" + last-updated
       date); full detail needs ADMIN_KEY via `x-admin-key` header or
       `?key=`. A wrong key silently gets the public view. Chris checks it
       with one bookmarked link: closinglinehq.com/health?key=<ADMIN_KEY>
       (key in ~/closingline/.admin_key_SAVE_THIS.txt). 25 checks (ALL PASS).
       GOTCHA HIT: `Base.metadata.create_all(engine)` runs partway down app.py,
       so a model defined BELOW it never gets its table created — the endpoint
       500'd with "no such table: job_runs". New models MUST go above that
       line. Would have failed identically on prod Postgres.
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
- [x] DOMAIN: closinglinehq.com LIVE — but the "verified 2026-07-19" claim
       here was WRONG for a month. Reality: the `_railway-verify.www` TXT
       record was never added, so the cert never issued and the domain served
       a Railway fallback 404 the whole time. Fixed 2026-08-21: TXT added at
       GoDaddy, then a stuck Railway cert order (a known recurring Railway
       defect — `certificate retry` refuses while status is
       VALIDATING_OWNERSHIP) was forced through with the
       `customDomainIssueCertificate` GraphQL mutation against
       backboard.railway.com/graphql/v2. Now: Verified yes, LE cert
       CN=www.closinglinehq.com, apex forwards to www, 200 end-to-end.
       Apex custom-domain registration deleted (CNAME-at-zone-apex is
       impossible; GoDaddy forwarding handles it).
- [~] CIRCA MILLIONS (branch `circa-millions`, 2026-08-22) — IN PROGRESS.
       Owner context: Chris is NOT entering; Mark entered and Chris is weighing
       buying 10% ($100). Overlay math researched: contest needs 6,000 entries
       to cover its $6M guarantee and missed 2 yrs running (5,817 in '24 =>
       +3.1% EV/entry; 5,685 in '25 => +5.5%), BUT only ~126 of ~5,700 entries
       cash => ~98% chance of $0. Slightly-better-than-fair lottery, not an
       investment. Nothing we build changes Chris's EV — MARK makes the picks.
       DESIGN DECISION: this is a LINE-VALUE model, NOT an outcome predictor.
       The 2026-08-10 research killed ATS prediction (48.7%, -7% ROI). Circa
       posts STATIC contest lines Thu 10am PT and picks lock Sat 4pm PT, so the
       number is frozen ~54h while the market moves. Edge = Circa's frozen line
       vs market consensus/close. That is exactly CLV, which this platform
       already computes.
       DONE: `loaders/circa_sheet.py` — fetch/render/OCR/validate. 22 new checks
       in test_all.py (ALL PASS). Dockerfile now installs tesseract-ocr +
       poppler-utils.
       KEY FINDINGS (do not re-derive):
         * Circa's sheet PDFs have NO text layer — zero fonts, zero text ops,
           ~15k vector path ops. Team names and numbers are vector OUTLINES.
           No PDF library will ever extract them. OCR is the only route.
         * Sheets are public, no login:
           circasports.com/wp-content/uploads/YYYY/MM/Circa-Sports-Million-<ROMAN>-Contest-Point-Spreads-Week-<N>.pdf
         * PAIR GAMES BY CIRCA'S OWN 1-32 CONTESTANT NUMBERS (consecutive
           odd/even). Pairing by matching spread values silently mis-pairs
           unrelated teams — it produced "TEXANS vs PACKERS" in testing.
         * The half-point is the ONLY unreliable field. Circa renders a true
           U+00BD glyph, taller than the digits and below the baseline;
           tesseract emits % ) ? ; or merges it into a digit (3.5 -> 37) or
           drops it. NEVER trust OCR alone for it — the mirror rule + explicit
           flagging is what keeps a wrong half-point out of a pick.
         * macOS gotcha: leptonica will not follow the /tmp -> /private/tmp
           symlink; pass os.path.realpath() or you get "image file not found"
           on a file that plainly exists.
       MEASURED on 5 real Million VI sheets: 56 games parsed, 54 confident
       (96%), ~2-3 cells/sheet flagged for human confirmation. Failures are
       always visible, never silent.
       FETCHER DONE: fetch_sheet() pulls the public archive (53/54 sheets,
       2023-2025); 646 games parsed, 98.3% confident.
       BACKTEST FINAL 2026-08-22 — **NO EDGE, AND NOT PROVABLE**. Owner paid
       $30 for one month of The Odds API 20K plan; 132 historical snapshots
       pulled (1,330 of 20,000 credits). Lookahead-free test: Circa's frozen
       Thursday line vs the market at the SATURDAY 6:45pm ET lock, graded ATS
       against Circa's own number, 590 games.
       RESULT: contest-format top-5-per-week = 53.7% (137-118), p=0.359 vs the
       52.4% break-even. EVERY bucket p>0.05; every 95% CI contains 50%. The
       0.5pt bucket grades 49.7%, BELOW break-even, which breaks any monotonic
       story. Sanity check passed (all sides = exactly 50.0%).
       KILLER STAT: proving a 53.7% edge at p<0.05 needs ~12,610 picks = ~140
       SEASONS of a 5-pick-per-week contest. Even if real, it is unverifiable
       and unexploitable at the sample sizes this contest produces.
       WHY: Circa's contest line IS the market at freeze time — median
       |Circa - market| Thursday = 0.00 pts. It drifts to a 0.50 median by
       Saturday. Half a point is not enough.
       DECISION: DO NOT build the /circa-millions pick page or leaderboard.
       Only established edge = the structural OVERLAY (~+3-5% EV/entry), which
       needs no model. Full writeup: docs/circa_line_value_backtest.md.
       NEEDS OWNER: **CANCEL the Odds API paid plan** (next invoice Sep 22
       2026) — one-time pull, nothing ongoing needs it. Free tier covers the
       live season. Raw snapshots in /tmp/circa_hist (10MB) — move if the
       question should ever be revisited without paying again.
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

**DEPLOY IS MANUAL — verified 2026-08-24.** The Railway project has NO GitHub
deployment trigger (`deploymentTriggers` is an empty list in the API), so
pushing to GitHub does NOT deploy. Ship with `railway up --detach` from
~/closingline. Earlier notes in this file claiming push-to-deploy were wrong.

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
