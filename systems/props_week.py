"""This week's first-look projections: QBs vs the 8 worst pass Ds, lead RBs
vs the 6 worst run Ds.

A first look, not the final word: run it early in the week, re-run it as
injury news lands (games not yet started are rebuilt, games already started
are left alone), and the 90-minute final check (scripts/final_check.py)
confirms each player before kickoff.

  defenses  ours = per play (yds/att, yds/carry); eric = per game; every
            snap through last week, the same rankings as the backtests
  starter   ESPN depth chart, skipping anyone Out / on IR (injury report);
            Questionable / Doubtful players are flagged, not dropped
  QB yards  halfway between his typical and what the D typically allows
            (both trimmed); lean OVER when that beats the book's line
  QB atts   league trimmed average of starters' attempts vs these Ds; lean
            UNDER when the line is 3+ above it (23-10; favorites 16-5,
            underdogs 7-5 -- trailing teams keep throwing)
  RB yards  trimmed carries x blended yards per carry; lean OVER only when
            it beats the line by 10+ AND his team is favored (21-10 tested;
            teams that fall behind stop running)

Chris bets yardage overs only, so no yardage unders are suggested.

  python3 systems/props_week.py PBP_CSV_GZ [--write]
"""
import csv
import json
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "systems"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from loaders.real_data import TEAM_ABBR  # noqa: E402
import props_range as pr  # noqa: E402
import props_backtest as pb  # noqa: E402
import props_rb as prb  # noqa: E402
import grade_props as gp  # noqa: E402
import final_check as fc  # noqa: E402
from props_eval import implied, med_price  # noqa: E402

BOARD = os.path.join(ROOT, "data", "props_board.json")
ODDS = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
KEY = os.environ.get("ODDS_API_KEY")
# Chris, 2026-11-19: the 8 worst pass defenses, but only the 6 worst run defenses
N_PASS, N_RUN = 8, 6
FIELDS = pr.FIELDS + ["proj", "line", "fav_by", "lean", "status"]


def trim(v):
    v = sorted(v)
    v = v[1:-1] if len(v) >= 4 else v
    return sum(v) / len(v)


def worst_lists(pbp, week):
    """Rank every defense on every snap before `week`."""
    qb = {k: v for k, v in pb.load(pbp).items() if k[0] < week}
    d = defaultdict(lambda: [0, 0.0, set()])
    for (wk, gid, _, pos, de), (a, c, y) in qb.items():
        d[de][0] += a; d[de][1] += y; d[de][2].add(gid)
    rb = {k: v for k, v in prb.load(pbp).items() if k[0] < week}
    r = defaultdict(lambda: [0, 0.0, set()])
    for (wk, gid, _, pos, de), (c, y) in rb.items():
        r[de][0] += c; r[de][1] += y; r[de][2].add(gid)
    worst = lambda m, n: sorted(m, key=m.get)[-n:][::-1]       # worst first
    return {"pass": {"ours": worst({t: v[1] / v[0] for t, v in d.items()}, N_PASS),
                     "eric": worst({t: v[1] / len(v[2]) for t, v in d.items()}, N_PASS)},
            "run": {"ours": worst({t: v[1] / v[0] for t, v in r.items()}, N_RUN),
                    "eric": worst({t: v[1] / len(v[2]) for t, v in r.items()}, N_RUN)}}, qb, rb


def odds_events():
    r = requests.get(f"{ODDS}/odds", params={"apiKey": KEY, "regions": "us",
                                            "markets": "spreads", "oddsFormat": "american"},
                     timeout=30)
    r.raise_for_status()
    out = {}
    for e in r.json():
        pts = defaultdict(list)
        for b in e.get("bookmakers", []):
            for m in b["markets"]:
                for o in m["outcomes"]:
                    pts[TEAM_ABBR.get(o["name"])].append(-o["point"])   # + = favored by
        h, a = TEAM_ABBR.get(e["home_team"]), TEAM_ABBR.get(e["away_team"])
        out[frozenset((h, a))] = (e["id"], {t: st.median(v) for t, v in pts.items() if v})
    return out


