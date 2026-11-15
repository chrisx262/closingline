"""RBs against the 8 worst run defenses: backtest, line purchase, scoring.

Same shape as the QB work. For each week W, only plays before W rank the run
defenses and build each back's numbers; every lead-back game (10+ carries)
against a bottom-8 run defense in week W is projected and later scored
against the real rush-yards / rush-attempts lines.

  python3 systems/props_rb.py backtest PBP_CSV_GZ
  python3 systems/props_rb.py buy PBP_CSV_GZ GAMES_CSV SEASON [--buy]
  python3 systems/props_rb.py score PBP_2025 PBP_2026
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

MIN_CAR = 10
FIRST_WEEK = 5
MKT = {"yds": "player_rush_yds", "car": "player_rush_attempts"}


def load(path):
    games = defaultdict(lambda: [0, 0.0])        # (wk, gid, rb, team, opp) -> car, yds
    with gzip.open(path, "rt") as fh:
        for r in csv.DictReader(fh):
            if r["season_type"] != "REG" or r["rush_attempt"] != "1":
                continue
            if r.get("qb_kneel") == "1" or r.get("qb_scramble") == "1":
                continue
            if r.get("two_point_attempt") == "1" or not r["rusher_player_name"]:
                continue
            k = (int(r["week"]), r["game_id"], r["rusher_player_name"],
                 r["posteam"], r["defteam"])
            games[k][0] += 1
            games[k][1] += float(r["rushing_yards"] or 0)
    return games


def run(path):
    games = load(path)
    rows = []
    for W in range(FIRST_WEEK, max(k[0] for k in games) + 1):
        before = {k: v for k, v in games.items() if k[0] < W}
        d = defaultdict(lambda: [0, 0.0, set()])
        for (wk, gid, rb, pos, de), (c, y) in before.items():
            d[de][0] += c; d[de][1] += y; d[de][2].add(gid)
        ypc = {t: v[1] / v[0] for t, v in d.items()}
        ypg = {t: v[1] / len(v[2]) for t, v in d.items()}
        rankings = {"ypc": sorted(ypc, key=ypc.get)[-8:],
                    "ypg": sorted(ypg, key=ypg.get)[-8:]}
        starts = {k: v for k, v in before.items() if v[0] >= MIN_CAR}
        rb = defaultdict(lambda: [0, 0, 0.0])
        for k, (c, y) in starts.items():
            rb[k[2]][0] += 1; rb[k[2]][1] += c; rb[k[2]][2] += y
        for rk, worst in rankings.items():
            car_vs = sorted(v[0] for k, v in starts.items() if k[4] in worst)
            if len(car_vs) < 6:
                continue
            tr = car_vs[1:-1]
            trim_avg = sum(tr) / len(tr)
            # The back is chosen BEFORE the game: whoever led his team in
            # carries (10+) in its most recent game. Filtering on carries in
            # the game being predicted would quietly drop every early injury
            # or benching -- the games unders win -- and flatter the overs.
            lead = {}
            for (wk, gid, name, pos, de), (cc, yy) in before.items():
                if cc >= MIN_CAR and (pos not in lead or (wk, cc) > lead[pos][:2]):
                    lead[pos] = (wk, cc, name)
            for k, (c, y) in games.items():
                if k[0] != W or k[4] not in worst:
                    continue
                if lead.get(k[3], (0, 0, None))[2] != k[2]:
                    continue
                q = rb.get(k[2])
                if not q or q[0] < 2:
                    continue
                own_car, own_ypc, own_ypg = q[1] / q[0], q[2] / q[1], q[2] / q[0]
                blend = (own_ypc + ypc[k[4]]) / 2
                rows.append({"week": W, "game_id": k[1], "rb": k[2],
                             "team": k[3], "opp": k[4], "ranking": rk,
                             "car": c, "yds": y,
                             "p_car_trim": trim_avg, "p_car_own": own_car,
                             "p_yds": trim_avg * blend,
                             "p_yds_own": own_car * blend,
                             "p_yds_avg": own_ypg})
    return rows


def buy(pbp, games_csv, season, really):
    rows = run(pbp)
    ko = pl.kickoffs(games_csv, season)
    wanted = sorted({r["game_id"] for r in rows})
    outdir = os.path.join(ROOT, "data", "props_lines_rb", str(season))
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


def line_for(path, name, mk):
    if not os.path.exists(path):
        return None
    ev = json.load(open(path)).get("data") or {}
    init, last = name.split(".", 1) if "." in name else ("", name)
    mains = []
    for b in ev.get("bookmakers", []):
        for m in b.get("markets", []):
            if m["key"] != MKT[mk]:
                continue
            by = defaultdict(dict)
            for o in m["outcomes"]:
                p = o.get("description", "").split()
                if not p or p[-1].lower().strip(".") not in (last.split()[-1].lower(),):
                    if not (len(p) > 1 and p[-2].lower() == last.split()[-1].lower()):
                        continue                        # "Kenneth Walker III"
                if init and p[0][0].upper() != init[0].upper():
                    continue
                by[o.get("point")][o["name"]] = o["price"]
            pairs = [(pt, s["Over"], s["Under"]) for pt, s in by.items()
                     if "Over" in s and "Under" in s]
            if pairs:
                mains.append(min(pairs, key=lambda x: abs(implied(x[1]) - implied(x[2]))))
    if not mains:
        return None
    pt = st.median([x[0] for x in mains])
    at = [x for x in mains if x[0] == pt] or \
         [x for x in mains if x[0] == min((y[0] for y in mains), key=lambda v: abs(v - pt))]
    return at[0][0], med_price([x[1] for x in at]), med_price([x[2] for x in at])


def score(p25, p26):
    out = defaultdict(lambda: defaultdict(list))
    for season, pbp in (("2025", p25), ("2026", p26)):
        for r in run(pbp):
            f = os.path.join(ROOT, "data", "props_lines_rb", season, r["game_id"] + ".json")
            preds = {"yds": [("trim carries x blend ypc", r["p_yds"]),
                             ("own carries x blend ypc", r["p_yds_own"]),
                             ("RB season average", r["p_yds_avg"]),
                             ("ALWAYS OVER", None), ("ALWAYS UNDER", None)],
                     "car": [("trim carries", r["p_car_trim"]),
                             ("own carries", r["p_car_own"]),
                             ("ALWAYS OVER", None), ("ALWAYS UNDER", None)]}
            for mk, plist in preds.items():
                ln = line_for(f, r["rb"], mk)
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
                                             won, po if over else pu, season))
    th = {"yds": (0, 10, 20), "car": (0, 2, 4)}
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
            print(f"   gap >= {t:<3} {w}-{len(bets) - w} ({100 * w / len(bets):.1f}%)  "
                  f"ROI {100 * prof / len(bets):+.1f}%   [{split}]")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "backtest":
        rows = run(sys.argv[2])
        print(len(rows), "rows,", len({r["game_id"] for r in rows}), "games")
    elif cmd == "buy":
        buy(sys.argv[2], sys.argv[3], int(sys.argv[4]), "--buy" in sys.argv)
    elif cmd == "score":
        score(sys.argv[2], sys.argv[3])
