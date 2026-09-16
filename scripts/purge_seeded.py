"""Remove archive-seeded snapshots from an in-progress season.

The nflverse archive holds only closing lines, so the loader wrote each
unplayed game a pair: one stamped at kickoff and one at kickoff minus 120
hours. Both are the eventual close wearing an earlier timestamp. Five days out
the second becomes the newest price we hold and the live board quotes it as
today's market -- which is how Seattle read 79.6% after the market had moved
them to 66%.

Only touches snapshots whose captured_at is exactly kickoff or kickoff-120h,
for games that are NOT final. Real captures are never at those instants.

Usage:  python scripts/purge_seeded.py SEASON         # dry run
        python scripts/purge_seeded.py SEASON --apply
"""
import sys
from datetime import timedelta

import _proddb  # noqa: F401
from app import SessionLocal, Game, OddsSnapshot

season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
apply_it = "--apply" in sys.argv

s = SessionLocal()
rows = (s.query(OddsSnapshot, Game).join(Game, Game.id == OddsSnapshot.game_id)
          .filter(Game.season == season, Game.final == False).all())  # noqa: E712
seeded = [sn for sn, g in rows
          if sn.captured_at in (g.kickoff, g.kickoff - timedelta(hours=120))]
keep = {}
for sn, g in rows:
    if sn.captured_at not in (g.kickoff, g.kickoff - timedelta(hours=120)):
        keep[g.id] = keep.get(g.id, 0) + 1
orphans = [g.id for _, g in rows if keep.get(g.id, 0) == 0]

print(f"season {season}, unplayed games")
print(f"  seeded snapshots to remove : {len(seeded)}")
print(f"  games left with no price   : {len(set(orphans))}")
if set(orphans):
    s.close()
    sys.exit("REFUSING: that would leave games unpriced.")
if not apply_it:
    print("\nDRY RUN — nothing deleted. Add --apply.")
else:
    for sn in seeded:
        s.delete(sn)
    s.commit()
    print(f"\ndeleted {len(seeded)} seeded snapshots")
s.close()
