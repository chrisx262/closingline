"""In-process scheduler — replaces external cron.

Runs inside the (always-on) web service when RUN_SCHEDULER=1 is set, so no
extra Railway cron services or dashboard config are needed. Times are
defined in US Eastern and converted per-tick via zoneinfo, so DST is
handled automatically (the season spans the November change).

Cadence (from loaders/real_data.py) + the Tuesday grading run (README):
  snapshots  Tue 12:00 / Thu 18:00 / Sat 12:00 / Sun 11:35 / Sun 12:45 ET
  weekly     Tue 09:00 ET — weekly_update.py (refresh scores, grade picks)

Budget: one snapshot covers all games and costs 3 Odds API credits
(3 markets x 1 region — verified live). 5/week in-season ~= 66/month
against the free tier's 500. Off-season the snapshot job is skipped
entirely (no kickoff within the next 8 days).
"""
import os
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# (name, weekday Mon=0, hour, minute, job)
SLOTS = [
    ("tue-grade",     1, 9,  0,  "weekly_update"),
    ("tue-open",      1, 12, 0,  "snapshot"),
    ("thu-pre-tnf",   3, 18, 0,  "snapshot"),
    ("sat-midweek",   5, 12, 0,  "snapshot"),
    ("sun-inactives", 6, 11, 35, "snapshot"),
    ("sun-closing",   6, 12, 45, "snapshot"),
]
GRACE_MIN = 15  # a slot fires once anywhere in [t, t+15min) — survives restarts


def due_slots(now_et: datetime, fired: set) -> list:
    """Pure slot logic (unit-tested): which slots should fire right now?
    `fired` holds '<name>:<date>' keys of slots already run."""
    out = []
    for name, wd, hh, mm, job in SLOTS:
        if now_et.weekday() != wd:
            continue
        start = now_et.replace(hour=hh, minute=mm, second=0, microsecond=0)
        key = f"{name}:{now_et.date()}"
        if start <= now_et < start + timedelta(minutes=GRACE_MIN) \
                and key not in fired:
            out.append((key, job))
    return out


def _season_active() -> bool:
    """Skip snapshots (and their API cost) unless a game kicks off within
    8 days — keeps the off-season from burning the request budget."""
    from app import SessionLocal, Game
    s = SessionLocal()
    try:
        now = datetime.utcnow()
        return s.query(Game).filter(
            Game.final == False,  # noqa: E712
            Game.kickoff >= now - timedelta(hours=12),
            Game.kickoff <= now + timedelta(days=8),
        ).count() > 0
    finally:
        s.close()


def _run(job: str):
    if job == "snapshot":
        if not _season_active():
            print("scheduler: no kickoff within 8 days — snapshot skipped")
            return
        from loaders.real_data import snapshot_odds
        snapshot_odds()
    elif job == "weekly_update":
        from sqlalchemy import func
        from app import SessionLocal, Game
        import weekly_update
        s = SessionLocal()
        season = s.query(func.max(Game.season)).scalar()
        s.close()
        if season:
            weekly_update.run(season)


def _loop():
    fired = set()
    while True:
        now_et = datetime.now(ET).replace(tzinfo=None)
        for key, job in due_slots(now_et, fired):
            fired.add(key)
            print(f"scheduler: firing {key} ({job})")
            try:
                _run(job)
            except Exception as e:  # log and keep the loop alive
                print(f"scheduler: {key} failed: {e}")
        # keep only today's keys so the set can't grow unbounded
        today = str(now_et.date())
        fired = {k for k in fired if k.endswith(today)}
        time.sleep(60)


def start():
    if os.environ.get("RUN_SCHEDULER") != "1":
        return False
    threading.Thread(target=_loop, daemon=True, name="closingline-cron").start()
    print("scheduler: started (RUN_SCHEDULER=1)")
    return True
