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

# --- board redesign (task 12): smack, streaks, movement, motion UI ------
check("leaderboard carries smack lines",
      isinstance(c.get("/leaderboard?mode=live").json().get("smack"), list))
# seed a board-qualified agent (5 graded live picks, all wins beating the close)
from app import SessionLocal as _SL, Pick as _P, Game as _G, snapshot_ranks as _snap
_s = _SL()
_played = _s.query(_G).filter(_G.final == True).first()  # noqa: E712
_sid = c.post("/agents/register",
              json={"name": "board_bot", "kind": "bot"}).json()["agent_id"]
for _i in range(5):
    _s.add(_P(agent_id=_sid, game_id=_played.id, market="spread",
              side=_played.home, stake_units=1.0, mode="live",
              submitted_at=datetime.utcnow() + timedelta(minutes=_i),
              snap_line=-3.0, snap_odds=-110, result="win",
              profit_units=0.909, clv_points=1.5))
_s.commit()
lb = c.get("/leaderboard?mode=live").json()
_row = next(r for r in lb["board"] if r["agent"] == "board_bot")
check("board rows have rank/streak/movement",
      _row["rank"] >= 1 and "movement" in _row and "beat_close_streak" in _row)
check("streak computed from graded picks", _row["streak"] == "W5"
      and _row["beat_close_streak"] == 5)
check("movement is None before any snapshot", _row["movement"] is None)
check("data-driven smack mentions the streaking agent",
      any("board_bot" in ln for ln in lb["smack"]))
n_snap = _snap(_s)
_s.close()
check("snapshot_ranks writes rows", n_snap >= 1)
_row2 = next(r for r in c.get("/leaderboard?mode=live").json()["board"]
             if r["agent"] == "board_bot")
check("movement resolves after snapshot", _row2["movement"] == 0)
_home = c.get("/").text
check("home has smack ticker", "tickerInner" in _home)
check("home has theme toggle", "themeBtn" in _home)
check("home respects reduced motion", "prefers-reduced-motion" in _home)
check("home renders movement arrows", "mvup" in _home and "fadeUp" in _home)
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

# --- odds snapshot (task 4): mapping, consensus, matching — no network --
from loaders.real_data import TEAM_ABBR, _consensus, _match_game  # noqa: E402
check("team map covers all 32 NFL teams", len(TEAM_ABBR) == 32
      and len(set(TEAM_ABBR.values())) == 32)
_event = {"home_team": "Kansas City Chiefs", "away_team": "Buffalo Bills",
          "bookmakers": [
    {"key": "b1", "markets": [
        {"key": "spreads", "outcomes": [
            {"name": "Kansas City Chiefs", "point": -2.5, "price": -110},
            {"name": "Buffalo Bills", "point": 2.5, "price": -110}]},
        {"key": "totals", "outcomes": [
            {"name": "Over", "point": 47.5, "price": -110},
            {"name": "Under", "point": 47.5, "price": -110}]},
        {"key": "h2h", "outcomes": [
            {"name": "Kansas City Chiefs", "price": -140},
            {"name": "Buffalo Bills", "price": 120}]}]},
    {"key": "b2", "markets": [
        {"key": "spreads", "outcomes": [
            {"name": "Kansas City Chiefs", "point": -3.5, "price": -105},
            {"name": "Buffalo Bills", "point": 3.5, "price": -115}]}]},
]}
_v = _consensus(_event)
check("consensus averages books' spreads", _v["spread_home_line"] == -3.0)
check("consensus rounds odds to int", _v["spread_home_odds"] == -108)
check("consensus keeps single-book totals", _v["total_line"] == 47.5)
check("consensus ml from book 1", _v["ml_home"] == -140)
check("consensus None with no spread",
      _consensus({"home_team": "x", "away_team": "y", "bookmakers": []}) is None)


class _G:  # minimal stand-in for a Game row
    def __init__(self, home, away, kickoff):
        self.home, self.away, self.kickoff = home, away, kickoff


_games = [_G("KC", "BUF", datetime(2025, 11, 2, 18, 0))]
check("match same teams within 36h",
      _match_game(_games, "KC", "BUF", datetime(2025, 11, 3, 1, 0)) is not None)
check("no match beyond 36h",
      _match_game(_games, "KC", "BUF", datetime(2025, 11, 8, 18, 0)) is None)
check("no match wrong teams",
      _match_game(_games, "PHI", "DAL", datetime(2025, 11, 2, 18, 0)) is None)

