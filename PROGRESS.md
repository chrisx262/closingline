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
- [x] 2. Wire owner's real model — DONE 2026-08-26. EndZone Edge ported into
       systems/endzone_agent.py (ported, NOT imported: EndZone invariant 6
       forbids merging the repos; agent submission is the sanctioned link,
       their T7). Frozen 2024 fit W_OFF=0.70 HFA=0.4, never refit in the
       runner. Dry run reproduced the reference harness EXACTLY — 59.6% on
       208 graded 2025 picks, from OUR game data rather than nflverse CSV.
       SUBMITTED to prod: agent_id 2, 208/208 moneyline picks, graded
       124-84-0, ROI -10.18%. Now rank 1 on both /leaderboard?mode=backtest
       and /leaderboard/moneyline?mode=backtest — the moneyline board's
       first real rows. Honest read: avg_fair_winprob 0.6329 vs 59.6% actual,
       i.e. it underperformed the market's own expectation of its picks;
       Vegas favourites hit 63.0%. Published unspun per invariant 6.
       Moneyline only — the 2026-08-10 research found no ATS edge, so spread
       picks would fake a skill the backtest denies. 17 new checks (222).
- [x] 3. Friend onboarding — DONE 2026-08-26: walked ONBOARDING.md verbatim
       against https://www.closinglinehq.com. Three blockers found and fixed:
       $URL was never defined, the example game_id 2026_W01_DAL_PHI does not
       exist (DAL plays NYG, PHI plays WAS in 2026 W1), and /data/odds 409s
       for every upcoming game because snapshots pause off-season — now
       documented with a 2025 backtest path. agent_stub.py defaulted to
       localhost; now defaults to prod and says why it picked nothing.
       10 new checks pin the doc to reality (205 total).
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
- 2026-09-02: DEPLOYED and verified live. All six routes 200 including the new
  /survivor/sim; /data/survivor serves 272 games over 18 weeks (114 market lines,
  158 estimates) with the as_of field. Ran the deployed simulator against prod
  data: 20 legs, best path 0.179% vs greedy 0.094%, ten diversified entries reach
  Thanksgiving 16% against 6% for ten clones, 200-cell portfolio grid, no console
  errors. as_of is null until the odds cron takes its first in-season capture
  (it skips off-season; season opens Sept 10) and the page says so.
- 2026-09-02: PRIORS NOW FIT ON GAMES NOT YET PLAYED, not the whole season.
  Owner's point: teams over- and under-perform preseason expectations every
  year, so a September line is a stale opinion by December. Confirmed on 2025 --
  the average team's rating moved 3.13 pts between weeks 1-4 and weeks 14-17,
  14 of 32 moved more than 3 pts, 6 moved more than 5, SEA went -0.93 -> +8.10.
  Then measured which fit predicts better. Standing at week 10 predicting weeks
  14-17: everything-so-far 3.94 pts error, unplayed-priced-only 3.04. At week 6
  predicting 10-13: 3.09 vs 2.20. About a quarter better both times. Late season
  the forward window thins, so recently played games are added back most-recent
  first until 64 games (~2 per team); that blend scored 3.21/2.18, barely behind
  and much steadier. Cache keys on the forward-window size so it refits as games
  are played. This is what makes the tool adapt week to week rather than
  replaying a preseason opinion.
- 2026-09-02: CONTINGENCY panel on /survivor/sim. We still do not model
  injuries -- the market prices them faster than we could and every posted line
  already carries today's news. What IS knowable today is how much the plan
  leans on one team, measured by removing that team and re-solving. Two blocks:
  the fallback ladder at each holiday leg, and the cost of losing each holiday
  team. KEY ASYMMETRY on the 2026 board: Thanksgiving is fragile (LA 68%, next
  is BUF at 58% -- a ten-point cliff, losing LA costs 31% of the season), while
  Christmas is robust (PHI 55%, BUF 55%, CHI 52%, LA 52% -- losing PHI costs
  three points and 20%). So the contingency worth having is for Thanksgiving,
  which is the opposite of where the attention has been all along.
