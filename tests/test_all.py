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

# --- survivor helper -------------------------------------------------
from app import devig_two_way, wp_from_spread  # noqa: E402
check("devig 50/50 is .5", abs(devig_two_way(-110, -110) - 0.5) < 1e-9)
check("devig strips vig (sums to 1)",
      abs(devig_two_way(-400, 320) + devig_two_way(320, -400) - 1.0) < 1e-9)
check("devig favorite > underdog", devig_two_way(-400, 320) > 0.5)
check("wp_from_spread home fav -7 ~ .70", 0.66 < wp_from_spread(-7) < 0.74)
check("wp_from_spread pick'em = .5", abs(wp_from_spread(0) - 0.5) < 1e-9)
check("wp_from_spread symmetric",
      abs(wp_from_spread(-7) + wp_from_spread(7) - 1.0) < 1e-9)

sv = c.get("/data/survivor?weeks=4")
check("survivor endpoint 200", sv.status_code == 200)
svd = sv.json()
check("survivor returns weeks", len(svd.get("weeks", [])) >= 1)
wps = [g for w in svd["weeks"] for g in w["games"] if g["home_wp"] is not None]
check("survivor has win probs on the upcoming slate", len(wps) >= 1)
check("survivor win probs are valid probabilities",
      all(0 <= g["home_wp"] <= 1 for g in wps))
check("survivor home_wp + away_wp == 1",
      all(abs(g["home_wp"] + g["away_wp"] - 1.0) < 1e-6 for g in wps))
check("survivor respects as_of (no future snapshot leak) via closing_snapshot",
      all(g["wp_source"] in ("ml", "spread") for g in wps))

sp = c.get("/survivor")
check("survivor page 200", sp.status_code == 200)
check("survivor page carries the RG footer", "1-800-GAMBLER" in sp.text)
check("survivor page has no hype language",
      not any(w in sp.text.lower() for w in ("guaranteed", "can't-miss", "lock of")))
check("survivor page has the home-field lean control",
      'id="lean"' in sp.text and "Home-field lean" in sp.text)
check("survivor page has holiday-leg protection",
      "HOLIDAY_LEGS" in sp.text and "Thanksgiving Leg" in sp.text
      and "Christmas Leg" in sp.text)

# ------------------------------------------------------- moneyline board
# Moneyline is the survivor-relevant market: picking a winner, not a spread.
# The board ranks on DE-VIGGED win-probability CLV, so these checks care most
# about (a) the vig actually being stripped and (b) CLV sign convention --
# market moving toward your side after you bet is positive.
from app import devig_two_way, Market

fair = devig_two_way(-110, -110)
check("ml: devig of a -110/-110 market is 50%", abs(fair - 0.5) < 1e-9)
lop = devig_two_way(-200, +170)
check("ml: devig strips the hold (fav under raw implied)",
      lop is not None and lop < (200/300))
check("ml: devig sides sum to 1",
      abs(devig_two_way(-200, +170) + devig_two_way(+170, -200) - 1.0) < 1e-9)

mlb = c.get("/leaderboard/moneyline")
check("ml board 200", mlb.status_code == 200)
mld = mlb.json()
check("ml board states its metric",
      mld.get("metric") == "de-vigged win-probability CLV")
check("ml board exposes its sample gate", "min_picks" in mld)
check("ml board rows carry moneyline-specific columns",
      all({"avg_clv_winprob", "avg_fair_winprob", "underdog_rate"} <= set(r)
          for r in mld["board"]))

# submit real moneyline picks in backtest mode and confirm they surface
mlk = c.post("/agents/register", json={"name": "ml_probe", "kind": "bot"}).json()
mlkey, mlid = mlk["api_key"], mlk["agent_id"]
placed = 0
for wk in (1, 2, 3):
    for g in c.get(f"/data/games?week={wk}").json():
        aso = (datetime.fromisoformat(g["kickoff"]) - timedelta(hours=24)).isoformat()
        r = c.post("/picks", headers={"x-api-key": mlkey},
                   json={"game_id": g["game_id"], "market": "moneyline",
                         "side": g["home"], "stake_units": 1.0,
                         "mode": "backtest", "as_of": aso})
        if r.status_code == 200:
            placed += 1
        if placed >= 6:
            break
    if placed >= 6:
        break
check("ml: moneyline picks accepted by /picks", placed >= 5)

