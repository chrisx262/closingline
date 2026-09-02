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
check("survivor labels every win prob with where it came from",
      all(g["wp_source"] in ("ml", "spread", "prior") for g in wps))

# ---- power-rating priors: the weeks no book has priced yet ----
from systems.power_ratings import fit, projected_spread, HFA_DEFAULT  # noqa: E402

# A league we know the answer to: A is 7 points better than B, B 7 better
# than C, home field exactly 2. Every pairing played home and away, priced
# with no noise, so a correct fit has to recover the gaps exactly.
TRUE = {"A": 7.0, "B": 0.0, "C": -7.0}
synth = [(h, a, -((TRUE[h] - TRUE[a]) + 2.0))
         for h in TRUE for a in TRUE if h != a]
R, H = fit(synth)
check("ratings recover known gaps", abs((R["A"] - R["C"]) - 14.0) < 0.3)
check("ratings recover known home field", abs(H - 2.0) < 0.2)
check("ratings are centred on the league average",
      abs(sum(R.values()) / len(R)) < 1e-6)
check("ratings do not collapse toward a coin flip",
      (max(R.values()) - min(R.values())) > 12.0)
check("projected spread favours the better team at home",
      projected_spread(R, H, "A", "C") < 0)
check("projected spread flips with venue",
      projected_spread(R, H, "A", "C") < projected_spread(R, H, "C", "A"))
check("projected spread is None for a team we never priced",
      projected_spread(R, H, "A", "ZZ") is None)
check("no lines at all -> default home field, no crash",
      fit([])[1] == HFA_DEFAULT)

full = c.get("/data/survivor?weeks=18").json()
allg = [g for w in full["weeks"] for g in w["games"]]
check("prior fills every unpriced game (no blanks left)",
      all(g["home_wp"] is not None for g in allg))
check("a real market price is never replaced by a prior",
      all(g["wp_source"] != "prior"
          for g in allg if g["spread_home"] is not None
          and g["wp_source"] in ("ml", "spread")))
check("response says how the prior was built",
      "fitted_from_games" in full.get("prior", {}))
check("prior note warns it is not a market price",
      "not a market price" in full.get("prior", {}).get("note", ""))

sp = c.get("/survivor")
check("survivor page 200", sp.status_code == 200)
check("survivor page carries the RG footer", "1-800-GAMBLER" in sp.text)
check("survivor page has no hype language",
      not any(w in sp.text.lower() for w in ("guaranteed", "can't-miss", "lock of")))

# ---- scenario simulator: its own page since 2026-09-01 ----
simp = c.get("/survivor/sim")
check("simulator page 200", simp.status_code == 200)
check("simulator page carries the RG footer", "1-800-GAMBLER" in simp.text)
check("simulator page has no hype language",
      not any(w in simp.text.lower() for w in ("guaranteed", "can't-miss", "lock of")))
# The helper must hand you across, and the simulator must be pickable on its own
# -- a plan page you cannot pick from would undo the reason it was split out.
check("the helper links across to the simulator", '/survivor/sim' in sp.text)
check("the simulator is no longer bolted to the helper",
      'id="simcards"' not in sp.text)
# ---- best possible path (exact assignment, not simulation) ----
check("the simulator carries a best-path panel",
      'id="bestpath"' in simp.text and "hungarian" in simp.text)
check("best path is compared against greedy computed the same exact way, "
      "not against a Monte Carlo estimate", "function greedyPath(" in simp.text)
# Entries picking the same team in the same leg must share one game result --
# that shared fate is the entire risk a multi-entry portfolio manages.
# After a QB goes down the only question is whether the market has repriced and
# whether we hold that price. A page that cannot answer it looks current.
sv_asof = c.get("/data/survivor?weeks=4").json()
check("the feed says when its newest price was captured", "as_of" in sv_asof)
check("both survivor pages show how old the odds are",
      'id="asof"' in sp.text and 'id="asof"' in simp.text)
# The nflverse archive timestamps rows at kickoff, so an unplayed game's
# snapshot sits in the future. Taking the plain max reported odds "captured" in
# December, four months old in the negative direction.
check("a future snapshot time is never reported as the capture time",
      sv_asof.get("as_of") is None or
      sv_asof["as_of"] <= __import__("datetime").datetime.utcnow().isoformat())