def props(event_id):
    r = requests.get(f"{ODDS}/events/{event_id}/odds", params={
        "apiKey": KEY, "regions": "us", "oddsFormat": "american",
        "markets": "player_pass_yds,player_pass_attempts,player_rush_yds"}, timeout=30)
    return r.json() if r.status_code == 200 else {}


def line(ev, market, player):
    """Consensus main line: each book's most even pair, then the median point."""
    mains = []
    for b in ev.get("bookmakers", []):
        for m in b.get("markets", []):
            if m["key"] != market:
                continue
            by = defaultdict(dict)
            for o in m["outcomes"]:
                if gp.same(o.get("description", ""), player):
                    by[o.get("point")][o["name"]] = o["price"]
            pairs = [(pt, s["Over"], s["Under"]) for pt, s in by.items()
                     if "Over" in s and "Under" in s]
            if pairs:
                mains.append(min(pairs, key=lambda x: abs(implied(x[1]) - implied(x[2]))))
    if not mains:
        return None
    pt = st.median([x[0] for x in mains])
    near = min({x[0] for x in mains}, key=lambda v: abs(v - pt))
    at = [x for x in mains if x[0] == near]
    return near, med_price([x[1] for x in at]), med_price([x[2] for x in at])


def report(event_id):
    """{team: {display name: status}} from ESPN's injury report."""
    r = requests.get(f"{gp.ESPN}/summary", params={"event": event_id}, timeout=30)
    out = {}
    for t in r.json().get("injuries", []):
        team = gp.ESPN_TEAM.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
        out[team] = {i["athlete"]["displayName"]: i.get("status", "") for i in t.get("injuries", [])}
    return out


def build(pbp, season, week):
    lists, qb_games, rb_games = worst_lists(pbp, week)
    qbs = pr.starters({k: [v[0], v[2]] for k, v in qb_games.items()}, "QB")
    rbs = pr.starters({k: list(v) for k, v in rb_games.items()}, "RB")
    # QB attempts: starters vs each list (the backtest's trimmed average)
    att_proj = {}
    for n in ("ours", "eric"):
        att = sorted(v[0] for k, v in qb_games.items() if v[0] >= pb.MIN_ATT and k[4] in lists["pass"][n])
        att_proj[n] = sum(att[1:-1]) / len(att[1:-1])
    # RB yards: the tested projection, built per list from carries vs that list
    car_proj = {}
    for n in ("ours", "eric"):
        car = sorted(v[0] for k, v in rb_games.items() if v[0] >= prb.MIN_CAR and k[4] in lists["run"][n])
        car_proj[n] = sum(car[1:-1]) / len(car[1:-1])
    d_ypc = defaultdict(lambda: [0, 0.0])
    for k, (c, y) in rb_games.items():
        d_ypc[k[4]][0] += c; d_ypc[k[4]][1] += y

    odds = odds_events()
    rows = []
    for ev, kick, state, teams in fc.games(season, week):
        if state != "pre":
            continue
        inj = report(ev)
        oid, spread = odds.get(frozenset(teams), (None, {}))
        lines = props(oid) if oid else {}
        for team, tid in teams.items():
            opp = next(t for t in teams if t != team)
            dc = fc.depth(season, tid)
            for pos, key, starts in (("QB", "pass", qbs), ("RB", "run", rbs)):
                on = [n for n in ("ours", "eric") if opp in lists[key][n]]
                if not on:
                    continue
                hurt = inj.get(team, {})
                pick = next(((d, s) for d, s in dc.get(pos, [])
                             if hurt.get(d) not in ("Out", "Injured Reserve")), None)
                if not pick:
                    continue
                disp = pick[0]
                # ESPN "C.J. Stroud" -> play-by-play "C.Stroud": prefer a name
                # that started for this team, else any team (a trade)
                names = sorted({(k[2] != team, v[0]) for k, v in starts.items()
                                if gp.same(disp, v[0])})
                short = names[0][1] if names else pick[1].replace(" ", "")
                own = [v[1] for v in starts.values() if v[0] == short]
                allowed = [v[1] for v in starts.values() if v[3] == opp]
                status = hurt.get(disp, "")
                if pos == "QB":
                    proj = (trim(own) + trim(allowed)) / 2 if own else None
                    ln = line(lines, "player_pass_yds", disp)
                    al = line(lines, "player_pass_attempts", disp)
                    ap = min(att_proj[n] for n in on)
                    lean = []
                    if proj and ln and proj >= ln[0]:
                        lean.append(f"OVER {ln[0]:g} yds")
                    if al and al[0] - ap >= 3:
                        # tested: favorites 16-5, underdogs 7-5 (trailing teams throw)
                        fav = spread.get(team)
                        lean.append(f"UNDER {al[0]:g} att (proj {ap:.1f})" +
                                    ("" if fav and fav > 0 else " - underdog, weaker"))
                else:
                    mine = [v for k, v in rb_games.items() if k[2] == short and v[0] >= prb.MIN_CAR]
                    proj = None
                    if len(mine) >= 2:
                        own_ypc = sum(v[1] for v in mine) / sum(v[0] for v in mine)
                        dy = d_ypc[opp][1] / d_ypc[opp][0]
                        proj = max(car_proj[n] for n in on) * (own_ypc + dy) / 2
                    ln = line(lines, "player_rush_yds", disp)
                    fav = spread.get(team)
                    lean = []
                    if proj and ln and proj - ln[0] >= 10:
                        lean.append(f"OVER {ln[0]:g} yds" if fav and fav > 0
                                    else "no bet - underdog")
                    if len(mine) < 2:
                        lean.append("fewer than 2 starts")
                    if ln and ln[0] < 40:
                        lean.append("book line says backup")
                rows.append({
                    "season": season, "week": week, "list": "both" if len(on) == 2 else on[0],
                    "pos": pos, "player": short, "team": team, "opp": opp,
                    "games": len(own),
                    "floor": f"{min(own):g}" if own else "",
                    "typical": f"{trim(own):.0f}" if own else "",
                    "ceiling": f"{max(own):g}" if own else "",
                    "def_floor": f"{min(allowed):g}" if allowed else "",
                    "def_ceiling": f"{max(allowed):g}" if allowed else "",
                    "actual": "", "zone": "",
                    "proj": f"{proj:.0f}" if proj else "",
                    "line": f"{ln[0]:g}" if ln else "",
                    "fav_by": f"{spread[team]:+g}" if team in spread else "",
                    "lean": "; ".join(lean), "status": status})
    return lists, rows