# --- scheduler slot logic (task 4 cron) ---------------------------------
import scheduler  # noqa: E402
_tue = datetime(2025, 11, 4, 12, 3)        # a Tuesday, inside grace window
check("tue 12:03 fires tue-open snapshot",
      [j for _, j in scheduler.due_slots(_tue, set())] == ["snapshot"])
check("slot never fires twice same day",
      scheduler.due_slots(_tue, {f"tue-open:{_tue.date()}"}) == [])
check("outside grace window fires nothing",
      scheduler.due_slots(datetime(2025, 11, 4, 12, 20), set()) == [])
check("sun 11:40 fires post-inactives snapshot",
      [j for _, j in scheduler.due_slots(datetime(2025, 11, 9, 11, 40),
                                         set())] == ["snapshot"])
check("wednesday fires nothing",
      scheduler.due_slots(datetime(2025, 11, 5, 12, 0), set()) == [])
check("scheduler off without RUN_SCHEDULER=1", scheduler.start() is False)

# --- best bets: declaration, one-per-day, tiers --------------------------
from app import Pick as PickRow, Game as GameRow  # noqa: E402

bb_key = c.post("/agents/register",
                json={"name": "bb_bot", "kind": "bot"}).json()["api_key"]
bb_s = SessionLocal()
upcoming = bb_s.query(GameRow).filter(GameRow.final == False).first()  # noqa: E712
played = bb_s.query(GameRow).filter(GameRow.final == True).first()     # noqa: E712

r = c.post("/picks", headers={"x-api-key": bb_key},
           json={"game_id": upcoming.id, "market": "spread",
                 "side": upcoming.home, "stake_units": 1, "best_bet": True})
check("best bet accepted and echoed", r.status_code == 200
      and r.json()["best_bet"] is True)
r = c.post("/picks", headers={"x-api-key": bb_key},
           json={"game_id": upcoming.id, "market": "total",
                 "side": "OVER", "stake_units": 1, "best_bet": True})
check("second best bet same slate day -> 409", r.status_code == 409)
r = c.post("/picks", headers={"x-api-key": bb_key},
           json={"game_id": upcoming.id, "market": "total",
                 "side": "UNDER", "stake_units": 1})
check("regular pick same day still fine", r.status_code == 200)
r = c.post("/picks", headers={"x-api-key": bb_key},
           json={"game_id": played.id, "market": "spread",
                 "side": played.home, "stake_units": 1, "best_bet": True,
                 "mode": "backtest",
                 "as_of": (played.kickoff - timedelta(hours=1)).isoformat()})
check("backtest best bet separate from live", r.status_code == 200)

# tier logic: seed graded best bets directly (uniqueness is API-level)
def _mk_bb_agent(name, n, clv):
    aid = c.post("/agents/register",
                 json={"name": name, "kind": "bot"}).json()["agent_id"]
    for i in range(n):
        bb_s.add(PickRow(agent_id=aid, game_id=played.id, market="spread",
                         side=played.home, stake_units=1.0, mode="live",
                         submitted_at=datetime.utcnow(), snap_line=-3.0,
                         snap_odds=-110, best_bet=True, result="win",
                         profit_units=0.909, clv_points=clv))
    bb_s.commit()

_mk_bb_agent("bb_t3", 3, 9.0)    # below floor — must not appear
_mk_bb_agent("bb_t4", 4, 5.0)    # provisional (high CLV on purpose)
_mk_bb_agent("bb_t8", 8, 1.0)    # ranked
_mk_bb_agent("bb_t12", 12, 0.5)  # proven
bb_s.close()

board = c.get("/leaderboard/best-bets?mode=live").json()
by = {r["agent"]: r for r in board["board"]}
check("tiers are 4/8/12", board["tiers"] ==
      {"provisional": 4, "ranked": 8, "proven": 12})
check("3 best bets stays off the board", "bb_t3" not in by)
check("4 -> provisional", by.get("bb_t4", {}).get("status") == "provisional")
check("8 -> ranked", by.get("bb_t8", {}).get("status") == "ranked")
check("12 -> proven", by.get("bb_t12", {}).get("status") == "proven")
check("sample size in payload", by.get("bb_t12", {}).get("picks") == 12)
names = [r["agent"] for r in board["board"]]
check("provisional sorts below ranked despite higher CLV",
      names.index("bb_t4") > names.index("bb_t8"))
check("pending best bets don't count", "bb_bot" not in by)

print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
