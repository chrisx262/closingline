"""Final check, 90 minutes before each kickoff, when the inactives come out.

Teams must name their inactives 90 minutes before kickoff and ESPN posts them
within minutes. For every game entering that window this script:

  1. reads the inactives (ESPN summary -> injuries, fantasy status INACTIVE)
     and the depth chart (first QB / RB not inactive = the starter);
  2. checks every logged pick and floor/ceiling row on those teams:
       confirmed  -- he is active and still the starter
       OUT        -- inactive or ruled out (picks: don't bet; graded void)
       backup?    -- active but not first on the depth chart. Depth charts lag
                     (wk 10: Darnold, already ruled out, was still listed over
                     Lock, who started), so this is a warning only
  3. for an OUT floor/ceiling row, voids it and logs the range of the next
     player on the depth chart who is not out.

Logged picks are never edited -- the verdict goes to data/final_checks.csv
beside them. Runs every 10 minutes from launchd; each game is checked once.

  python3 scripts/final_check.py [--no-publish] [--now ISO]
"""
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "systems"))
import grade_props as gp  # noqa: E402
import props_range as pr  # noqa: E402

CHECKS = os.path.join(ROOT, "data", "final_checks.csv")
FIELDS = ["checked_at_utc", "season", "week", "kind", "team", "player",
          "status", "starter", "note"]
CACHE = os.path.join(ROOT, ".cache")
PBP_URL = ("https://github.com/nflverse/nflverse-data/releases/download/pbp/"
           "play_by_play_{season}.csv.gz")
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
WINDOW = timedelta(minutes=90)
# inactives normally land 0-10 minutes into the window; past this, check anyway
LATE = timedelta(minutes=60)


def log(msg):
    gp.log(msg)


def games(season, week):
    r = requests.get(f"{gp.ESPN}/scoreboard", params={
        "dates": season, "seasontype": 2, "week": week}, timeout=30)
    r.raise_for_status()
    out = []
    for ev in r.json().get("events", []):
        c = ev["competitions"][0]
        teams = {gp.ESPN_TEAM.get(x["team"]["abbreviation"], x["team"]["abbreviation"]):
                 x["team"]["id"] for x in c["competitors"]}
        kick = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        out.append((ev["id"], kick, c["status"]["type"]["state"], teams))
    return out


def inactives(event_id):
    """{team: (unavailable display names, inactives posted?)}.

    Unavailable = the 90-minute inactives plus anyone already ruled Out or on
    injured reserve (those never appear on the inactive list, and depth charts
    can still show them first). Posted = the team's INACTIVE list is up."""
    r = requests.get(f"{gp.ESPN}/summary", params={"event": event_id}, timeout=30)
    r.raise_for_status()
    out = {}
    for t in r.json().get("injuries", []):
        team = gp.ESPN_TEAM.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
        flag = lambda i: i.get("details", {}).get("fantasyStatus", {}).get("abbreviation")
        out[team] = ({i["athlete"]["displayName"] for i in t.get("injuries", [])
                      if flag(i) in ("INACTIVE", "OUT", "IR")
                      or i.get("status") in ("Out", "Injured Reserve")},
                     any(flag(i) == "INACTIVE" for i in t.get("injuries", [])))
    return out


def depth(season, team_id):
    """{"QB": [(display, short)...], "RB": [...]} in depth-chart order."""
    d = requests.get(f"{CORE}/seasons/{season}/teams/{team_id}/depthcharts",
                     timeout=30).json()
    out = {}
    for it in d.get("items", []):
        for key, pos in (("qb", "QB"), ("rb", "RB")):
            if pos in out or key not in it.get("positions", {}):
                continue
            names = []
            for a in it["positions"][key]["athletes"][:4]:
                p = requests.get(a["athlete"]["$ref"].replace("http:", "https:"),
                                 timeout=30).json()
                names.append((p.get("displayName", ""), p.get("shortName", "")))
            out[pos] = names
    return out


