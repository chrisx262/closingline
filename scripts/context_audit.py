"""Is the per-game context we would filter on actually populated? Read-only."""
import _proddb  # noqa: F401  (must precede the app import)
from collections import Counter

from app import SessionLocal, Game

s = SessionLocal()
g = s.query(Game).filter(Game.season == 2026).all()
print(f"2026 games on prod: {len(g)}")
print(f"  div_game set true : {sum(1 for x in g if x.div_game)}")
print(f"  div_game null     : {sum(1 for x in g if x.div_game is None)}")
print(f"  roof populated    : {sum(1 for x in g if x.roof)}")
wk = Counter(x.week for x in g if x.div_game)
print("  division by week  :", " ".join(f"w{k}:{wk[k]}" for k in sorted(wk)))
s.close()
