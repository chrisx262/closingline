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

s = SessionLocal()
try:
    already_seeded = s.query(Game).count() > 0
finally:
    s.close()

if already_seeded:
    print("boot: DB already has games — skipping season preload")
else:
    print("boot: empty DB — loading 2025 season ...")
    from loaders.nflverse_loader import load
    try:
        load([2025])
    except Exception as e:  # never block startup on a data-source hiccup
        print(f"boot: season preload failed, starting with empty board: {e}")

# Railway injects $PORT; fall back to 8000 for local/dev.
port = os.environ.get("PORT", "8000")
print(f"boot: starting uvicorn on 0.0.0.0:{port}")
os.execvp("uvicorn", ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", port])