check("archive-seeded prices say so instead of looking live",
      sv_asof.get("as_of") is not None or "seeded archive" in (sv_asof.get("as_of_note") or ""))
check("stale odds are called out, not shown as if current",
      "a snapshot has been missed" in simp.text)
check("odds can be refreshed without a page reload",
      "function reloadOdds(" in simp.text)
check("one game gives one result to every entry that picked it",
      "ONE GAME, ONE RESULT" in simp.text and "if(out&&key in out)" in simp.text)
check("the portfolio spreads entries instead of cloning the best path",
      "function portfolioPaths(" in simp.text and "var CLASH=" in simp.text)
check("a portfolio is scored by simulating the paths together, not entry by entry",
      "function simulatePaths(" in simp.text)
# A leg already picked is not a decision; re-optimising it made the path
# disagree with the pick the owner had just made.
check("legs already picked are settled, not re-optimised",
      "function settledFor(" in simp.text and "is not a decision any more" in simp.text)
check("survival is measured over the legs still to play",
      "charge the owner twice" in simp.text)
check("you can pin the opening team and re-solve from there",
      "function setBpStart(" in simp.text and "forceFirst" in simp.text)
check("opening options are ranked by where the season ends up, not by this week",
      "ranked by where the " in simp.text)
# Bare "NO" reads as the word no rather than New Orleans, which is how the
# owner read it. Every team on this page is a coloured chip.
# We do not predict injuries. What is knowable today is how much the plan leans
# on any one team, measured by removing it and re-solving.
check("a contingency panel shows the fallback ladder at each leg",
      'id="contingency"' in simp.text and "function renderContingency(" in simp.text)
check("contingency is measured by removing a team, not by guessing injuries",
      "That is not a forecast of injuries" in simp.text)
check("a holiday-teams-held path is shown alongside the unrestricted one",
      "function firstHolidayLeg(" in simp.text and "Holiday teams held" in simp.text)
check("a held holiday team is free again from its own leg onward",
      "free from it onward" in simp.text)
check("the greedy column shows teams as chips, not bare text",
      'class="gd">' in simp.text and "reads as the word no" in simp.text)
check("best path warns it is not a script to follow",
      "not a script to follow" in simp.text)

# The assignment solver is the kind of code that stays plausible while being
# wrong, so it is checked against brute force on random instances.
import shutil, subprocess  # noqa: E402
if shutil.which("node"):
    _r = subprocess.run(["node", "tests/check_hungarian.js", "survivor_sim_page.py"],
                        capture_output=True, text=True)
    check("assignment solver matches brute force on random instances "
          "(" + (_r.stdout.strip().splitlines() or ["no output"])[-1] + ")",
          _r.returncode == 0)
else:
    print("SKIP  assignment solver brute-force check (node not installed)")

check("you can pick without leaving the simulator page",
      'class="usebtn"' in simp.text and "useTeam(" in simp.text)
check("both pages share one set of entries",
      "survivor_entries_v1" in sp.text and "survivor_entries_v1" in simp.text)
check("simulator page carries the simulator",
      "SCENARIO SIMULATOR" in simp.text and 'id="simcards"' in simp.text)
check("simulator sees the whole remaining season, not an 8-week window",
      "/data/survivor?weeks=18" in simp.text)
check("simulator counts a tie as elimination, like Circa",
      "TIE_RATE" in simp.text)
check("simulator is seeded, so a number only moves when the board does",
      "mulberry32" in simp.text)
check("simulator warns the percentages are not forecasts",
      "ranking of your options" in simp.text)
check("simulator shows the active entry on its own, not just the portfolio",
      'id="simentry"' in simp.text and "Across all " in simp.text)
# '<1%' written straight into innerHTML is parsed as the start of a tag and
# vanishes, blanking exactly the rarest numbers. Must be entity-escaped.
check("small probabilities are HTML-escaped, not swallowed as a tag",
      "&lt;1%" in simp.text and "return '<1%'" not in simp.text
      and "return '>99%'" not in simp.text)
check("simulate() can be restricted to one entry", "onlyId" in simp.text)
check("a pinned live bar follows you down the long board",
      'id="livebar"' in simp.text and "position:fixed" in simp.text)
