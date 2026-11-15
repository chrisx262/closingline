"""Receivers against the 8 worst pass defenses: backtest, line purchase, scoring.

Each team's top 3 targets (by targets over its last 4 games, chosen BEFORE
the game) facing a bottom-8 pass defense. Projection uses Chris's targets
idea: target share x the trimmed-average team attempts vs weak defenses x
catch rate (player/defense blend) x yards per catch (player/defense blend).

  python3 systems/props_wr.py buy PBP GAMES SEASON [--buy]
  python3 systems/props_wr.py score PBP_2025 PBP_2026
"""
import csv
import gzip
import json
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "systems"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from loaders.real_data import TEAM_ABBR  # noqa: E402
import props_lines as pl  # noqa: E402
from props_eval import med_price, implied, payout  # noqa: E402

FIRST_WEEK = 5
MKT = {"yds": "player_reception_yds", "rec": "player_receptions"}


def load(path):
    """Per (week, game, team, opp): team attempts; per receiver: tgt, rec, yds."""
    team = defaultdict(lambda: [0, 0, 0.0])                 # att, cmp, yds
    rcv = defaultdict(lambda: [0, 0, 0.0])                  # tgt, rec, yds
    with gzip.open(path, "rt") as fh:
        for r in csv.DictReader(fh):
            if r["season_type"] != "REG" or r["pass_attempt"] != "1":
                continue
            if r["sack"] == "1" or r.get("two_point_attempt") == "1":
                continue
            g = (int(r["week"]), r["game_id"], r["posteam"], r["defteam"])
            c = r["complete_pass"] == "1"
            y = float(r["passing_yards"] or 0)
            team[g][0] += 1; team[g][1] += c; team[g][2] += y
            if r["receiver_player_name"]:
                k = g + (r["receiver_player_name"],)
                rcv[k][0] += 1; rcv[k][1] += c; rcv[k][2] += y
    return team, rcv


def run(path):
    team, rcv = load(path)
    rows = []
    for W in range(FIRST_WEEK, max(k[0] for k in team) + 1):
        tb = {k: v for k, v in team.items() if k[0] < W}
        d = defaultdict(lambda: [0, 0, 0.0, set()])
        for (wk, gid, pos, de), (a, c, y) in tb.items():
            d[de][0] += a; d[de][1] += c; d[de][2] += y; d[de][3].add(gid)
        ypa = {t: v[2] / v[0] for t, v in d.items()}
        ypg = {t: v[2] / len(v[3]) for t, v in d.items()}
        cmpa = {t: v[1] / v[0] for t, v in d.items()}
        ypc = {t: v[2] / v[1] for t, v in d.items()}
        rankings = {"ypa": sorted(ypa, key=ypa.get)[-8:],
                    "ypg": sorted(ypg, key=ypg.get)[-8:]}
        # team attempts per game vs weak D (trimmed), as in the QB work
        for rk, worst in rankings.items():
            att_vs = sorted(v[0] for k, v in tb.items() if k[3] in worst and v[0] >= 15)
            if len(att_vs) < 6:
                continue
            tr = att_vs[1:-1]
            team_att = sum(tr) / len(tr)
            for g, (a, c, y) in team.items():
                wk, gid, pos, de = g
                if wk != W or de not in worst:
                    continue
                # receivers chosen before the game: top 3 targets, last 4 team games
                recent = sorted({k[0] for k in tb if k[2] == pos})[-4:]
                tgts = defaultdict(int)
                tot = 0
                for k, v in rcv.items():
                    if k[2] == pos and k[0] in recent:
                        tgts[k[4]] += v[0]
                for k, v in tb.items():
                    if k[2] == pos and k[0] in recent:
                        tot += v[0]
                if not tot:
                    continue
                for name in sorted(tgts, key=tgts.get, reverse=True)[:3]:
                    season = [v for k, v in rcv.items()
                              if k[2] == pos and k[4] == name and k[0] < W]
                    st_tgt = sum(v[0] for v in season)
                    st_rec = sum(v[1] for v in season)
                    st_yds = sum(v[2] for v in season)
                    if st_rec < 5:
                        continue
                    share = tgts[name] / tot
                    catch = (st_rec / st_tgt + cmpa[de]) / 2
                    ypr = (st_yds / st_rec + ypc[de]) / 2
                    act = rcv.get(g + (name,), [0, 0, 0.0])
                    rows.append({"week": W, "game_id": gid, "player": name,
                                 "team": pos, "opp": de, "ranking": rk,
                                 "rec": act[1], "yds": act[2],
                                 "p_rec": share * team_att * catch,
                                 "p_yds": share * team_att * catch * ypr,
                                 "p_yds_avg": st_yds / len(season)})
    return rows