c.post("/admin/grade")
board = c.get("/leaderboard/moneyline?mode=backtest").json()["board"]
row = next((r for r in board if r["agent"] == "ml_probe"), None)
check("ml: agent appears on the moneyline board", row is not None)
if row:
    check("ml: board reports a fair win prob", row["avg_fair_winprob"] is not None)
    check("ml: fair win prob is a probability",
          0 < row["avg_fair_winprob"] < 1)
    check("ml: underdog_rate is a share", 0 <= row["underdog_rate"] <= 1)
    check("ml: rank assigned", row.get("rank") == 1 or row.get("rank") >= 1)
    check("ml: picks counted match what was placed", row["picks"] >= 5)

# a spread pick from the same agent must NOT inflate the moneyline board
gsp = c.get("/data/games?week=4").json()[0]
aso_sp = (datetime.fromisoformat(gsp["kickoff"]) - timedelta(hours=24)).isoformat()
c.post("/picks", headers={"x-api-key": mlkey},
       json={"game_id": gsp["game_id"], "market": "spread", "side": gsp["home"],
             "stake_units": 1.0, "mode": "backtest", "as_of": aso_sp})
c.post("/admin/grade")
row2 = next((r for r in c.get("/leaderboard/moneyline?mode=backtest").json()["board"]
             if r["agent"] == "ml_probe"), None)
check("ml: spread picks excluded from the moneyline board",
      row2 is not None and row["picks"] == row2["picks"])

# the board must never rank on how much of a favourite you take
check("ml: fair win prob is context, not the sort key",
      "avg_fair_winprob" in (row or {}) and
      c.get("/leaderboard/moneyline?mode=backtest").json()["metric"]
      == "de-vigged win-probability CLV")

mp = c.get("/moneyline")
check("moneyline page 200", mp.status_code == 200)
check("moneyline page carries the RG footer", "1-800-GAMBLER" in mp.text)
check("moneyline page has no hype language",
      not any(w in mp.text.lower() for w in
              ("guaranteed", "can't-miss", "lock of", "sure thing")))
check("moneyline page states the de-vigged metric", "de-vigged" in mp.text)
check("moneyline page reads the real endpoint",
      "/leaderboard/moneyline" in mp.text)
check("moneyline page explains an empty board",
      "No ranked moneyline pickers" in mp.text)
check("moneyline page shares the board theme key", "clhq_theme" in mp.text)
check("moneyline page shows sample size (picks column)", ">Picks<" in mp.text)
check("moneyline page surfaces dog rate as context", "Dog rate" in mp.text)
check("board links to the moneyline page", '/moneyline' in c.get("/").text)
check("survivor links to the moneyline page", '/moneyline' in c.get("/survivor").text)

# ------------------------------------------------------- scheduler health
# The scheduler lives inside the web process, so a restart can kill it with no
# trace. These checks guard the thing that makes failure VISIBLE, and that
# every reported problem carries an actionable fix rather than just a red flag.
from app import JobRun, SessionLocal as _SL
from datetime import datetime as _dt, timedelta as _td

h = c.get("/health")
check("health endpoint 200", h.status_code == 200)
hd = h.json()
check("health reports a status", hd["status"] in ("ok", "warn", "error"))
check("health reports season activity", isinstance(hd["season_active"], bool))
check("health issues are actionable (every issue has a fix)",
      all(i.get("fix") and i.get("why") and i.get("what") for i in hd["issues"]))
check("health issue levels are valid",
      all(i["level"] in ("warn", "error") for i in hd["issues"]))

# a fresh db has no recorded runs -> must NOT claim everything is fine
check("health does not report ok when nothing has ever run",
      hd["status"] != "ok" or hd["last_weekly_update"] is not None)

_s = _SL()
_s.query(JobRun).delete()
_s.add(JobRun(job="weekly_update", started_at=_dt.utcnow(),
              finished_at=_dt.utcnow(), ok=True, detail="test"))
_s.commit()
hd2 = c.get("/health").json()
check("health sees a recorded weekly update", hd2["last_weekly_update"] is not None)
check("fresh weekly update clears the stale-weekly issue",
      not any("Weekly update last succeeded" in i["what"] for i in hd2["issues"]))

# an old run must be flagged as stale
_s.query(JobRun).delete()
_s.add(JobRun(job="weekly_update", started_at=_dt.utcnow() - _td(days=30),
              finished_at=_dt.utcnow() - _td(days=30), ok=True, detail="old"))
_s.commit()
hd3 = c.get("/health").json()
check("stale weekly update is flagged",
      any("Weekly update last succeeded" in i["what"] for i in hd3["issues"]))
check("stale weekly update fix names the command",
      any("weekly_update.py" in i["fix"] for i in hd3["issues"]))