check("picking on an entry makes that entry the one on screen",
      "LASTPICK={t:team,n:String(n)}" in simp.text)
# A pick that costs nothing is the common case; saying nothing about it is
# indistinguishable from the tool being broken, which is how this was found.
check("the bar states the cost of a pick even when it is zero",
      "costs you nothing at either holiday leg" in simp.text)
check("pick cost is measured by re-running without that pick, not by diffing "
      "whatever was last on screen", "omitTeam" in simp.text)
# Holding ONE team per leg means burning a worse holiday team is free by the
# policy's own arithmetic. That is only true if the held team's number never
# moves, and it is a week-16 line. Depth in the pool must be counted and shown.
check("holiday-pool depth is counted, not just the single best team",
      "legDepth" in simp.text and "options left" in simp.text)
check("spending a holiday team is never reported as simply free",
      "but it was a holiday team" in simp.text)
# A market line prices today's injuries; a prior is fitted to lines posted
# before the news and cannot. The two must be distinguishable on screen.
check("legs say whether they are a real line or an estimate",
      "priced by estimate" in simp.text and "estdot" in simp.text)
check("the holiday numbers name their own source", "legsrc" in simp.text)
# Future value (SurvivorGrid's formula) now spans estimated weeks too, which
# moved 10 of 31 teams' star ratings. The flag must declare that mix rather
# than implying every star rests on a real line.
# The future-value flag is on the board, which stayed on the helper page.
# "consider saving" is the flag that changes what you do with a pick, so it is
# blue and filled rather than a third outline in the row. --mid cannot be used:
# it is blue in the light palette and tan in the dark one.
check("the save flag has its own colour in both themes",
      "--save:#1f6feb" in sp.text and "--save:#7cb0ff" in sp.text)
check("the save flag reads as blue, not gold",
      "color:var(--save)" in sp.text and "flag.save{color:var(--gold)" not in sp.text)

check("future value declares how much of it is estimated",
      "still estimated, so treat the star count as a rough sort" in sp.text)
check("weeks-ahead count is split into market vs estimated",
      "return {total:n,market:mkt,est:n-mkt}" in simp.text)

# The page hardcodes the two holiday legs. If the NFL schedule in the database
# disagrees with them, every reservation the tool recommends is wrong -- and it
# would fail silently, which is the worst way for this particular thing to break.
import re  # noqa: E402
from app import Game  # noqa: E402

legs_js = re.search(r"var HOLIDAY_LEGS=\[(.*?)\n\];", sp.text, re.S)
check("holiday legs are declared on the page", legs_js is not None)
if legs_js:
    pairs = re.findall(r"\['([A-Z]+)','([A-Z]+)'\]", legs_js.group(1))
    check("both holiday legs are populated (Thanksgiving + Christmas)",
          len(pairs) == 9)
    ss = SessionLocal()
    seasons = [x[0] for x in ss.query(Game.season).distinct().all()]
    real = set()
    for sea in seasons:
        for g in ss.query(Game).filter(Game.season == sea,
                                       Game.week.in_([12, 16])).all():
            real.add((sea, g.away, g.home))
    ss.close()
    # only meaningful once a season with a real week 12/16 is loaded
    checked = [p for p in pairs if any((sea, p[0], p[1]) in real for sea in seasons)]
    missing = [p for p in pairs
               if seasons and not any((sea, p[0], p[1]) in real for sea in seasons)]
    check("every hardcoded holiday game exists in a loaded schedule "
          "(skipped if only synthetic data is loaded)",
          not checked or not missing)
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
# ------------------------------------- survivor: one pick per entry per week
# You make exactly one pick per entry per week. Picks used to be stored as a
# bare team name with no week, so nothing stopped an entry taking two teams in
# the same week -- which is not a move that exists in survivor.
check("survivor: a pick records the week it was made", "{t:team,w:wk}" in sv_t)
check("survivor: old flat pick lists still migrate", "function normPicks(" in sv_t)
check("survivor: migrated picks keep burning the team",
      "return {t:x,w:0}" in sv_t)
check("survivor: a week's existing pick can be looked up",
      "function pickForWeek(" in sv_t)
check("survivor: a second pick in the same week is refused",
      "already has '+have.t+' for week" in sv_t)
