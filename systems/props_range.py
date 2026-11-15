"""Floor and ceiling for each QB and lead RB facing a bottom-8 defense.

Logged before kickoff to data/tracked_ranges.csv, graded afterwards by
scripts/grade_props.py. Not a bet: it records where each player's yards
usually land so we can see how often the game lands below, inside or above.

  player floor / ceiling  -- his lowest and highest yards this season in games
                             where he was the starter (QB 15+ attempts, RB 10+
                             carries); `games` says how many that is
  defense floor / ceiling -- the fewest and most yards this defense has allowed
                             to the opposing starter (QB / lead back) this season
  typical                 -- trimmed average of the player's games (drop the
                             highest and lowest when he has 4+)

The starter is chosen before the game: the team's leading passer / rusher
(10+ carries) in its most recent game. Same rule as the backtests.

  python3 systems/props_range.py PBP_CSV_GZ SEASON WEEK [--write]
"""
import csv
import gzip
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "tracked_ranges.csv")
FIELDS = ["logged_at_utc", "season", "week", "list", "pos", "player", "team", "opp",
          "games", "floor", "typical", "ceiling", "def_floor", "def_ceiling",
          "actual", "zone"]
MIN = {"QB": 15, "RB": 10}


def load(path, week):
    """{pos: {(wk, gid, name, team, opp): [volume, yards]}} for weeks < week,
    plus every (team, opp) pairing scheduled in `week`."""
    out = {"QB": defaultdict(lambda: [0, 0.0]), "RB": defaultdict(lambda: [0, 0.0])}
    with gzip.open(path, "rt") as fh:
        for r in csv.DictReader(fh):
            if r["season_type"] != "REG" or int(r["week"]) >= week:
                continue
            if r.get("two_point_attempt") == "1":
                continue
            base = (int(r["week"]), r["game_id"])
            if r["pass_attempt"] == "1" and r["sack"] != "1" and r["passer_player_name"]:
                k = base + (r["passer_player_name"], r["posteam"], r["defteam"])
                out["QB"][k][0] += 1
                out["QB"][k][1] += float(r["passing_yards"] or 0)
            elif (r["rush_attempt"] == "1" and r.get("qb_kneel") != "1"
                  and r.get("qb_scramble") != "1" and r["rusher_player_name"]):
                k = base + (r["rusher_player_name"], r["posteam"], r["defteam"])
                out["RB"][k][0] += 1
                out["RB"][k][1] += float(r["rushing_yards"] or 0)
    return out


def starters(games, pos):
    """{(wk, gid, team): (name, yards)} -- the team's starter in each game."""
    best = {}
    for (wk, gid, name, team, opp), (v, y) in games.items():
        k = (wk, gid, team)
        if v >= MIN[pos] and (k not in best or v > best[k][2]):
            best[k] = (name, y, v, opp)
    return best


def trimmed(vals):
    v = sorted(vals)
    if len(v) >= 4:
        v = v[1:-1]
    return sum(v) / len(v)


def ranges(pbp, week, lists, matchups):
    """lists = {"ours"|"eric": {"QB": [...pass D], "RB": [...run D]}};
    matchups = [(team, opp)]. A player facing a defense on both lists gets
    list "both"."""
    data = load(pbp, week)
    rows = []
    for pos in ("QB", "RB"):
        st = starters(data[pos], pos)
        for team, opp in matchups:
            on = [n for n in ("ours", "eric") if opp in lists[n][pos]]
            if not on:
                continue
            mine = [k for k in st if k[2] == team]
            if not mine:
                continue
            name = st[max(mine)][0]                      # starter, most recent game
            own = [v[1] for k, v in st.items() if k[2] == team and v[0] == name]
            allowed = [v[1] for k, v in st.items() if v[3] == opp]
            rows.append({"list": "both" if len(on) == 2 else on[0], "pos": pos, "player": name, "team": team, "opp": opp,
                         "games": len(own), "floor": f"{min(own):g}",
                         "typical": f"{trimmed(own):.0f}", "ceiling": f"{max(own):g}",
                         "def_floor": f"{min(allowed):g}" if allowed else "",
                         "def_ceiling": f"{max(allowed):g}" if allowed else "",
                         "actual": "", "zone": ""})
    return rows


def matchups_for(season, week):
    import requests
    r = requests.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
                     params={"dates": season, "seasontype": 2, "week": week}, timeout=30)
    r.raise_for_status()
    fix = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}
    out = []
    for ev in r.json().get("events", []):
        if ev["competitions"][0]["status"]["type"]["state"] != "pre":
            continue                    # already kicked off: logging it now is lookahead
        t = [fix.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
             for c in ev["competitions"][0]["competitors"]]
        out += [(t[0], t[1]), (t[1], t[0])]
    return out


if __name__ == "__main__":
    import json
    pbp, season, week = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    board = json.load(open(os.path.join(ROOT, "data", "props_board.json")))
    lists = {n: {"QB": board["defenses"]["pass"][n], "RB": board["defenses"]["run"][n]}
             for n in ("ours", "eric")}
    rows = ranges(pbp, week, lists, matchups_for(season, week))
    for r in rows:
        print(f"{r['list']:<4} {r['pos']} {r['player']:<14} {r['team']:>3} vs {r['opp']:<3} "
              f"n={r['games']}  floor {r['floor']:>4}  typical {r['typical']:>4}  "
              f"ceiling {r['ceiling']:>4}   D allowed {r['def_floor']}-{r['def_ceiling']}")
    if "--write" in sys.argv:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        new = not os.path.exists(OUT)
        with open(OUT, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if new:
                w.writeheader()
            for r in rows:
                w.writerow({"logged_at_utc": now, "season": season, "week": week, **r})
        print(f"logged {len(rows)} rows to {OUT}")