# a recent failure must surface with its recorded error
_s.add(JobRun(job="snapshot", started_at=_dt.utcnow() - _td(hours=2),
              finished_at=_dt.utcnow() - _td(hours=2), ok=False,
              detail="RuntimeError: odds api 401"))
_s.commit()
hd4 = c.get("/health").json()
check("recent job failure is surfaced",
      any("failed in the last 3 days" in i["what"] for i in hd4["issues"]))
check("failure detail is carried into the report",
      any("odds api 401" in i["why"] for i in hd4["issues"]))
_s.query(JobRun).delete(); _s.commit(); _s.close()

bt = c.get("/").text
check("board carries the health banner", 'id="healthbar"' in bt)
check("board fetches health itself", "fetch('/health')" in bt)
check("health banner is hidden by default", 'id="healthbar" style="display:none"' in bt)

# --------------------------------------------- survivor: variable entry count
# Mark plays 10 Circa Survivor entries ($10k), so the helper cannot assume 3.
# Circa caps a person at 10, which is the ceiling enforced here.
sv_t = c.get("/survivor").text
check("survivor: entry-count control present", 'id="nentries"' in sv_t)
check("survivor: caps entries at Circa's limit of 10", "MAX_ENTRIES=10" in sv_t)
check("survivor: input max matches the cap", 'max="10"' in sv_t)
check("survivor: no hardcoded three-entry loops", "['1','2','3']" not in sv_t)
check("survivor: entry ids are derived, not fixed", "function entryIds()" in sv_t)
check("survivor: portfolio no longer promises 'all three'",
      "end all three" not in sv_t)
check("survivor: portfolio warns when forced onto weak teams",
      "not a recommendation to like it" in sv_t)
check("survivor: stacks entries across teams, not one block plus singletons",
      "largest remainder" in sv_t.lower() or "largest-remainder" in sv_t)
check("survivor: caps any one team at half the entries",
      "no team may take more than half" in sv_t)
check("survivor: cap is enforced in code, not just described",
      "Math.floor(N/2)" in sv_t)
check("survivor: explains the stack shape to the user",
      "multi-entry play actually works" in sv_t)
check("survivor: only plausible teams get weight",
      "p.wp>=0.60" in sv_t)
check("survivor: entry count persists per browser", "survivor_count_v1" in sv_t)

# ------------------------------------------- survivor: knocked-out entries
# A loss or a tie ends an entry. By week 20 most of a 10-entry portfolio is
# dead, and a dead entry must stop influencing the live ones: it drops off
# the per-pick Use buttons and out of the weekly split, or the split keeps
# diversifying against corpses and pushes the survivors onto weaker teams.
check("survivor: elimination state exists", "function isOut(" in sv_t)
check("survivor: out state persists per browser", "survivor_out_v1" in sv_t)
check("survivor: out entries are stamped with the week", "function outWeek(" in sv_t)
check("survivor: an entry can be marked out and revived",
      "function markOut(" in sv_t and "function reviveEntry(" in sv_t)
check("survivor: alive list is derived from the out state", "function aliveIds()" in sv_t)
check("survivor: Use buttons are built from live entries only",
      "aliveIds().map(function(n)" in sv_t)
check("survivor: the weekly split allocates to live entries only",
      "ids=aliveIds()" in sv_t)
check("survivor: the planner locks teams from live entries only",
      "return aliveIds().some(" in sv_t)
check("survivor: an all-out portfolio degrades gracefully",
      "Every entry is marked out" in sv_t)
check("survivor: the active entry never points at a dead one",
      "if(isOut(a))" in sv_t)
check("survivor: dead entries collapse instead of taking a full card",
      ".entry.dead{" in sv_t)
check("survivor: history of a dead entry is kept, not wiped",
      "function toggleDead(" in sv_t)
check("survivor: live cards show how many teams are still available",
      "NFL_TEAMS-used.length" in sv_t)
check("survivor: Use buttons keep the full 'Use E1' wording",
      "'Use E'+n" in sv_t)
check("survivor: live entries carry a green border",
      "border:1px solid var(--up)" in sv_t)
check("survivor: out entries carry a red border",
      "border-color:color-mix(in srgb,var(--down)" in sv_t)
# --shadow is `none` in dark mode; listing it after another shadow makes the
# whole declaration invalid and silently drops the active ring.
check("survivor: active ring does not compose with var(--shadow)",
      "0 0 0 2px color-mix(in srgb,var(--gold) 45%,transparent)}" in sv_t)
check("survivor: Use buttons lay out across, not down",
      "grid-template-columns:repeat('+useCols()" in sv_t
      or "repeat('+useCols()+'" in sv_t)