def pbp_path(season):
    """This season's play-by-play, re-downloaded when older than 6 hours."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"pbp_{season}.csv.gz")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 6 * 3600:
        r = requests.get(PBP_URL.format(season=season), timeout=300)
        r.raise_for_status()
        open(path, "wb").write(r.content)
    return path


def read(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def write(path, rows, fields):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(now):
    board = __import__("json").load(open(os.path.join(ROOT, "data", "props_board.json")))
    season, week = board["season"], board["week"]
    done = {(c["season"], c["week"], c["team"]) for c in read(CHECKS)}
    picks = [p for p in read(gp.CSV) if p["week"] == str(week) and p["season"] == str(season)]
    ranges_all = read(pr.OUT)
    rfields = list(ranges_all[0]) if ranges_all else pr.FIELDS
    rng = [r for r in ranges_all if r["week"] == str(week) and r["season"] == str(season)
           and r["zone"] != "void"]
    new_checks, new_ranges, changed = [], [], False
    for ev, kick, state, teams in games(season, week):
        mine = [t for t in teams if (str(season), str(week), t) not in done
                and any(x["team"] == t for x in picks + rng)]
        if not mine or state != "pre" or now < kick - WINDOW:
            continue
        out = inactives(ev)
        if not all(out.get(t, (0, False))[1] for t in teams) and now < kick - LATE:
            log(f"{'/'.join(teams)}: inactives not posted yet"); continue
        for t in mine:
            out_t = out.get(t, (set(), False))[0]
            dc = depth(season, teams[t])
            start = {pos: next(((d, s) for d, s in dc.get(pos, [])
                                if d not in out_t), ("", "")) for pos in ("QB", "RB")}
            stamp = now.strftime("%Y-%m-%dT%H:%MZ")

            def verdict(player, pos):
                if any(gp.same(n, player) for n in out_t):
                    return "OUT", ""
                d, s = start.get(pos, ("", ""))
                if pos and d and not gp.same(d, player):
                    return "backup?", d
                return "confirmed", ""

            for p in [x for x in picks if x["team"] == t]:
                pos = {"pass_attempts": "QB", "rush_yds": "RB"}.get(p["stat"])
                st, by = verdict(p["player"], pos)
                note = {"OUT": "inactive - don't bet (graded void)",
                        "backup?": f"depth chart lists {by} first - check before betting"
                        }.get(st, "active, starting")
                new_checks.append({"checked_at_utc": stamp, "season": season, "week": week,
                                   "kind": "pick", "team": t, "player": p["player"],
                                   "status": st, "starter": by, "note": note})
                log(f"pick {p['player']} ({t}): {st} {by}")
            for r in [x for x in rng if x["team"] == t]:
                st, by = verdict(r["player"], r["pos"])
                note = ("active, starting" if st == "confirmed" else
                        f"depth chart lists {by} first - range kept")
                if st == "OUT":
                    r["zone"] = "void"
                    by = by or start[r["pos"]][0]
                    short = start[r["pos"]][1].replace(" ", "")
                    lists = {n: {"QB": board["defenses"]["pass"][n],
                                 "RB": board["defenses"]["run"][n]} for n in ("ours", "eric")}
                    fresh = [x for x in pr.ranges(pbp_path(season), week, lists,
                                                  [(t, r["opp"])], {f"{t}:{r['pos']}": short})
                             if x["pos"] == r["pos"]]
                    for x in fresh:
                        new_ranges.append({"logged_at_utc": stamp, "season": season,
                                           "week": week, **x})
                    note = (f"replaced by {short} ({fresh[0]['games']} starts)" if fresh
                            else f"{by or 'new starter'} has no starts this season - no range")
                new_checks.append({"checked_at_utc": stamp, "season": season, "week": week,
                                   "kind": "range", "team": t, "player": r["player"],
                                   "status": st, "starter": by, "note": note})
                log(f"range {r['player']} ({t}): {st} {note}")
            changed = True
    if not changed:
        return False
    write(CHECKS, read(CHECKS) + new_checks, FIELDS)
    write(pr.OUT, ranges_all + new_ranges, rfields)
    return True


def publish():
    def run(*cmd):
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        log(f"$ {' '.join(cmd[:3])} -> {p.returncode} {p.stderr.strip()[-200:]}")
        return p.returncode == 0
    run("git", "add", "data/final_checks.csv", "data/tracked_ranges.csv")
    if not run("git", "commit", "-m", "Final check: inactives and starters\n\n"
               "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"):
        return
    run("git", "push")
    run("railway", "up", "--detach")


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    if "--now" in sys.argv:
        now = datetime.fromisoformat(sys.argv[sys.argv.index("--now") + 1])
    if main(now) and "--no-publish" not in sys.argv:
        publish()