- 2026-09-02: HOW MANY TO HOLD, measured. Holding the top N of each leg until
  that leg: N=0 0.167%, N=1 0.167%, N=2 0.167%, N=3 0.134%, N=4 0.117%. Holding
  1-2 per leg is FREE; 3+ costs real value; all twelve costs 62%. And N=0 already
  fields 68%/55% at the legs -- the assignment solver reserves LA and PHI on its
  own without being told, because it optimises the whole season. The hold-back
  rule is a crutch for the GREEDY weekly policy, not for the optimum.
- 2026-09-02: third column on the best-path table, "Holiday teams held" -- the
  best path if no holiday-leg team may be spent before its own holiday leg
  (free from that leg onward; a both-legs team is therefore locked only until
  Thanksgiving, since spending it there is what uses it up). Owner's request.
  RESULT: the blanket rule is expensive. 0.064% against the unrestricted
  0.167%, roughly two and a half times worse, and worse than greedy's 0.105%.
  Holding ONE team per leg (the simulator's reservation policy) captures the
  protection; holding all twelve throws away far more than it saves. Useful
  precisely because it shows a plausible rule is a bad one.
- 2026-09-02: verified the mid-season case end to end on a synthetic week-4
  state (weeks 1-3 marked final). The feed anchors at week 4, settled picks hold,
  and a season-long injury re-solves properly: dropping MIN by 22 points across
  its 14 remaining games removed MIN from the plan entirely and changed 10 of 17
  legs. Note the counterintuitive-but-correct result -- survival ROSE (0.292% ->
  0.345%), because every team that plays the injured side becomes a safer pick.
- 2026-09-02: /data/survivor reports `as_of`, the newest snapshot captured AT OR
  BEFORE NOW, plus `as_of_note`. Both pages show the age and a Refresh button,
  and flag anything over three days as a missed snapshot. First cut took the
  plain maximum captured_at and reported odds "captured Fri Dec 25" aged minus
  165,330 minutes: the nflverse archive timestamps its rows at KICKOFF, so an
  unplayed game carries a future capture time. A future timestamp now means the
  price is archive-seeded rather than live, and the page says exactly that
  rather than dressing it up as fresh.
- 2026-09-02: CORRELATION BUG FIXED, and it was a bad one. Every entry drew its
  OWN random result for the same game, so three entries on the Chargers could
  have three different outcomes. That deletes the only risk a multi-entry
  portfolio exists to manage. Entries picking the same team in the same leg now
  share one result. Effect: ten IDENTICAL entries now score exactly the same as
  one entry (reach Thx 5%, Xmas 1%, table 0.10%), where before they showed
  29%/4%/1.1%. Every multi-entry number reported before 2026-09-02 was inflated.
- 2026-09-02: PORTFOLIO OF PATHS on /survivor/sim. Entries are solved in turn,
  each charged CLASH=0.35 log-probability for every team it would share with an
  entry already placed, so the ten paths deliberately differ. Scored by
  simulatePaths(), which plays them together sharing one result per game --
  the effect being measured IS the correlation, so it cannot be computed entry
  by entry. Diversified vs all-on-the-best-path, 10 entries: reach Thanksgiving
  16% vs 5%, any runs the table 0.40% vs 0.20%. Nine distinct week-1 teams.
- 2026-09-02: SETTLED LEGS. bestPath and greedyPath now take the entry's
  already-made picks and hold those legs fixed instead of re-optimising them --
  previously the path would show a different week-1 team than the one the owner
  had just picked. Survival is computed over the legs STILL TO PLAY, since a
  settled leg has already been survived. Legs carry `week` so a stored pick
  {t,w} can be matched to the right leg in weeks 12 and 16, which hold two each.
- 2026-09-02: BEST PATH takes a pinned opening team (bestPath(...,forceFirst)),
  so the owner can ask "what if I start with JAX or LV" and get the optimal
  continuation from there rather than only the unconstrained optimum. The panel
  ranks every opening option BY WHERE THE SEASON ENDS UP, not by this week's win
  probability, and the two orders differ sharply: DET at 72% this week lands
  BELOW LV at 64% and PIT at 61%, because the optimum wants Detroit in week 5
  and has no later use for Las Vegas or Pittsburgh. JAX at 77% costs only 4%
  against opening with LAC, because LAC simply slides to week 2 at 75%. That gap
  between "best now" and "best overall" is the entire value of the panel.
- 2026-09-01: BEST POSSIBLE PATH on /survivor/sim, at the owner's suggestion
  ("can the simulator take the bigger edge wk X and project a winning entry
  look ahead?"). Assigning 20 legs from 32 teams to maximise survival is an
  assignment problem, not a simulation: maximising a product of win probs is
  maximising the sum of their logs, so it is max-weight bipartite matching.
  Hungarian, exact, ~1ms. On the real 2026 board the optimum survives 0.167% vs
  greedy's 0.105% -- 1.6x -- and they differ on 12 of 20 legs, e.g. greedy burns
  SF at 84% in week 2 while the optimum saves it for week 3 and takes TB at 68%.
- 2026-09-01: the greedy comparison is computed EXACTLY (greedyPath), not
  sampled. First cut compared exact-optimum against a 4000-season Monte Carlo
  and printed the optimum as WORSE (0.17% vs 0.22%), which is impossible --
  surviving all 20 legs happens ~2 times in 1000, so at any affordable sample
  size the noise dwarfs the effect. Which teams greedy takes is deterministic,
  so its true probability is just the product along that fixed sequence.
- 2026-09-01: tests/check_hungarian.js brute-forces the solver against every
  permutation on 300 random instances (including infeasible cells). Wired into
  test_all.py, skipped with a printed SKIP if node is not installed. A matching
  algorithm that is subtly wrong still returns plausible answers.
- 2026-09-01: SURVIVOR SPLIT INTO TWO PAGES at the owner's call. /survivor is
  the weekly decision (board, portfolio, holiday panel, planner); /survivor/sim
  is the season simulator. Shared guts extracted to survivor_core.py (theme,
  team colours, HOLIDAY_LEGS, entry state + elimination, the /data/survivor
  feed, weekTeams/futureValue/tier, and a shell() that builds both pages so the
  chrome and the RG footer cannot drift apart). CONTRACT: core calls renderAll()
  only; each page defines renderAll() over the panels it actually has. Core may
  never name a page-specific renderer -- that coupling is what made the split
  hard. Entries live in the same localStorage keys, so a pick on either page
  shows on the other.
- 2026-09-01: the simulator page is SELF-CONTAINED for picking -- the comparison
  table carries its own Use buttons. A planning page you cannot pick from would
  undo the reason for splitting it out, which was the owner not being able to
  watch a number move while causing it to move.
- 2026-09-01: FUTURE VALUE (SurvivorGrid's formula, taken 2026-08-31) silently
  changed meaning when priors landed today. It sums (wp-0.5) over remaining
  weeks a team is favoured; it used to see only market-priced weeks because
  those were the only ones with a number, and now it spans all 18. That moved
  the star rating for 10 of 31 teams (BUF 3->4, SEA 4->5, SF 5->4) and the stars
  drive the "consider saving" flag. Kept the wider span -- it is closer to the
  definition, and the whole reason for taking it was to catch the team favoured
  in eight straight weeks, which you cannot see in September without estimates.
  But the flag now states the mix ("6 weeks of real market lines and 11 still
  estimated"), and fvWeeksAhead returns {total, market, est} instead of a bare
  count. The stale docstring claiming market-only has been corrected.
- 2026-09-01 CORRECTION to the depth note below: all NINE holiday-leg games are
  real market moneylines (verified), NOT estimates. The earlier justification
  ("often built off an estimate") was wrong. Depth still matters, for a
  different reason: a line posted in September for a December game is real but
  EARLY, and moves on every injury and three months of form.
- 2026-09-01: INJURIES ARE HANDLED BY THE MARKET, NOT MODELLED. We take no
  injury feed. Where a book has posted a line the injury is already in the
  price, refreshed by 5 snapshots a week (tue-open, thu-pre-tnf, sat-midweek,
  sun-inactives 11:35 ET which is timed for the 90-minute inactive list, and
  sun-closing). Where no line exists the prior is fitted to lines posted BEFORE
  the news and is injury-blind. Right now that is 11 of the 20 legs. The page
  now says which: legs carry a `mkt` share, estimate legs are tagged "est" in
  the survival curve, and the holiday numbers state "real line" or "estimate".
  This is why the output is a hold-back list re-run weekly, never a 20-week
  script -- a script cannot survive a QB injury and the market reprices faster
  than we could.
- 2026-09-01: HOLIDAY-POOL DEPTH is now counted and shown, after the owner
  caught the tool calling CHI and BUF free in week 1 -- both play BOTH legs.
  The reservation policy holds ONE team per leg (LA 68% Thx, PHI 55% Xmas), so
  by its own arithmetic burning a worse holiday team costs nothing: you still
  field PHI. That is only true if PHI's number never moves, and it is a WEEK 16
  line, often off an estimate. Lose their QB in November and the held team is a
  dog with no fallbacks, because they were spent in week 1. The panel and the
  pinned bar now show options-left per leg (x of 10, y of 8), and spending a
  holiday team is never reported as simply free -- it reads "does not change who
  you field, but it was a holiday team -- 9 left of 10, 7 left of 8".
- 2026-09-01: survivor page reordered -- Scenario Simulator now sits directly
  under the week board, above Entry Portfolio. Owner: "it seem very disjointed
  because i have to scroll too far from the entry to the sim."
- 2026-09-01: PINNED LIVE BAR (#livebar, position:fixed, bottom). The board is
  30-odd rows, so by the time you are clicking a team every number is off
  screen -- you could not watch a value move while causing it to move.
- 2026-09-01: useTeam() now sets the picked entry active. The per-entry panel
  was welded to entry 1, so picking on entries 2 and 3 changed nothing visible;
  two clicks in three looked like a dead tool.
- 2026-09-01: the bar states the cost of every pick INCLUDING when it is zero
  ("CHI costs you nothing at either holiday leg"). Most picks are free, and
  silence about that is indistinguishable from a bug -- which is exactly how the
  owner reported it. Cost is measured by re-running the entry with that team
  omitted (simulate(...omitTeam)), not by diffing the previous render, which
  broke as soon as the active entry changed.
- 2026-09-01: simulator shows the ACTIVE ENTRY on its own, above the
  portfolio-wide cards. Found by the owner: he used a team on entry 1 and
  nothing on screen moved. Everything shown was an "any of my 10 entries"
  aggregate, which one pick cannot shift, so a correct tool looked broken. The
  per-entry panel (legs spent, teams left, its own holiday numbers) changes on
  every click. simulate() gained an onlyId argument to make it possible.
- 2026-09-01: pc() must return HTML entities. It returned the literal '<1%',
  which innerHTML parses as the start of a tag and silently drops -- blanking
  precisely the rarest numbers ("runs the table" for a single entry). Test now
  asserts the escaped form and forbids the raw one.
- 2026-09-01: SCENARIO SIMULATOR shipped on /survivor. Browser-side Monte Carlo
  over the whole remaining season, re-run on every pick/entry change, so the
  owner can try a plan and back out of it. Models a Circa season as 20 LEGS, not
  18 weeks: weeks 1-18 plus a Thanksgiving and a Christmas leg, each needing its
  own unused team, so the week-12 and week-16 slates exclude their holiday
  games. Seeded (mulberry32) so a number only moves when the board does.
- 2026-09-01: the simulator reports the team you FIELD at each holiday leg, not
  survival to it. Survival is the obvious metric and it is nearly useless here:
  holdbacks on vs off moved "any entry past Christmas" by under a point (1% vs
  1%), because most seasons are over before Thanksgiving. The same comparison on
  the team fielded moves 68% vs 45% at Thanksgiving and 55% vs 45% at Christmas.
  Shipping the survival number would have told the owner reservation does not
  matter, when what it actually says is he probably will not get to find out.
- 2026-09-01: pc() never rounds a real chance to a flat 0% ("<1%" instead).
  Running the table is ~0.4% with 3 entries; "0%" reads as impossible.
- 2026-09-01: test parses HOLIDAY_LEGS out of the served page and checks every
  one of the 9 games against the loaded schedule. Verified it fails on a
  corrupted leg — if the hardcoded legs ever go stale, every reservation the
  tool recommends is wrong, and it would otherwise break silently.
- 2026-09-01: nflverse loader no longer drops games that have no betting line.
  It skipped any row without a spread+total, so prod held 114 of 272 games and
  the survivor planner literally could not see week 16 — the question it exists
  to answer. Schedule row now always loads; a snapshot is created only where a
  real line exists, so an unpriced week stays visibly unpriced.
- 2026-09-01: `--wipe` is opt-in on the nflverse loader CLI. It was the default,
  one argument from dropping every table, including the purchased 2025 openers.
- 2026-09-01: unpriced games get a POWER-RATING PRIOR, tagged wp_source
  "prior" (systems/power_ratings.py). Fitted to THIS season's real market
  spreads — not last season's results — so it reflects the current roster.
  Ridge picked by 6-fold CV on held-out lines, NOT by intuition: the intuition
  was wrong. Shrinking hard is right when fitting to noisy game results, but
  these are lines, which the market has already regressed; shrinking again drove
  held-out error from 0.66 to 2.36 pts and squashed the best-to-worst spread
  from a realistic 13 pts to 7, biasing every projection toward a coin flip —
  the exact direction that makes a survivor tool understate the best available
  team. RIDGE is now 0.1, kept non-zero only as insurance for a thin slate.
  Fitted home field lands at 1.5 pts, which is the real NFL number and was not
  handed to it. A real line ALWAYS wins; the prior only fills gaps.
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
- 2026-08-25: survivor page — the per-pick "Use E1..E10" buttons run ACROSS,
  not down. Going 3 -> 10 entries turned that column into a 250px-tall stack,
  so every pick card was three times taller than the pick it described. Now a
  grid of at most five columns (useCols(), set inline from entryCount); pick
  rows are ~99px at 3 entries and at 10. Full "Use E1" wording is kept — the
  owner asked for it explicitly — and the mobile rule shrinks type/padding so
  five still fit a 360px phone rather than dropping to fewer columns.
  The ENTRY CARDS ARE DELIBERATELY LEFT ALONE: they look oversized with 10
  entries, but each card must show every team that entry has burned (a team
  is usable once), so that vertical space is the feature. A previous pass
  compacted them into a tab strip and was reverted — do not redo it.
- 2026-08-26 (later): **FIXED — real 2025 opening lines bought and applied.**
  540 credits on The Odds API historical archive (18 weekly calls x 3 markets
  x 10), Tuesday 12:00 ET each week to match scheduler.py's `tue-open` slot.
  Quota 18,660 -> 18,120; owner cancels the $30 plan Sept 15. Raw JSON kept in
  data/opening_lines/ so it never has to be re-bought; the 544 pre-existing
  2025 snapshot rows are backed up in data/backups/ before any deletion.
  loaders/opening_lines.py `apply` removed 272 synthetic rows (only those
  byte-identical to the close AND exactly 120h before it — the signature
  nflverse_loader leaves) and wrote 272 real ones. Movement is real:
  moneyline moved on 98% of games (mean 59 cents), spread on 68% (mean 0.85).
  GOTCHA: books post the WHOLE season months out, so one Tuesday call returns
  all 272 games. Taking them all would price a January game off a September
  line and call four months of information "CLV". _iter_snapshots() therefore
  keeps only games kicking off within 7 days of the snapshot.
  RESULT — the same 208 picks, resubmitted as endzone_edge_v2 (agent 3):
    v1 priced at the close  ROI -10.18%  CLV 0.0
    v2 priced at the open   ROI +15.44%  CLV +0.0054  beat_close 54.8%
  Identical 124-84-0 record. The whole 25-point ROI gap is ENTRY PRICE, which
  is the platform's thesis stated in one row. Do not read v2 as the model
  being good: it still picks winners at 59.6% vs the market's 63.0%, so its
  edge is TIMING, not selection.
  KNOWN ARTIFACT: picks carry as_of = kickoff-24h but get priced from the
  Tuesday snapshot, because that is the only one at-or-before that as_of in a
  one-snapshot-per-week backfill. Betting Tuesday is legitimate here (the
  model reads only prior-week games), but the label is looser than the trade.
  Self-corrects live from Week 1, where Thu/Sat/Sun snapshots exist and
  kickoff-24h really will price at Saturday. Left as-is rather than
  resubmitting a v3: a graded record is never deleted, and the v1/v2 pair is
  a better demonstration of CLV than a tidier board would be.

- 2026-08-26: **CLV WAS STRUCTURALLY ZERO ON BACKTEST DATA — now fixed above.**
  The EndZone submission graded out with avg_clv_prob exactly 0.0 across 208
  picks and beat_close_pct 0.0. Not a bug in the agent or the CLV math:
  loaders/nflverse_loader.py writes the SAME odds dict twice per game (once
  at kickoff-120h so agents picking days out find a price, once at kickoff as
  the close) because nflverse games.csv carries only one line per game — the
  close. No movement in the data means no CLV, by construction.
  Consequences: (1) the backtest board ranks CLV-first per invariant 5, but
  with CLV pinned at 0 it is effectively ROI-ranked; (2) a reader sees "0.0"
  and may take it as *neutral* CLV rather than *unmeasurable*. LIVE CLV is
  unaffected — the scheduler takes genuinely different snapshots in-season
  (task 4), which is where the product's core claim actually gets exercised.
  SUGGESTED (not done, needs owner): render backtest CLV as "n/a — no line
  movement in historical data" instead of 0.0, or backfill real opening
  lines (loaders/circa_historical.py notes the Odds API historical endpoint
  needs a PAID plan, ~$30/20k credits).
- 2026-08-31: reviewed SurvivorGrid/PoolCrunch (Mark's suggestion) and took
  two things, both just formulas. (1) FUTURE VALUE is now their definition:
  sum (wp - 0.5) over every remaining PRICED week the team is favoured, banded
  1-5 stars. Ours only found a team's single best week ahead, which misses the
  team favoured in eight straight weeks without ever standing out. The old
  "bigger edge Wk X" flag stays alongside it — that one is actionable.
  (2) systems/survivor_backtest.py, their Knockouts page rebuilt from our data.
  We deliberately do NOT copy the entry-weighted part: it needs real pick
  popularity, theirs comes from Yahoo/ESPN public pools, and that field is
  nothing like Circa's — borrowing it would mislead rather than help.
  WHAT IT SAYS ABOUT 2025, and it is sobering:
    calibration overall -1.9pt (fine) BUT the 60-70% band returned 53.8%
    against 64.9% predicted, -11.0pt over 78 picks. One season, small sample,
    and the reason survival odds must never be shown to two decimals.
    A greedy entry (best unused team weekly) DIED IN WEEK 5 on a 78.2%
    favourite, LA vs SF. A 2000-entry field picking randomly from the top 3
    each week: 32.6% wiped out in WEEK 3 alone on GB (79.1% favourite, lost
    10-13 at CLE), median entry dead week 5, 0.6% survived the season.
    Any simulated survival curve has to resemble that shape or it is wrong.
  Only 1 tie all season — but a tie kills a Circa entry, so it is counted as
  elimination throughout.
  NOT TAKEN: their P% / EV. Real popularity is the one thing we cannot source
  for Circa, so EV stays out rather than being built on a guess.
- 2026-08-25: survivor picks are now {t:team, w:week}, not bare team names.
  The old flat list had no week on it, so the tool could not tell that an
  entry had already picked this week — the owner hit this immediately by
  putting two teams on Entry 1 in week 4. One pick per entry per week is now
  enforced in useTeam() AND reflected in the board (that entry's Use buttons
  disable across the whole week), keyed to the week ON SCREEN (wkNo=w.week),
  not to "today". Removing the chip frees the week. normPicks() migrates old
  lists to w:0 = "week unknown": those still burn the team for the season but
  lock no week, so nobody's saved history breaks. The weekly split now skips
  entries that already picked this week and shows them as settled cards.
- 2026-08-25: survivor entries can be marked OUT (survivor_out_v1 =
  {entryId: weekNumber}). Simulating week 20 showed the real problem was not
  size — a 19-team card is only 159px and fits fine — but that the tool had
  no idea an entry could die: it offered all ten Use buttons and, worse, the
  weekly split kept diversifying across dead entries and pushed the live ones
  onto weaker teams. Out entries now drop from useCols()/the Use buttons,
  from renderPortfolio's ids, and from usedAny() (a corpse's history must not
  lock teams for the survivors); they collapse to a 35px strip that expands
  to show their history, and active() never resolves to a dead entry. Live
  cards gained a "13 left" count (NFL_TEAMS - used). Entries section at week
  20 with 2 alive: 657px -> 454px. Marking out is reversible ("back in") —
  nothing is ever deleted, per invariant #1.

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