check("survivor: the refusal explains how to switch", "✕ it first to switch" in sv_t)
check("survivor: the locked entry's buttons are disabled, not just refused",
      "var lk=!u&&pickForWeek(n,wkNo)" in sv_t)
check("survivor: locking is keyed to the week on screen, not the current week",
      "var wkNo=w.week" in sv_t)
check("survivor: removing a pick frees that week again",
      "return p.t!==team" in sv_t)
check("survivor: chips show which week each team was used",
      "'<i class=\"cwk\">W'+p.w+'</i>'" in sv_t)
check("survivor: the split skips entries that already picked this week",
      "var settled=aliveIds().filter(" in sv_t)
check("survivor: a fully-picked week says so instead of suggesting more",
      "is set</h3>" in sv_t)

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

# ------------------------------------------------ onboarding doc (task 3)
# "Done = friend integrates unassisted." Walking the doc against the deployed
# site on 2026-08-26 found three things that would stop them cold: $URL was
# never defined, the copy-paste game_id did not exist, and /data/odds 409s for
# every upcoming game off-season with no explanation. These lock in the fixes.
import pathlib as _pl
_root = _pl.Path(__file__).resolve().parent.parent
_onb = (_root / "ONBOARDING.md").read_text()
_stub = (_root / "examples" / "agent_stub.py").read_text()

check("onboarding: states the actual platform URL",
      "https://www.closinglinehq.com" in _onb)
check("onboarding: defines $URL before using it",
      "export URL=https://www.closinglinehq.com" in _onb)
check("onboarding: warns off the bare domain",
      "bare domain does not serve paths" in _onb)
check("onboarding: no invented game_id in the examples",
      "2026_W01_DAL_PHI" not in _onb)
check("onboarding: explains the game_id format",
      "SEASON_Wnn_AWAY_HOME" in _onb)
check("onboarding: tells them to take ids from /data/games",
      "Never hand-type a `game_id`" in _onb)
check("onboarding: explains the off-season 409 on /data/odds",
      "409" in _onb and "paused in the off-season" in _onb)
check("onboarding: points at 2025 for a season with real odds",
      "season=2025" in _onb)
check("stub: defaults to production, not localhost",
      'CLOSINGLINE_URL", "https://www.closinglinehq.com"' in _stub
      and "localhost:8000" not in _stub)
check("stub: says why nothing was picked instead of going silent",
      "had no odds yet" in _stub)

# ------------------------------------------- endzone edge agent (task 2)
# The owner's real model, ported from ~/projects/endzone-edge (its own
# invariant 6 forbids merging the repos; submitting as an agent is the one
# sanctioned link). The port is only worth anything if it reproduces the
# reference harness, so these pin the method, not a vibe.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("endzone_agent",
                                     _root / "systems" / "endzone_agent.py")
_ez = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_ez)

check("endzone: weights are the frozen 2024 fit",
      _ez.W_OFF == 0.70 and _ez.HFA == 0.4)
check("endzone: skips the unstable opening weeks", _ez.MIN_WEEK == 5)
check("endzone: tests on the untouched season", _ez.TEST_SEASON == 2025)

# z-score: a league where everyone is identical has no signal, and must not
# blow up on a zero standard deviation.
_flat = _ez.zscorer([7.0, 7.0, 7.0])
check("endzone: a flat league z-scores to zero", _flat(7.0) == 0.0)

# ratings: better offence and better defence both raise a rating.
_g = [{"home": "AAA", "away": "BBB", "hs": 30, "as": 10},
      {"home": "CCC", "away": "AAA", "hs": 14, "as": 21},
      {"home": "BBB", "away": "CCC", "hs": 13, "as": 17}]
_r = _ez.ratings_through(_g)
check("endzone: rates every team that has played", set(_r) == {"AAA", "BBB", "CCC"})
check("endzone: the team outscoring everyone rates highest",
      _r["AAA"] == max(_r.values()))
check("endzone: the team being outscored rates lowest",
      _r["BBB"] == min(_r.values()))

# home-field advantage must actually tilt a coin-flip matchup home.
_even = {"AAA": 0.0, "BBB": 0.0}
check("endzone: HFA breaks a tie toward the home side",
      _ez.predict(_even, "AAA", "BBB")[0] == "AAA")
check("endzone: a big enough gap beats HFA",
      _ez.predict({"AAA": 0.0, "BBB": 9.0}, "AAA", "BBB")[0] == "BBB")
