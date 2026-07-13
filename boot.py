"""Container entrypoint for production (Railway).

Why this exists: the season preload must land in the LIVE database
(Postgres via DATABASE_URL), which only exists at runtime — not at docker
build time. So we seed here, on first boot, and only if the DB is empty.
That keeps the board populated on day one without duplicating odds
snapshots on every redeploy (games merge cleanly, but snapshots are
append-only, so re-seeding a non-empty DB would double them).
"""
import os

from app import SessionLocal, Base, engine, Game

# Ensure tables exist on a fresh Postgres, then check if we need to seed.
Base.metadata.create_all(engine)

# 2026 matters as much as 2025: the odds cron matches snapshots against
# these rows — without the coming season's schedule every snapshot goes
# unmatched. Seeding is per-season so an already-seeded DB still picks up
# a season it's missing (games merge by id, so this never duplicates).
WANT_SEASONS = [2025, 2026]

s = SessionLocal()
try:
    have = {row[0] for row in s.query(Game.season).distinct()}
finally:
    s.close()

missing = [y for y in WANT_SEASONS if y not in have]
if not missing:
    print(f"boot: seasons {sorted(have)} present — skipping preload")
else:
    print(f"boot: loading missing season(s) {missing} ...")
    from loaders.nflverse_loader import load
    try:
        load(missing)
    except Exception as e:  # never block startup on a data-source hiccup
        print(f"boot: season preload failed, continuing anyway: {e}")

# Railway injects $PORT; fall back to 8000 for local/dev.
port = os.environ.get("PORT", "8000")
print(f"boot: starting uvicorn on 0.0.0.0:{port}")
os.execvp("uvicorn", ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", port])
