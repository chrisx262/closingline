"""Backtest QB passing projections against the 8 worst pass defenses.

For every week W from FIRST_WEEK on, uses ONLY plays from weeks before W to
rank defenses and build each QB's numbers, then predicts every QB start
(15+ attempts) against a bottom-8 defense in week W and scores it against
what happened. The real starter is taken as known: this tests the method,
not starter-guessing.

Usage: python3 systems/props_backtest.py PBP_CSV_GZ [FIRST_WEEK]
"""
import csv
import gzip
import sys
from collections import defaultdict

MIN_ATT = 15
FIRST_WEEK = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def load(path):
    """QB-game rows: (week, game, qb, team, opp) -> att, cmp, yds."""
    games = defaultdict(lambda: [0, 0, 0.0])
    with gzip.open(path, "rt") as fh:
        for r in csv.DictReader(fh):
            if r["season_type"] != "REG" or r["pass_attempt"] != "1":
                continue
            if r["sack"] == "1" or r.get("two_point_attempt") == "1":
                continue
            if not r["passer_player_name"]:
                continue
            k = (int(r["week"]), r["game_id"], r["passer_player_name"],
                 r["posteam"], r["defteam"])
            g = games[k]
            g[0] += 1
            g[1] += r["complete_pass"] == "1"
            g[2] += float(r["passing_yards"] or 0)
    return games


def trimmed(xs, n=1):
    xs = sorted(xs)
    return xs[n:-n] if len(xs) > 2 * n + 2 else xs


def run(path):
    games = load(path)
    last_week = max(k[0] for k in games)
    res = defaultdict(list)          # method -> [(pred, actual)]
    floor_hits = defaultdict(lambda: [0, 0])
    for W in range(FIRST_WEEK, last_week + 1):
        before = {k: v for k, v in games.items() if k[0] < W}
        # defense tallies (every pass, not just starters)
        d = defaultdict(lambda: [0, 0, 0.0, set()])
        for (wk, gid, qb, pos, de), (a, c, y) in before.items():
            t = d[de]
            t[0] += a; t[1] += c; t[2] += y; t[3].add(gid)
        ypa = {t: v[2] / v[0] for t, v in d.items()}
        ypg = {t: v[2] / len(v[3]) for t, v in d.items()}
        rankings = {"ypa": sorted(ypa, key=ypa.get)[-8:],
                    "ypg": sorted(ypg, key=ypg.get)[-8:]}
        ypc = {t: v[2] / v[1] for t, v in d.items()}
        cmpa = {t: v[1] / v[0] for t, v in d.items()}

        starts = {k: v for k, v in before.items() if v[0] >= MIN_ATT}
        qb = defaultdict(lambda: [0, 0, 0, 0.0])
        for k, (a, c, y) in starts.items():
            q = qb[k[2]]
            q[0] += 1; q[1] += a; q[2] += c; q[3] += y

        for rk, worst in rankings.items():
            att_vs = [v[0] for k, v in starts.items() if k[4] in worst]
            if len(att_vs) < 6:
                continue
            fl100 = min(att_vs)
            tr = trimmed(att_vs)
            fl_trim, avg_trim = tr[0], sum(tr) / len(tr)
            cmp_vs = (sum(v[1] for k, v in starts.items() if k[4] in worst) /
                      sum(v[0] for k, v in starts.items() if k[4] in worst))

            for k, (a, c, y) in games.items():
                if k[0] != W or a < MIN_ATT or k[4] not in worst:
                    continue
                q = qb.get(k[2])
                if not q or q[0] < 2:
                    continue
                de = k[4]
                own_att, own_cmp = q[1] / q[0], q[2] / q[1]
                own_ypg = q[3] / q[0]
                blend = (own_cmp + cmpa[de]) / 2
                tag = rk + ":"
                floor_hits[tag + "floor100"][0] += a >= fl100
                floor_hits[tag + "floor100"][1] += 1
                floor_hits[tag + "trim_floor"][0] += a >= fl_trim
                floor_hits[tag + "trim_floor"][1] += 1
                for name, att in (("trim_avg", avg_trim), ("own_att", own_att),
                                  ("trim_floor", fl_trim)):
                    res[tag + "att " + name].append((att, a))
                    res[tag + "yds " + name + " x blend x opp_ypc"].append(
                        (att * blend * ypc[de], y))
                    res[tag + "yds " + name + " x own_cmp x opp_ypc"].append(
                        (att * own_cmp * ypc[de], y))
                res[tag + "yds QB season avg (overall-average baseline)"].append(
                    (own_ypg, y))
                res[tag + "cmp% own"].append((own_cmp, c / a))
                res[tag + "cmp% blend"].append((blend, c / a))
                res[tag + "cmp% group vs weak D"].append((cmp_vs, c / a))
    return res, floor_hits


def report(res, floor_hits):
    print(f"{'method':<58}{'n':>5}{'avg miss':>10}{'bias':>8}")
    for k in sorted(res):
        pa = res[k]
        mae = sum(abs(p - a) for p, a in pa) / len(pa)
        bias = sum(p - a for p, a in pa) / len(pa)
        fmt = "{:>10.3f}{:>8.3f}" if "cmp%" in k else "{:>10.1f}{:>8.1f}"
        print(f"{k:<58}{len(pa):>5}" + fmt.format(mae, bias))
    print("\nhow often the QB reached the floor:")
    for k, (h, n) in sorted(floor_hits.items()):
        print(f"  {k:<30} {h}/{n} = {100 * h / n:.0f}%")


if __name__ == "__main__":
    report(*run(sys.argv[1]))
