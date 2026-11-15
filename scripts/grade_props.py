"""Grade the tracked prop picks once their games are final, then publish.

Reads data/tracked_props.csv, fills result/actual for any pick whose game
ESPN reports as FINAL (overtime included -- a game is only graded after its
final whistle), commits, pushes, and redeploys if anything changed. Safe to run
as often as you like: graded picks are never touched again, and a game still
in progress is simply left for the next run.

  win / loss / push  -- against the logged line and side
  void               -- game final but the player recorded nothing (inactive),
                        which is how sportsbooks settle a DNP

Usage: python3 scripts/grade_props.py [--no-publish]
"""
import csv
import os
import subprocess
import sys
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "data", "tracked_props.csv")
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
# ESPN abbreviations that differ from ours
ESPN_TEAM = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}
# which box-score table and column holds each stat
STAT = {"pass_attempts": ("passing", "C/ATT", lambda v: float(v.split("/")[1])),
        "rush_yds": ("rushing", "YDS", float),
        "rec_yds": ("receiving", "YDS", float),
        "pass_yds": ("passing", "YDS", float)}
RANGES = os.path.join(ROOT, "data", "tracked_ranges.csv")
RANGE_STAT = {"QB": "pass_yds", "RB": "rush_yds"}


def log(msg):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z  {msg}", flush=True)


def week_games(season, week):
    r = requests.get(f"{ESPN}/scoreboard", params={
        "dates": season, "seasontype": 2, "week": week}, timeout=30)
    r.raise_for_status()
    out = {}
    for ev in r.json().get("events", []):
        comp = ev["competitions"][0]
        teams = [ESPN_TEAM.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
                 for c in comp["competitors"]]
        final = comp["status"]["type"].get("completed", False)
        for t in teams:
            out[t] = (ev["id"], final)
    return out


def box(event_id):
    """{(team, stat_key): {player full name: value}}"""
    r = requests.get(f"{ESPN}/summary", params={"event": event_id}, timeout=30)
    r.raise_for_status()
    out = {}
    for side in r.json().get("boxscore", {}).get("players", []):
        team = side["team"]["abbreviation"]
        team = ESPN_TEAM.get(team, team)
        for grp in side.get("statistics", []):
            for key, (name, col, conv) in STAT.items():
                if grp.get("name") != name:
                    continue
                labels = grp.get("labels", [])
                if col not in labels:
                    continue
                i = labels.index(col)
                for a in grp.get("athletes", []):
                    try:
                        out.setdefault((team, key), {})[a["athlete"]["displayName"]] = \
                            conv(a["stats"][i])
                    except (ValueError, IndexError, KeyError):
                        pass
    return out


def same(a, b):
    norm = lambda s: s.lower().replace(".", "").replace(" jr", "").replace(" iii", "") \
        .replace(" ii", "").strip()
    if "." in b and " " not in b.split(".", 1)[0]:      # pbp short name, "J.Goff"
        init, last = b.split(".", 1)
        return norm(a).endswith(" " + norm(last)) and a[:1].upper() == init[:1].upper()
    return norm(a) == norm(b)


def grade_ranges():
    """Fill actual + zone (below / inside / above his floor-ceiling) for the
    logged floor/ceiling rows whose games are final."""
    if not os.path.exists(RANGES):
        return 0
    rows = list(csv.DictReader(open(RANGES)))
    fields = list(rows[0].keys()) if rows else []
    todo = [r for r in rows if not r["zone"]]
    changed = 0
    for (season, week) in sorted({(r["season"], r["week"]) for r in todo}):
        games = week_games(season, week)
        boxes = {}
        for r in [x for x in todo if (x["season"], x["week"]) == (season, week)]:
            g = games.get(r["team"])
            if not g or not g[1]:
                continue
            if g[0] not in boxes:
                boxes[g[0]] = box(g[0])
            vals = boxes[g[0]].get((r["team"], RANGE_STAT[r["pos"]]), {})
            actual = next((v for n, v in vals.items() if same(n, r["player"])), None)
            if actual is None:
                r["actual"], r["zone"] = "", "void"
            else:
                r["actual"] = f"{actual:g}"
                r["zone"] = ("below" if actual < float(r["floor"]) else
                             "above" if actual > float(r["ceiling"]) else "inside")
            changed += 1
            log(f"range {r['player']}: {r['actual'] or '-'} -> {r['zone']}")
    if changed:
        with open(RANGES, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def main():
    changed = grade_ranges()
    rows = list(csv.DictReader(open(CSV)))
    fields = list(rows[0].keys())
    todo = [r for r in rows if not r["result"]]
    if not todo:
        log("no picks to grade"); return changed > 0
    for (season, week) in sorted({(r["season"], r["week"]) for r in todo}):
        games = week_games(season, week)
        boxes = {}
        for r in [x for x in todo if (x["season"], x["week"]) == (season, week)]:
            g = games.get(r["team"])
            if not g:
                log(f"{r['player']}: no game found for {r['team']} week {week}"); continue
            ev, final = g
            if not final:
                log(f"{r['player']}: game not final yet"); continue
            if ev not in boxes:
                boxes[ev] = box(ev)
            vals = boxes[ev].get((r["team"], r["stat"]), {})
            actual = next((v for n, v in vals.items() if same(n, r["player"])), None)
            if actual is None:
                r["result"], r["actual"] = "void", ""
            else:
                line = float(r["line"])
                if actual == line:
                    res = "push"
                else:
                    res = "win" if (actual > line) == (r["side"] == "Over") else "loss"
                r["result"], r["actual"] = res, f"{actual:g}"
            changed += 1
            log(f"graded {r['player']} {r['side']} {r['line']} {r['stat']}: "
                f"{r['actual'] or '-'} -> {r['result']}")
    if changed:
        with open(CSV, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed > 0


def publish():
    def run(*cmd):
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        log(f"$ {' '.join(cmd[:3])} -> {p.returncode} {p.stderr.strip()[-200:]}")
        return p.returncode == 0
    run("git", "add", "data/tracked_props.csv", "data/tracked_ranges.csv")
    if not run("git", "commit", "-m", "Grade tracked props\n\n"
               "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"):
        return
    run("git", "push")
    run("railway", "up", "--detach")


if __name__ == "__main__":
    if main() and "--no-publish" not in sys.argv:
        publish()
