"""Where did each game's price actually come from? Read-only.

The nflverse archive writes snapshots timestamped at kickoff and kickoff-120h;
the live odds cron writes them at the moment of capture. Grouping by
captured_at therefore separates seeded prices from real ones, which is the
difference between a market line and a number that merely looks like one.
"""
import _proddb  # noqa: F401  (must precede the app import)
from collections import Counter
from datetime import datetime

from app import SessionLocal, Game, OddsSnapshot

s = SessionLocal()
now = datetime.utcnow()

rows = (s.query(Game.week, OddsSnapshot.captured_at, OddsSnapshot.ml_home)
          .join(OddsSnapshot, OddsSnapshot.game_id == Game.id)
          .filter(Game.season == 2026).all())

by_time = Counter(r[1] for r in rows)
print(f"{len(rows)} snapshots across {len(by_time)} distinct capture times\n")
print("most common capture times:")
for t, n in by_time.most_common(6):
    tag = "FUTURE - archive-seeded" if t > now else "past - real capture"
    print(f"  {t}  {n:>4} snapshots   {tag}")

real = [r for r in rows if r[1] <= now]
print(f"\nsnapshots actually captured before now: {len(real)}")
if real:
    wk = Counter(r[0] for r in real)
    print("  by week:", " ".join(f"w{w}:{wk[w]}" for w in sorted(wk)))
    print("  with a moneyline:", sum(1 for r in real if r[2] is not None))
s.close()
