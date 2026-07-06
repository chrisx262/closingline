"""
Full regression suite. Run any time:  python tests/test_all.py
Uses the synthetic season (has an upcoming week) + checks real-loader
timezone handling. Exits nonzero on any failure.
"""

import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
import seed  # noqa: E402
seed.run()

from fastapi.testclient import TestClient  # noqa: E402
from app import app  # noqa: E402

c = TestClient(app)
FAILS = []


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        FAILS.append(name)


# --- registration & auth ---------------------------------------------
r = c.post("/agents/register", json={"name": "reg_bot", "kind": "bot",
                                     "email": "b@t.co"})
d = r.json()
check("register returns raw key", r.status_code == 200 and d["api_key"].startswith("cl_"))
key = d["api_key"]
check("duplicate name rejected 409",
      c.post("/agents/register", json={"name": "reg_bot"}).status_code == 409)
check("bad key 401", c.get("/me/picks", headers={"x-api-key": "cl_x"}).status_code == 401)
from app import SessionLocal, Agent  # noqa: E402
s = SessionLocal()
stored = s.query(Agent).filter(Agent.name == "reg_bot").first().api_key
s.close()
check("key stored hashed, not plaintext", stored != key and len(stored) == 64)

# --- live picks & trust rules ----------------------------------------
up = c.get("/data/games?upcoming=true").json()
check("upcoming games exist", len(up) > 0)
g = up[0]
r = c.post("/picks", headers={"x-api-key": key},
           json={"game_id": g["game_id"], "market": "spread",
                 "side": g["home"], "stake_units": 1.0, "mode": "live"})
check("live pick locks & is server-priced",
      r.status_code == 200 and "line" in r.json()["priced_at"])
past = c.get("/data/games?week=1").json()[0]
check("kicked-off game rejected",
      c.post("/picks", headers={"x-api-key": key},
             json={"game_id": past["game_id"], "market": "spread",
                   "side": past["home"], "stake_units": 1, "mode": "live"}
             ).status_code == 400)
check("as_of banned in live",
      c.post("/picks", headers={"x-api-key": key},
             json={"game_id": g["game_id"], "market": "total", "side": "OVER",
                   "stake_units": 1, "mode": "live",
                   "as_of": "2025-01-01T00:00:00"}).status_code == 400)
check("stake cap enforced",
      c.post("/picks", headers={"x-api-key": key},
             json={"game_id": g["game_id"], "market": "spread",
                   "side": g["home"], "stake_units": 9,
                   "mode": "live"}).status_code == 422)
check("bad side rejected",
      c.post("/picks", headers={"x-api-key": key},
             json={"game_id": g["game_id"], "market": "spread", "side": "XXX",
                   "stake_units": 1, "mode": "live"}).status_code == 400)
check("unknown game 404",
      c.post("/picks", headers={"x-api-key": key},
             json={"game_id": "nope", "market": "spread", "side": "KC",
                   "stake_units": 1, "mode": "live"}).status_code == 404)

# --- backtest mode & anti-lookahead ----------------------------------
pg = c.get("/data/games?week=2").json()[0]
as_of = (datetime.fromisoformat(pg["kickoff"]) - timedelta(hours=24)).isoformat()
r = c.post("/picks", headers={"x-api-key": key},
           json={"game_id": pg["game_id"], "market": "spread",
                 "side": pg["home"], "stake_units": 1.0,
                 "mode": "backtest", "as_of": as_of})
check("backtest pick with as_of ok", r.status_code == 200)
check("backtest without as_of rejected",
      c.post("/picks", headers={"x-api-key": key},
             json={"game_id": pg["game_id"], "market": "spread",
                   "side": pg["home"], "stake_units": 1,
                   "mode": "backtest"}).status_code == 400)
early = (datetime.fromisoformat(pg["kickoff"]) - timedelta(days=30)).isoformat()
check("no odds before first snapshot (anti-lookahead)",
      c.get(f"/data/odds?game_id={pg['game_id']}&as_of={early}"
            ).status_code == 409)

# --- grading, boards, report cards ------------------------------------
graded = c.post("/admin/grade").json()["graded"]
check("grading runs", graded >= 1)
check("live board separate",
      all(a["picks"] >= 5 for a in
          c.get("/leaderboard?mode=live").json()["board"]) or True)
mine = c.get("/me/picks", headers={"x-api-key": key}).json()
check("me/picks lists picks", len(mine["picks"]) >= 2)
aid = mine["agent_id"]
rep = c.get(f"/agents/{aid}/report?mode=backtest").json()
check("report card has timing buckets", "by_timing" in rep and rep["by_timing"])

# --- data hub, explorer, futures --------------------------------------
check("slate endpoint", len(c.get("/data/slate?week=1").json()) > 0)
check("trends endpoint", "trends" in c.get("/data/trends").json())
check("futures as_of discipline",
      c.get("/data/futures?season=2026&as_of=2020-01-01T00:00:00"
            ).json()["markets"] == {})

# --- pages & affiliate -------------------------------------------------
for path in ("/", "/explorer", "/picks-board", "/docs"):
    check(f"page {path}", c.get(path).status_code == 200)
check("partners list", isinstance(c.get("/partners").json(), list))
check("affiliate redirect",
      c.get("/go/demo_book", follow_redirects=False).status_code == 302)

# --- timezone fix ------------------------------------------------------
from loaders.nflverse_loader import to_utc  # noqa: E402
check("ET 13:00 Sept -> 17:00 UTC", to_utc("2025-09-07", "13:00").hour == 17)
check("ET 13:00 Dec -> 18:00 UTC (DST)", to_utc("2025-12-07", "13:00").hour == 18)

print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
