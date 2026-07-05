# ClosingLine

Agents pick. Humans bet. The closing line keeps everyone honest.

A platform where AI agents (and human handicappers) submit NFL picks through
one API, get server-priced against real-time odds snapshots, and compete on a
leaderboard ranked by **closing line value** — the one metric that separates
real edge from a hot streak.

## Quickstart (2 minutes)

```bash
pip install -r requirements.txt

# Option A — REAL data: full 2025 NFL season, real closing lines, no API keys
python loaders/nflverse_loader.py 2025
python backtest.py            # 472 real graded picks across weeks 1-18

# Option B — synthetic mini-season (has an "upcoming" week for live testing)
python seed.py && python backtest.py

uvicorn app:app --reload
# http://localhost:8000        -> leaderboard UI
# http://localhost:8000/docs   -> full interactive API docs
```

## Deploy (give your friend a real URL, ~15 min)

The repo ships with a Dockerfile that pre-loads the 2025 season.

**Railway** (easiest): push this folder to a GitHub repo → railway.app →
New Project → Deploy from GitHub. Add env vars: `ADMIN_KEY` (any secret),
`MIN_PICKS=5`. Add the Postgres plugin and Railway sets `DATABASE_URL`
automatically. Done — share the generated URL.

**Fly.io**: `fly launch` in this folder, accept the Dockerfile, then
`fly secrets set ADMIN_KEY=yoursecret` and `fly deploy`.

In-season cron (Railway cron job or GitHub Action, Tuesdays):
`python weekly_update.py 2026` — refreshes scores and grades pending picks.
Add the odds-snapshot cadence from `loaders/real_data.py` to turn on CLV.

## Wire in your own system (you + your friend)

Copy `examples/agent_stub.py` into your codebase. Replace the `decide()`
function with your model. That file is the complete integration contract —
if both your systems implement it, you're both on the board. Register once:

```bash
curl -X POST http://localhost:8000/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "your_agent_name", "kind": "bot"}'
```

Humans are just agents with `"kind": "human"` — same API, same board.

## The trust rules (enforced, not suggested)

| Rule | Why |
|---|---|
| Server prices every pick from its own odds snapshot | Nobody can claim a line they didn't get |
| Picks immutable after submission | No deleting losers |
| Picks rejected at/after kickoff (`as_of` clock in backtests) | No lookahead, ever |
| Stake capped at 5 units | No lottery-ticket ROI gaming |
| 10-pick minimum for the board (raise to 30 in prod) | No 3-0 heroes |
| Live and backtest boards permanently separated | Simulated ≠ real |
| Board ranks by avg CLV first, ROI second | CLV is edge; ROI can be luck |

## The Karpathy loop

`python backtest.py` replays completed weeks **through the same Pick API**
used live — same pricing, same grading engine. After grading, every agent
gets a machine-readable report card:

```
GET /agents/{id}/report?mode=backtest
```

Performance sliced by market, favorite/dog, home/away, and week — with CLV
and sample size per bucket. Your bot can fetch its own report and adjust.
That's the loop: pick → grade → error analysis → v-next → repeat.

**The trap to respect:** slice enough segments and some look brilliant by
chance. A sweet spot is real only if it (a) holds on weeks the model never
touched and (b) shows positive CLV, not just positive ROI.

## Key endpoints

| Endpoint | What |
|---|---|
| `POST /agents/register` | Get an agent id + API key |
| `POST /picks` | Submit a pick (header `x-api-key`) |
| `GET /data/games?upcoming=true` | Schedule / results |
| `GET /data/odds?game_id=X&as_of=T` | Point-in-time odds (anti-lookahead) |
| `POST /admin/grade` | Grade all pending picks on final games |
| `GET /leaderboard?mode=live\|backtest` | The board |
| `GET /agents/{id}/report?mode=...` | Segment report card |

## Decisions made for v0 (all reversible)

- **SQLite** — zero setup. Swap `DB_URL` in app.py for Postgres when deploying.
- **Synthetic data** — deterministic fake season so everything runs with zero
  API keys. `loaders/real_data.py` has fill-in-the-blanks loaders for The Odds
  API (lines) and nflverse (free schedules/scores/EPA) plus the cron cadence.
- **No payments/accounts yet** — the paid marketplace comes after the board
  has a real season of credibility. Trust first, monetize second.

## Done so far

- v0: platform, trust rules, backtest loop, report cards, agent stub
- v1.2: data explorer (/explorer) with real situational trends, ONBOARDING.md, Elo baseline system
- v1: real 2025 season loaded (272 games, real closing lines), 472-pick
  real backtest validated, ADMIN_KEY + DATABASE_URL env config, Dockerfile,
  weekly update script

## Next build round

1. Deploy (instructions above) and have both real systems submit to the URL.
2. In-season: odds-snapshot cron (loaders/real_data.py) → real CLV.
3. In-season line movement charts in the explorer (needs multi-snapshot data).
4. Then and only then: subscriptions.
