"""Chris's method: QBs vs the 8 worst pass defenses (prototype).

python3 -I qb_weakd.py PBP_CSV_GZ GAMES_CSV SEASON THROUGH_WEEK TARGET_WEEK
"""
import csv, gzip, sys, json
from collections import defaultdict

pbp, games_csv, season, thru, target = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
MIN_ATT = 15          # a QB-game counts as a start at 15+ attempts

def f(x):
    try: return float(x)
    except: return 0.0

# per defense, per QB-game
d_att = defaultdict(float); d_cmp = defaultdict(float); d_yds = defaultdict(float)
qbg = defaultdict(lambda: {"att": 0, "cmp": 0, "yds": 0.0})   # (game, qb) -> stats
qb_team = {}
with gzip.open(pbp, "rt") as fh:
    for r in csv.DictReader(fh):
        if r["season_type"] != "REG" or int(r["week"]) > thru: continue
        if r["pass_attempt"] != "1" or r["sack"] == "1" or not r["passer_player_name"]: continue
        if r.get("two_point_attempt") == "1": continue
        de = r["defteam"]; c = r["complete_pass"] == "1"; y = f(r["passing_yards"])
        d_att[de] += 1; d_cmp[de] += c; d_yds[de] += y
        k = (r["game_id"], r["week"], r["passer_player_name"], r["posteam"], de)
        g = qbg[k]; g["att"] += 1; g["cmp"] += c; g["yds"] += y
        qb_team[r["passer_player_name"]] = r["posteam"]

ypa = {t: d_yds[t] / d_att[t] for t in d_att}
rank = sorted(ypa, key=lambda t: ypa[t])          # 1 = best ... 32 = worst
worst8 = rank[-8:]
ypc = {t: d_yds[t] / d_cmp[t] for t in d_att}
cmp_allowed = {t: d_cmp[t] / d_att[t] for t in d_att}

starts = {k: v for k, v in qbg.items() if v["att"] >= MIN_ATT}
vs_weak = [v for k, v in starts.items() if k[4] in worst8]
atts = sorted(v["att"] for v in vs_weak)
def pct_floor(p):   # attempts reached by p of the starts
    return atts[int((1 - p) * (len(atts) - 1))]
weak_cmp = sum(v["cmp"] for v in vs_weak) / sum(v["att"] for v in vs_weak)

# each QB's own season numbers (starts only)
qs = defaultdict(lambda: {"g": 0, "att": 0, "cmp": 0, "yds": 0.0})
for k, v in starts.items():
    q = qs[k[2]]; q["g"] += 1; q["att"] += v["att"]; q["cmp"] += v["cmp"]; q["yds"] += v["yds"]

# target week matchups
match = []
for r in csv.DictReader(open(games_csv)):
    if r["season"] == str(season) and r["week"] == str(target) and r["game_type"] == "REG":
        match += [(r["away_team"], r["home_team"]), (r["home_team"], r["away_team"])]

# the QB who started most recently for each team
last = {}
for k, v in starts.items():
    gid, wk, qb, pos, de = k
    if pos not in last or int(wk) > last[pos][0]:
        last[pos] = (int(wk), qb)

out = {"season": season, "through_week": thru, "target_week": target,
       "worst8": [{"team": t, "rank": 32 - i, "ypa": round(ypa[t], 2),
                   "ypc": round(ypc[t], 2), "cmp_allowed": round(cmp_allowed[t], 3)}
                  for i, t in enumerate(reversed(worst8))],
       "starts_vs_weak": len(vs_weak),
       "floor100": atts[0], "floor90": pct_floor(.9), "floor80": pct_floor(.8),
       "median_att": atts[len(atts) // 2], "weak_cmp": round(weak_cmp, 3),
       "projections": []}
for off, de in match:
    if de not in worst8 or off not in last: continue
    qb = last[off][1]; q = qs[qb]
    own_cmp = q["cmp"] / q["att"]; own_att = q["att"] / q["g"]
    blend = (own_cmp + cmp_allowed[de]) / 2
    row = {"qb": qb, "team": off, "opp": de, "opp_rank": 32 - worst8[::-1].index(de),
           "games": q["g"], "own_att": round(own_att, 1), "own_cmp": round(own_cmp, 3),
           "opp_cmp_allowed": round(cmp_allowed[de], 3), "blend_cmp": round(blend, 3),
           "opp_ypc": round(ypc[de], 2)}
    for name, a in (("floor100", out["floor100"]), ("floor80", out["floor80"]), ("own", own_att)):
        row["yds_" + name] = round(a * blend * ypc[de])
        row["cmp_" + name] = round(a * blend, 1)
    out["projections"].append(row)
out["projections"].sort(key=lambda r: -r["yds_own"])
print(json.dumps(out, indent=1))
