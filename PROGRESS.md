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
       DEPLOYED — verified live 2026-08-21 at https://www.closinglinehq.com/survivor
       (200, holiday-leg panel + RG footer + home-field lean all present in prod).
       NEXT: moneyline leaderboard (rank picks/agents by ML win prob); real
       pick-popularity feed; optional EndZone model win-prob as a cross-check column.
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
       NEXT: (a) fetcher that finds the current week's PDF from the contest
       page; (b) two snapshot times — Thu 13:05 ET (line freezes) and Sat 18:45
       ET (just before lock), ~+26 Odds API credits/mo on top of ~66 of 500;
       (c) line-value calc reusing snapshot_at()/closing_snapshot(); (d)
       /circa-millions page + leaderboard; (e) BACKTEST over the public archive
       to answer whether line value actually beats 52.4% here — publish the
       result either way per invariant 6. Circa is famously sharp, so a null
       result is a real possibility and must not be spun.
       NEEDS OWNER: nothing blocking. Branch is uncommitted to main, not
       deployed, not pushed.
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