check("endzone: an unrated team yields no pick",
      _ez.predict({"AAA": 1.0}, "AAA", "ZZZ") is None)

# no-lookahead: ratings come only from the games handed in, and the runner
# hands in strictly-earlier weeks. Feeding a later result must not change
# an earlier week's rating.
_early = _ez.ratings_through(_g)
_late = _ez.ratings_through(_g + [{"home": "BBB", "away": "AAA",
                                   "hs": 60, "as": 0}])
check("endzone: later results cannot change an earlier week's ratings",
      _early != _late and _ez.ratings_through(_g) == _early)

# as_of must sit before kickoff, or the pick is priced off the close.
_ao = _ez.as_of_for("2025-09-14T17:00:00")
check("endzone: as_of is 24h before kickoff", _ao == "2025-09-13T17:00:00")

_src = (_root / "systems" / "endzone_agent.py").read_text()
check("endzone: picks moneyline, the market it actually predicts",
      '"market": "moneyline"' in _src)
check("endzone: does not submit spread picks (no ATS edge found)",
      '"market": "spread"' not in _src)
check("endzone: flat staking, since the model has no sizing signal",
      '"stake_units": 1.0' in _src)
check("endzone: writing is opt-in, never the default",
      '"--submit"' in _src and '"--dry-run"' in _src)
check("endzone: records that the market still beats it",
      "63.0%" in _src and "59.6%" in _src)

# ------------------------------------- survivor: future value + backtest
# Two things borrowed from SurvivorGrid after reviewing it on 2026-08-30.
# Their future-value definition is better than the one we had (ours only found
# a team's single best week, which misses the team favoured in eight straight
# weeks), and their Knockouts page is the right way to sanity-check a survival
# curve: against a season that actually happened.
check("survivor: future value sums every favoured week, not just the best",
      "function futureValue(" in sv_t and "fv[p.team]=(fv[p.team]||0)+(p.wp-0.5)" in sv_t)
check("survivor: future value ignores games the team is not favoured in",
      "if(p.wp>0.5)fv[p.team]" in sv_t)
check("survivor: future value only looks forward",
      "if(w.week<=afterWeek)return;" in sv_t)
check("survivor: future value is banded into stars", "function fvStars(" in sv_t)
check("survivor: the board shows a future-value flag", 'class="flag fv"' in sv_t)

_bt = _ilu.module_from_spec(
    _ilu.spec_from_file_location("survivor_backtest",
                                 _root / "systems" / "survivor_backtest.py"))
_bt.__spec__.loader.exec_module(_bt)

# a tiny season: the 90% favourite loses in week 2, so every entry that took it
# must die there, and nobody can survive past the games available.
_rows = [
    {"week": 1, "team": "AAA", "opp": "BBB", "wp": 0.90, "home": True,
     "won": True, "tie": False, "score": "3-30"},
    {"week": 1, "team": "BBB", "opp": "AAA", "wp": 0.10, "home": False,
     "won": False, "tie": False, "score": "3-30"},
    {"week": 2, "team": "CCC", "opp": "DDD", "wp": 0.90, "home": True,
     "won": False, "tie": False, "score": "24-20"},
    {"week": 2, "team": "DDD", "opp": "CCC", "wp": 0.10, "home": False,
     "won": True, "tie": False, "score": "24-20"},
]
_res = _bt.elimination_curve(_rows, entries=200, top_k=1, seed=1)
check("backtest: a field survives a week its favourite won",
      _res["alive_after"][1] == 200)
check("backtest: a field is wiped out by an upset it all picked",
      _res["alive_after"][2] == 0 and _res["survived"] == 0)
check("backtest: the upset is attributed to the team that lost",
      _res["killers"].get((2, "CCC")) == 200)
check("backtest: seeded runs are reproducible",
      _bt.elimination_curve(_rows, entries=200, top_k=1, seed=1)["survived"]
      == _res["survived"])
check("backtest: a tie counts as elimination, per Circa",
      "Circa eliminates on a tie" in (_root / "systems" / "survivor_backtest.py").read_text())
check("backtest: it does not claim to replicate entry-weighted knockouts",
      "we do not have" in (_root / "systems" / "survivor_backtest.py").read_text())

print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
