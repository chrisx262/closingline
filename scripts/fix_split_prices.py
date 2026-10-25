"""Repair prices that were averaged straight across even money.

The consensus used to take the plain mean of each book's american price. When
books sit either side of even (-110 here, +108 there) that mean is about -1,
which is not a price: it reads as a 1% chance. Week 8's ATL @ TB came out
ATL -1, and the survivor board put TB at 98% in a game TB is favoured by one
point. loaders/real_data.py::avg_american now averages through decimal odds.

This fixes the rows already stored. A valid american price is never strictly
between -100 and +100, so those rows are exactly the damaged ones.

  - 2025 openers were bought and the raw feed is kept in data/opening_lines/,
    so those are recomputed exactly from it.
  - Live captures kept no raw feed. A damaged price is rebuilt from the
    OTHER side of the same market in the same snapshot, at the median
    bookmaker hold of every undamaged pair we hold for that market (about
    4.5%). If both sides are damaged, both sat at even money, so each is
    priced at half of (1 + hold): about -109. The plain mean cannot be
    inverted -- with uneven book counts the 200-point gap between -100 and
    +100 dominates it ([-105, +100, -105] means -37) -- so it is not used.

Picks are NOT touched (invariant 1). The script lists any pick priced at a
damaged number so it can be recorded, not rewritten.

Usage:  railway run --service Postgres python3 scripts/fix_split_prices.py          # dry run
        railway run --service Postgres python3 scripts/fix_split_prices.py --apply
        python3 scripts/fix_split_prices.py --local [--apply]                       # local DB
"""
import os
import sys

if "--local" in sys.argv:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
else:
    import _proddb  # noqa: F401
from app import SessionLocal, Game, OddsSnapshot, Pick
from loaders.real_data import TEAM_ABBR, _consensus, _match_game
from loaders.opening_lines import _iter_snapshots

PRICES = ("spread_home_odds", "spread_away_odds", "over_odds", "under_odds",
          "ml_home", "ml_away")
apply_it = "--apply" in sys.argv


def bad(v):
    return v is not None and -100 < v < 100


PAIRS = {"ml_home": "ml_away", "ml_away": "ml_home",
         "spread_home_odds": "spread_away_odds",
         "spread_away_odds": "spread_home_odds",
         "over_odds": "under_odds", "under_odds": "over_odds"}


def implied(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def to_american(p):
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


s = SessionLocal()

# exact recomputation for any snapshot we still hold the raw feed for
exact = {}
for season in (2025, 2026):
    games = s.query(Game).filter(Game.season == season).all()
    for ev, snap_dt in _iter_snapshots(season):
        home = TEAM_ABBR.get(ev.get("home_team", ""))
        away = TEAM_ABBR.get(ev.get("away_team", ""))
        if not home or not away:
            continue
        from datetime import datetime
        commence = datetime.fromisoformat(
            ev["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
        g = _match_game(games, home, away, commence)
        vals = _consensus(ev) if g else None
        if vals:
            exact[(g.id, snap_dt)] = vals

rows = s.query(OddsSnapshot).all()

# median hold per market, from every pair where neither side is damaged
holds = {}
for a in ("ml_home", "spread_home_odds", "over_odds"):
    b = PAIRS[a]
    hs = sorted(implied(getattr(r, a)) + implied(getattr(r, b)) - 1 for r in rows
                if getattr(r, a) is not None and getattr(r, b) is not None
                and not bad(getattr(r, a)) and not bad(getattr(r, b)))
    holds[a] = holds[b] = hs[len(hs) // 2] if hs else 0.045
print("median hold: " + ", ".join(f"{k} {v:.3%}" for k, v in holds.items()
                                    if k in ("ml_home", "spread_home_odds", "over_odds")))
fixed = 0
n_exact = n_approx = 0
for sn in rows:
    hit = [k for k in PRICES if bad(getattr(sn, k))]
    if not hit:
        continue
    raw = exact.get((sn.game_id, sn.captured_at))
    for k in hit:
        old = getattr(sn, k)
        if raw and raw.get(k) is not None and not bad(raw[k]):
            new, how = raw[k], "exact"
            n_exact += 1
        else:
            other = getattr(sn, PAIRS[k])
            if other is not None and not bad(other):
                new = to_american(1 + holds[k] - implied(other))
            else:
                new = to_american((1 + holds[k]) / 2)
            how = "from other side"
            n_approx += 1
        print(f"  {sn.game_id:<18} {sn.captured_at:%Y-%m-%d %H:%M} "
              f"{k:<16} {old:>5} -> {new:>5}  ({how})")
        setattr(sn, k, new)
    fixed += 1

print(f"\n{fixed} snapshots, {n_exact} prices exact from raw feed, "
      f"{n_approx} rebuilt from the other side")

picks = [p for p in s.query(Pick).all()
         if bad(p.snap_odds) or bad(p.close_odds)]
if picks:
    print("\npicks touched by a damaged number (left as recorded, invariant 1):")
    for p in picks:
        print(f"  pick {p.id} agent {p.agent_id} {p.mode} {p.game_id} {p.market} "
              f"{p.side} bought {p.snap_odds} close {p.close_odds} {p.result}")

if not apply_it:
    s.rollback()
    print("\nDRY RUN — nothing written. Add --apply.")
else:
    s.commit()
    print(f"\nwrote {fixed} snapshots")
s.close()
