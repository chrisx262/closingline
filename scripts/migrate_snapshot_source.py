"""Add odds_snapshots.source and backfill it. Idempotent.

Archive rows are identifiable by their timestamps: the nflverse loader writes
them at exactly kickoff and at kickoff minus 120 hours, because the archive
stores only closing lines and that pair is how it fakes an "available" price. A
real capture landing on either instant to the second is not something the odds
cron does.

Usage:  python scripts/migrate_snapshot_source.py         # dry run
        python scripts/migrate_snapshot_source.py --apply
"""
import sys
from datetime import timedelta

import _proddb  # noqa: F401
from sqlalchemy import text

from app import SessionLocal, engine, Game, OddsSnapshot

apply_it = "--apply" in sys.argv
s = SessionLocal()

has = [r[1] for r in s.execute(text(
    "SELECT * FROM information_schema.columns "
    "WHERE table_name='odds_snapshots' AND column_name='source'"))]
if not has:
    print("column 'source' is missing")
    if apply_it:
        s.execute(text("ALTER TABLE odds_snapshots "
                       "ADD COLUMN source VARCHAR NOT NULL DEFAULT 'live'"))
        s.commit()
        print("  added, defaulting every existing row to 'live'")
else:
    print("column 'source' already present")

if not apply_it:
    print("\nDRY RUN — nothing changed. Add --apply.")
    s.close()
    raise SystemExit

rows = (s.query(OddsSnapshot, Game)
          .join(Game, Game.id == OddsSnapshot.game_id).all())
n = 0
for sn, g in rows:
    seeded = sn.captured_at in (g.kickoff, g.kickoff - timedelta(hours=120))
    want = "archive" if seeded else "live"
    if sn.source != want:
        sn.source = want
        n += 1
s.commit()
arch = sum(1 for sn, _ in rows if sn.source == "archive")
print(f"\nreclassified {n} rows")
print(f"  archive: {arch}")
print(f"  live   : {len(rows) - arch}")
s.close()