if __name__ == "__main__":
    board = json.load(open(BOARD))
    season, week = board["season"], int(sys.argv[sys.argv.index("--week") + 1]) \
        if "--week" in sys.argv else board["week"]
    lists, rows = build(sys.argv[1], season, week)
    for k in ("pass", "run"):
        print(k, "ours", lists[k]["ours"], "| eric", lists[k]["eric"])
    for r in rows:
        print(f"{r['list']:<4} {r['pos']} {r['player']:<13} {r['team']:>3}-{r['opp']:<3} "
              f"n={r['games']:<2} {r['floor']:>4}/{r['typical']:>4}/{r['ceiling']:>4}  "
              f"proj {r['proj']:>4} line {r['line']:>6} fav {r['fav_by']:>5}  "
              f"{r['status']:<12} {r['lean']}")
    if "--write" in sys.argv:
        for k in ("pass", "run"):
            for n in ("ours", "eric"):
                board["defenses"][k][n] = lists[k][n]
        board["defenses"]["pass"]["eric_basis"] = "passing yards allowed per game (Eric's method)"
        board["defenses"]["run"]["eric_basis"] = "rushing yards allowed per game (Eric's method)"
        board["week"], board["through_week"] = week, week - 1
        json.dump(board, open(BOARD, "w"), indent=2)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        old = list(csv.DictReader(open(pr.OUT)))
        started = {t for _, _, s, ts in fc.games(season, week) if s != "pre" for t in ts}
        keep = [r for r in old if not (r["season"] == str(season) and r["week"] == str(week)
                                       and r["team"] not in started)]
        with open(pr.OUT, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, restval="")
            w.writeheader()
            w.writerows(keep)
            w.writerows({"logged_at_utc": now, **r} for r in rows
                        if r["team"] not in started)
        print(f"wrote {len(rows)} first-look rows for week {week}")
