"""
SURVIVOR BACKTEST — does the market number mean what it says, and what
actually killed people?

WHY THIS EXISTS
---------------
A survivor simulator is only worth running if its inputs are honest. Ours are
de-vigged market win probabilities, and the whole plan rests on them. So before
trusting a survival curve, check the input against a season that already
happened: when the market said 75%, did those teams win 75% of the time?

Modelled on SurvivorGrid's "Knockouts" page, which reports the upsets that
eliminated the most entries. We cannot copy the entry-weighted part of it — that
needs real pick-popularity data we do not have, and theirs comes from public
Yahoo/ESPN pools whose field is nothing like Circa's. What we CAN do, and what
matters more for calibration, is measure the market itself and walk a real
strategy through a real season.

WHAT IT REPORTS
  1. CALIBRATION  — market win% bucketed against actual win rate. If the market
     is well calibrated the two columns track each other, and a simulator fed
     these numbers produces believable survival curves. If they diverge, the
     simulator is built on sand and we should know that first.
  2. GREEDY WALK  — take the highest win% team still unused, every week, and see
     how far it gets. This is what most of the field does.
  3. TOP UPSETS   — the biggest favourites that lost, which is where survivor
     entries actually die.

Run:  python systems/survivor_backtest.py [season] [--url URL]
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, ".")

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:                                    # pragma: no cover
    _CTX = None

DEFAULT_URL = "https://www.closinglinehq.com"


def _get(base, path, **q):
    url = f"{base}{path}?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=60, context=_CTX) as r:
        return json.load(r)


def load(base, season):
    """Market win prob per team per week, joined to the actual result."""
    wp = {}
    data = _get(base, "/data/survivor", season=season, weeks=18)
    for w in data.get("weeks", []):
        for g in w.get("games", []):
            if g.get("home_wp") is None:
                continue
            wp[(w["week"], g["home"])] = (g["home_wp"], g["away"], True)
            wp[(w["week"], g["away"])] = (g["away_wp"], g["home"], False)

    rows = []
    for week in range(1, 19):
        try:
            slate = _get(base, "/data/slate", week=week, season=season)
        except Exception:
            continue
        slate = slate if isinstance(slate, list) else slate.get("games", [])
        for g in slate:
            if not g.get("final") or g.get("home_score") is None:
                continue
            hs, as_ = g["home_score"], g["away_score"]
            for team, opp, won in ((g["home"], g["away"], hs > as_),
                                   (g["away"], g["home"], as_ > hs)):
                hit = wp.get((week, team))
                if not hit:
                    continue
                rows.append({"week": week, "team": team, "opp": opp,
                             "wp": hit[0], "home": hit[2], "won": won,
                             "tie": hs == as_,
                             "score": f"{as_}-{hs}"})
    return rows


def calibration(rows):
    """Market win% vs what actually happened, in 10-point buckets.

    A tie is counted as NOT surviving. Circa eliminates on a tie, so that is
    the number we care about — and it is why this can read slightly below a
    conventional win-probability check."""
    buckets = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    print("CALIBRATION — does the market number hold up?\n")
    print(f"  {'market says':>14}  {'picks':>6}  {'actually won':>13}  {'gap':>7}")
    tot_p = tot_a = tot_n = 0
    for lo, hi in buckets:
        b = [r for r in rows if lo <= r["wp"] < hi]
        if not b:
            continue
        pred = sum(r["wp"] for r in b) / len(b)
        act = sum(1 for r in b if r["won"]) / len(b)
        tot_p += pred * len(b); tot_a += act * len(b); tot_n += len(b)
        print(f"  {int(lo*100):>6}-{int(hi*100):<3}%  {len(b):>6}  "
              f"{pred*100:>5.1f}% -> {act*100:>5.1f}%  {(act-pred)*100:>+6.1f}")
    if tot_n:
        print(f"\n  overall: predicted {tot_p/tot_n*100:.1f}%, "
              f"actual {tot_a/tot_n*100:.1f}% over {tot_n} team-weeks")
        gap = (tot_a - tot_p) / tot_n * 100
        print(f"  overall gap {gap:+.1f}pt")
        # An overall figure can hide a badly-behaved band, so report the worst
        # bucket that has enough picks to mean anything rather than declaring
        # victory on the average alone.
        worst, worst_gap, worst_n = None, 0.0, 0
        for lo, hi in buckets:
            b = [r for r in rows if lo <= r["wp"] < hi]
            if len(b) < 30:
                continue
            g = (sum(1 for r in b if r["won"]) / len(b)
                 - sum(r["wp"] for r in b) / len(b)) * 100
            if abs(g) > abs(worst_gap):
                worst, worst_gap, worst_n = (lo, hi), g, len(b)
        if worst:
            print(f"  worst band with a real sample: {int(worst[0]*100)}-"
                  f"{int(worst[1]*100)}% off by {worst_gap:+.1f}pt "
                  f"over {worst_n} picks")
        if abs(gap) < 2 and abs(worst_gap) < 6:
            print("  -> market holds up; a simulator fed these numbers is believable")
        else:
            print("  -> one season is a small sample, but do not present "
                  "simulated survival odds to two decimal places")
    ties = [r for r in rows if r["tie"]]
    print(f"\n  ties in the season: {len(set((r['week'], r['team']) for r in ties))//2}"
          " (each one eliminates a Circa entry that picked either side)")


def greedy_walk(rows):
    """Pick the best available team every week and see how far it gets."""
    by_week = {}
    for r in rows:
        by_week.setdefault(r["week"], []).append(r)
    used, alive = set(), True
    print("\n\nGREEDY WALK — best unused team, every week\n")
    for week in sorted(by_week):
        cands = [r for r in by_week[week] if r["team"] not in used]
        if not cands:
            print(f"  wk {week:<3} no unused team left"); break
        pick = max(cands, key=lambda r: r["wp"])
        used.add(pick["team"])
        ok = pick["won"]
        mark = "OK " if ok else ("TIE" if pick["tie"] else "DEAD")
        print(f"  wk {week:<3} {pick['team']:<4} "
              f"{'vs' if pick['home'] else '@ '} {pick['opp']:<4} "
              f"{pick['wp']*100:>5.1f}%  {pick['score']:>7}  {mark}")
        if not ok:
            alive = False
            print(f"\n  eliminated in week {week} on a "
                  f"{pick['wp']*100:.1f}% favourite.")
            break
    if alive:
        print("\n  survived all 18 weeks.")


def elimination_curve(rows, entries=2000, top_k=3, seed=7):
    """The Knockouts idea, rebuilt from results we own.

    A single greedy path is one coin-flip sequence, not a distribution. So run a
    FIELD: `entries` entries that each week pick at random among the top `top_k`
    teams still available to them. That is roughly how a real field behaves —
    everyone crowds the same few favourites but not identically — and because
    it runs against actual 2025 results, the curve is history, not simulation.
    """
    import random
    rnd = random.Random(seed)
    by_week = {}
    for r in rows:
        by_week.setdefault(r["week"], []).append(r)
    weeks = sorted(by_week)

    alive_after = {w: 0 for w in weeks}
    death_week, killers = [], {}
    for _ in range(entries):
        used, dead_at, killed_by = set(), None, None
        for w in weeks:
            cands = sorted([r for r in by_week[w] if r["team"] not in used],
                           key=lambda r: -r["wp"])[:top_k]
            if not cands:
                break
            pick = rnd.choice(cands)
            used.add(pick["team"])
            if not pick["won"]:
                dead_at, killed_by = w, pick["team"]
                break
            alive_after[w] += 1
        death_week.append(dead_at or 99)
        if killed_by:
            killers[(dead_at, killed_by)] = killers.get((dead_at, killed_by), 0) + 1

    print(f"\n\nELIMINATION CURVE — {entries} entries, each week picking at "
          f"random from the top {top_k} available\n")
    print(f"  {'wk':>3}  {'still alive':>11}   ")
    for w in weeks:
        pct = alive_after[w] / entries * 100
        bar = "#" * int(round(pct / 2.5))
        print(f"  {w:>3}  {pct:>10.1f}%  {bar}")
    survived = sum(1 for d in death_week if d == 99)
    print(f"\n  survived the season: {survived}/{entries} "
          f"({survived/entries*100:.1f}%)")
    med = sorted(d for d in death_week if d != 99)
    if med:
        print(f"  median entry died in week {med[len(med)//2]}")
    top = sorted(killers.items(), key=lambda kv: -kv[1])[:5]
    print("\n  biggest killers (week, team picked, entries lost):")
    for (w, t), n in top:
        print(f"    wk {w:<3} {t:<4} {n:>5} entries "
              f"({n/entries*100:.1f}% of the field)")
    return {"alive_after": alive_after, "survived": survived,
            "entries": entries, "killers": killers,
            "median_death": med[len(med) // 2] if med else None}


def top_upsets(rows, n=10):
    """Where entries actually die: the biggest favourites that lost."""
    lost = sorted([r for r in rows if not r["won"]],
                  key=lambda r: -r["wp"])[:n]
    print("\n\nTOP UPSETS — the favourites that killed entries\n")
    print(f"  {'wk':>3}  {'pick':<5} {'':2} {'opp':<5} {'market':>7}  {'score':>8}")
    for r in lost:
        print(f"  {r['week']:>3}  {r['team']:<5} {'vs' if r['home'] else '@ ':2} "
              f"{r['opp']:<5} {r['wp']*100:>6.1f}%  {r['score']:>8}"
              f"{'  (tie)' if r['tie'] else ''}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("season", nargs="?", type=int, default=2025)
    ap.add_argument("--url", default=DEFAULT_URL)
    a = ap.parse_args()
    rows = load(a.url, a.season)
    print(f"{a.season}: {len(rows)} graded team-weeks with a market price\n")
    if not rows:
        print("no data — is that season loaded?"); return
    calibration(rows)
    greedy_walk(rows)
    elimination_curve(rows)
    top_upsets(rows)


if __name__ == "__main__":
    main()