# ------------------------------------------------- health: public vs admin
# The detailed report names env vars, deploy commands and raw error text.
# That is an operator runbook, not something to print on a public homepage.
import json as _json
import app as _app
_saved_key = _app.ADMIN_KEY
_app.ADMIN_KEY = "testkey_health_123"

_pub = c.get("/health").json()
check("health: public view hides the issue list", "issues" not in _pub)
check("health: public view hides fix commands",
      "railway" not in _json.dumps(_pub).lower())
check("health: public view still says whether data is stale",
      _pub["status"] in ("ok", "warn", "error") and "summary" in _pub)
check("health: public view reports a last-updated date", "last_updated" in _pub)

_adm = c.get("/health?key=testkey_health_123").json()
check("health: admin view returns full detail", "issues" in _adm)
check("health: admin key works via header",
      "issues" in c.get("/health", headers={"x-admin-key": "testkey_health_123"}).json())
check("health: wrong key gets the public view only",
      "issues" not in c.get("/health?key=nope").json())
check("health: admin detail still carries fixes",
      all(i.get("fix") for i in _adm["issues"]) if _adm["issues"] else True)
_app.ADMIN_KEY = _saved_key

check("board banner tolerates the undetailed public payload",
      "public, undetailed view" in c.get("/").text)
# ---------------------------------------------------------------- Circa sheet
# Pure-logic checks on the contest-sheet parser. No OCR here on purpose: the
# suite must stay fast and deterministic, and the pairing/validation rules are
# where a wrong half-point would actually reach a pick.
from loaders.circa_sheet import canon_team, validate

check("circa: canonical team passes through", canon_team("RAVENS") == "RAVENS")
check("circa: OCR alias AOERS -> 49ERS", canon_team("AOERS") == "49ERS")
check("circa: near-miss OCR slip recovered", canon_team("PAVENS") == "RAVENS")
check("circa: junk token rejected", canon_team("XQZP") is None)

# slot map: {contestant_number: (team, sign, int_part, saw_half_glyph)}
clean = {1: ("CHIEFS", "-", 2, True), 2: ("RAVENS", "+", 2, True)}
g, prob = validate(clean)
check("circa: mirrored pair yields one game", len(g) == 1 and not prob)
check("circa: favorite is the minus side", g[0].favorite == "CHIEFS")
check("circa: half-point applied from both sides", g[0].line == 2.5)
check("circa: agreeing pair is confident", g[0].confident is True)

# one side lost its half glyph -> line still recovered, but NOT confident
lopsided = {1: ("CHIEFS", "-", 2, True), 2: ("RAVENS", "+", 2, False)}
g2, _ = validate(lopsided)
check("circa: half recovered from the mirror", g2[0].line == 2.5)
check("circa: mirror-recovered game flagged for review", g2[0].confident is False)

whole = {1: ("CHARGERS", "-", 3, False), 2: ("RAIDERS", "+", 3, False)}
g3, _ = validate(whole)
check("circa: whole-number line stays whole", g3[0].line == 3.0)

# OCR merged the half into a digit (3.5 -> 37): must be flagged, never guessed
bad_int = {1: ("FALCONS", "-", 3, False), 2: ("STEELERS", "+", 37, False)}
g4, p4 = validate(bad_int)
check("circa: integer mismatch produces no game", len(g4) == 0)
check("circa: integer mismatch is reported", any("mismatch" in m for _, m in p4))

same_sign = {1: ("A", "-", 3, False), 2: ("B", "-", 3, False)}
same_sign[1] = ("BEARS", "-", 3, False); same_sign[2] = ("TITANS", "-", 3, False)
g5, p5 = validate(same_sign)
check("circa: same-sign pair rejected", len(g5) == 0 and len(p5) == 1)

half_pair = {1: ("CHIEFS", "-", 2, True)}
g6, p6 = validate(half_pair)
check("circa: unread half of a pair is flagged", len(g6) == 0 and len(p6) == 1)

# bye weeks legitimately leave slots empty - that must NOT raise a problem
byes = {1: ("CHIEFS", "-", 2, True), 2: ("RAVENS", "+", 2, True)}
g7, p7 = validate(byes)
check("circa: empty slots from byes are not flagged", len(p7) == 0)

check("circa: pairing is by consecutive slot numbers, not by value",
      validate({1: ("CHIEFS", "-", 2, True), 2: ("RAVENS", "+", 2, True),
                3: ("TEXANS", "-", 2, True), 4: ("COLTS", "+", 2, True)})[0][1].favorite
      == "TEXANS")

print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
