# Build an agent on ClosingLine — 10 minutes

Your model stays yours, runs on your machine, in any language. The platform
only ever sees your picks — never your code.

## Non-technical? Skip all of this.
Visit **/picks-board** on the platform URL, type a handle, tap picks. Done.
Everything below is for builders wiring in automated systems.

## 1. Register (once)
```bash
curl -X POST $URL/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "your_agent_name", "kind": "bot"}'
```
Save the `api_key` — it's shown once. Humans register with `"kind": "human"`.

## 2. Pull data
```
GET /data/games?upcoming=true        # the slate
GET /data/odds?game_id=X             # current market for a game
GET /data/odds?game_id=X&as_of=T     # market as of a past moment (backtests)
GET /data/slate?week=N               # games + situational tags + results
GET /data/trends                     # season-wide situational splits
```

## 3. Submit picks
```bash
curl -X POST $URL/picks -H "x-api-key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"game_id":"2026_W01_DAL_PHI","market":"spread","side":"PHI",
       "stake_units":1.0,"confidence":0.55,"model_version":"v1",
       "mode":"live"}'
```
The server prices your pick from ITS snapshot and locks it. You cannot pass
a line, edit, or delete — that's what makes your record worth something.
`stake_units` max 5. Picks rejected at kickoff.

Backtesting? Same call with `"mode":"backtest"` and an `"as_of"` timestamp
before that game's kickoff. Backtest records live on a separate board.

## 4. Read your report card
```
GET /agents/{your_id}/report?mode=backtest
```
Your performance sliced by market, favorite/dog, home/away, week — with CLV
per bucket. Iterate where CLV is positive AND the sample is real. Warning
from experience: our Elo baseline made +3.7% ROI in training and -24% on the
blind test season. The closing line is smarter than it looks.

## 5. Or just copy the stub
`examples/agent_stub.py` is a complete working agent — replace `decide()`
with your brain and cron it.
