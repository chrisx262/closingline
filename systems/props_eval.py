"""Score the QB projections against real sportsbook prop lines.

For each QB start in the backtest, takes the consensus line (median point
across books, ~90 min before kickoff) and bets the side the projection points
to. Reports win rate and ROI at the median price, overall and only where the
projection disagrees with the line by at least a threshold.

Usage: python3 systems/props_eval.py PBP_2025 PBP_2026
"""
import json
import os
import statistics as st
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "systems"))
import props_backtest  # noqa: E402

MKT = {"yds": "player_pass_yds", "att": "player_pass_attempts",
       "cmp": "player_pass_completions"}


def line_for(game_file, qb, market):
    """(consensus point, over price, under price) or None.

    Some books list several points for one player in the same market. Each
    book's MAIN line is the pair whose two prices sit closest together; the
    consensus is the median of those, priced at the median of the books that
    hang exactly that number (else -110).
    """
    if not os.path.exists(game_file):
        return None
    ev = json.load(open(game_file)).get("data") or {}
    init, last = qb.split(".", 1) if "." in qb else ("", qb)
    mains = []                      # (point, over price, under price) per book
    for b in ev.get("bookmakers", []):
        for m in b.get("markets", []):
            if m["key"] != MKT[market]:
                continue
            by_pt = defaultdict(dict)
            for o in m["outcomes"]:
                parts = o.get("description", "").split()
                if not parts or parts[-1].lower() != last.split()[-1].lower():
                    continue
                if init and parts[0][0].upper() != init[0].upper():
                    continue
                by_pt[o.get("point")][o["name"]] = o["price"]
            pairs = [(pt, s["Over"], s["Under"]) for pt, s in by_pt.items()
                     if "Over" in s and "Under" in s]
            if pairs:
                mains.append(min(pairs, key=lambda x: abs(implied(x[1]) - implied(x[2]))))
    if not mains:
        return None
    point = st.median([x[0] for x in mains])
    at = [x for x in mains if x[0] == point]
    if not at:
        point = min((x[0] for x in mains), key=lambda p: abs(p - point))
        at = [x for x in mains if x[0] == point]
    return point, med_price([x[1] for x in at]), med_price([x[2] for x in at])


def med_price(prices):
    """Median american price, taken in decimal odds. A plain median of -110
    and +100 is -5, the same trap as the site's split-price bug."""
    d = st.median([1 + (p / 100 if p > 0 else 100 / -p) for p in prices])
    return int(round((d - 1) * 100)) if d >= 2 else int(round(-100 / (d - 1)))


def implied(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def payout(price):
    return price / 100 if price > 0 else 100 / -price


def main():
    out = defaultdict(lambda: defaultdict(list))
    for season, pbp in (("2025", sys.argv[1]), ("2026", sys.argv[2])):
        for r in props_backtest.run(pbp)[2]:
            f = os.path.join(ROOT, "data", "props_lines", season,
                             r["game_id"] + ".json")
            preds = {"yds": [("your method", r["p_yds"]),
                             ("QB season average", r["p_yds_avg"])],
                     "att": [("trimmed avg", r["p_att"]),
                             ("QB own avg", r["p_att_own"])],
                     "cmp": [("trimmed avg x blend", r["p_att"] * r["p_cmp_pct"])]}
            for mk, plist in preds.items():
                ln = line_for(f, r["qb"], mk)
                if not ln:
                    continue
                point, po, pu = ln
                actual = r[mk]
                for name, p in plist:
                    key = (r["ranking"], mk, name)
                    out[key]["line_miss"].append(abs(point - actual))
                    out[key]["our_miss"].append(abs(p - actual))
                    if actual == point:
                        continue
                    over = p > point
                    won = (actual > point) == over
                    price = po if over else pu
                    edge = abs(p - point)
                    out[key]["bets"].append((edge, won, price, season))
                    out[key]["prices"].append(price)
                    out[key]["sides"].append(("over" if over else "under", won))

    th = {"yds": (0, 15, 30), "att": (0, 1.5, 3), "cmp": (0, 1, 2)}
    for key in sorted(out):
        rk, mk, name = key
        d = out[key]
        print(f"\n[{rk} ranking] {mk} - {name}:  n={len(d['our_miss'])}  "
              f"our avg miss {st.mean(d['our_miss']):.1f}  "
              f"sportsbook line avg miss {st.mean(d['line_miss']):.1f}  "
              f"median price {st.median(d['prices'])}  "
              f"overs {sum(1 for s, w in d['sides'] if s == 'over' and w)}-"
              f"{sum(1 for s, w in d['sides'] if s == 'over' and not w)}  "
              f"unders {sum(1 for s, w in d['sides'] if s == 'under' and w)}-"
              f"{sum(1 for s, w in d['sides'] if s == 'under' and not w)}")
        for t in th[mk]:
            bets = [b for b in d["bets"] if b[0] >= t]
            if not bets:
                continue
            w = sum(b[1] for b in bets)
            profit = sum(payout(b[2]) if b[1] else -1 for b in bets)
            by = {s: [b for b in bets if b[3] == s] for s in ("2025", "2026")}
            split = "  ".join(f"{s}: {sum(b[1] for b in v)}-{len(v) - sum(b[1] for b in v)}"
                              for s, v in by.items() if v)
            print(f"   disagree by >= {t:<4} bets {len(bets):>3}  "
                  f"won {w}-{len(bets) - w} ({100 * w / len(bets):.1f}%)  "
                  f"ROI {100 * profit / len(bets):+.1f}%   [{split}]")


if __name__ == "__main__":
    main()