def buy(pbp, games_csv, season, really):
    rows = run(pbp)
    ko = pl.kickoffs(games_csv, season)
    wanted = sorted({r["game_id"] for r in rows})
    outdir = os.path.join(ROOT, "data", "props_lines_wr", str(season))
    os.makedirs(outdir, exist_ok=True)
    todo = [g for g in wanted if not os.path.exists(os.path.join(outdir, g + ".json"))]
    weeks = sorted({ko[g][3] for g in todo})
    print(f"{season}: {len(wanted)} games, {len(todo)} to buy -> at most "
          f"{len(weeks) + 20 * len(todo)} credits")
    if not really:
        return
    left = None
    for w in weeks:
        gs = [g for g in todo if ko[g][3] == w]
        first = min(ko[g][0] for g in gs)
        events = requests.get(f"{pl.BASE}/events", params={
            "apiKey": pl.KEY, "date": pl.iso(first - timedelta(hours=6))},
            timeout=30).json().get("data", [])
        for g in gs:
            kick, home, away, _ = ko[g]
            ev = next((e for e in events if TEAM_ABBR.get(e["home_team"]) == home
                       and TEAM_ABBR.get(e["away_team"]) == away), None)
            if not ev:
                print(f"  {g}: no event"); continue
            r = requests.get(f"{pl.BASE}/events/{ev['id']}/odds", params={
                "apiKey": pl.KEY, "regions": "us", "oddsFormat": "american",
                "markets": ",".join(MKT.values()),
                "date": pl.iso(kick - pl.BEFORE_KICK)}, timeout=30)
            if r.status_code != 200:
                print(f"  {g}: HTTP {r.status_code}"); continue
            left = r.headers.get("x-requests-remaining")
            json.dump(r.json(), open(os.path.join(outdir, g + ".json"), "w"))
        print(f"  W{w}: {len(gs)} games, credits left {left}")


def name_ok(desc, short):
    """'A.St. Brown' vs 'Amon-Ra St. Brown', 'K.Walker' vs 'Kenneth Walker III'."""
    init, last = short.split(".", 1) if "." in short else ("", short)
    d = desc.replace(".", "").lower()
    return (last.replace(".", "").lower() in d
            and (not init or desc[:1].upper() == init[:1].upper()))


def line_for(path, name, mk):
    if not os.path.exists(path):
        return None
    ev = json.load(open(path)).get("data") or {}
    mains = []
    for b in ev.get("bookmakers", []):
        for m in b.get("markets", []):
            if m["key"] != MKT[mk]:
                continue
            by = defaultdict(dict)
            for o in m["outcomes"]:
                if name_ok(o.get("description", ""), name):
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


def score(p25, p26):
    out = defaultdict(lambda: defaultdict(list))
    for season, pbp in (("2025", p25), ("2026", p26)):
        for r in run(pbp):
            f = os.path.join(ROOT, "data", "props_lines_wr", season, r["game_id"] + ".json")
            preds = {"yds": [("targets method", r["p_yds"]),
                             ("season average", r["p_yds_avg"]),
                             ("ALWAYS OVER", None), ("ALWAYS UNDER", None)],
                     "rec": [("targets method", r["p_rec"]),
                             ("ALWAYS OVER", None), ("ALWAYS UNDER", None)]}
            for mk, plist in preds.items():
                ln = line_for(f, r["player"], mk)
                if not ln:
                    continue
                pt, po, pu = ln
                act = r[mk]
                for name, p in plist:
                    key = (r["ranking"], mk, name)
                    out[key]["line_miss"].append(abs(pt - act))
                    if p is not None:
                        out[key]["miss"].append(abs(p - act))
                    if act == pt:
                        continue
                    over = (p > pt) if p is not None else name == "ALWAYS OVER"
                    won = (act > pt) == over
                    out[key]["bets"].append((abs(p - pt) if p is not None else 99,
                                             won, po if over else pu, season,
                                             "over" if over else "under"))
    th = {"yds": (0, 10, 20), "rec": (0, 1, 2)}
    for key in sorted(out):
        rk, mk, name = key
        d = out[key]
        miss = f"our miss {st.mean(d['miss']):.1f}  " if d["miss"] else ""
        print(f"\n[{rk}] {mk} - {name}: n={len(d['line_miss'])}  {miss}"
              f"line miss {st.mean(d['line_miss']):.1f}")
        for t in (th[mk] if "ALWAYS" not in name else (0,)):
            bets = [b for b in d["bets"] if b[0] >= t]
            if not bets:
                continue
            w = sum(b[1] for b in bets)
            prof = sum(payout(b[2]) if b[1] else -1 for b in bets)
            split = "  ".join(
                f"{s}: {sum(b[1] for b in bets if b[3] == s)}-"
                f"{sum(1 for b in bets if b[3] == s and not b[1])}" for s in ("2025", "2026"))
            sides = "  ".join(
                f"{s} {sum(b[1] for b in bets if b[4] == s)}-"
                f"{sum(1 for b in bets if b[4] == s and not b[1])}" for s in ("over", "under"))
            print(f"   gap >= {t:<3} {w}-{len(bets) - w} ({100 * w / len(bets):.1f}%)  "
                  f"ROI {100 * prof / len(bets):+.1f}%   [{split}]  [{sides}]")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "buy":
        buy(sys.argv[2], sys.argv[3], int(sys.argv[4]), "--buy" in sys.argv)
    elif cmd == "score":
        score(sys.argv[2], sys.argv[3])
