"""In-process scheduler — replaces external cron.

Runs inside the (always-on) web service when RUN_SCHEDULER=1 is set, so no
extra Railway cron services or dashboard config are needed. Times are
defined in US Eastern and converted per-tick via zoneinfo, so DST is
handled automatically (the season spans the November change).

Cadence:
  Tue 09:00 ET  weekly_update.py (refresh scores, grade picks)
  Tue 12:00 ET  the week's opening capture
  Sat 12:00 ET  a midweek reference point
  ~80 min before EACH distinct kickoff time — the closing capture

That last one is derived from the schedule rather than pinned to weekdays,
because the NFL calendar will not sit still: week 1 opens on a WEDNESDAY,
Thanksgiving and Christmas add midweek games, and Saturday slates appear late
in the season once college football finishes. Fixed weekday slots missed all of
those. Worse, they mis-measured CLV on the games they did miss: "closing line"
here means the last snapshot taken before kickoff, so under the old fixed slots
a Monday night game was graded against Sunday lunchtime's price, 31 hours stale,
and the Sunday 16:25 games against a price taken before their inactives were
even announced. Eight of week 1's sixteen games had no genuine close.

Budget: one snapshot covers every game and costs 3 Odds API credits (3 markets
x 1 region, verified live). A typical week is now Tue + Sat + about five kickoff
waves (Thu, three on Sunday, Mon) = 7 captures = 21 credits, roughly 92/month
against the free tier's 500. Off-season everything is skipped (no kickoff within
8 days).
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
    ("sat-midweek",   5, 12, 0,  "snapshot"),
]

# Minutes before kickoff for the closing capture. Inactives are published 90
# minutes out, so 80 lands just after them and still comfortably before the
# line is pulled.
PRE_KICK_MIN = 80
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


def due_kickoff_slots(now_et: datetime, fired: set, kickoffs) -> list:
    """Which kickoff waves need their closing capture right now?

    `kickoffs` is the naive-UTC kickoff times of unplayed games, passed in so
    this stays a pure function and can be unit-tested without a database. One
    capture serves every game sharing a kickoff time, so the eight games at
    Sunday 13:00 cost one snapshot between them, not eight.
    """
    now_utc = now_et.replace(tzinfo=ET).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    lo = now_utc + timedelta(minutes=PRE_KICK_MIN)
    hi = lo + timedelta(minutes=GRACE_MIN)
    out = []
    for t in sorted({k for k in kickoffs if lo <= k < hi}):
        # The key must end in today's date: _loop prunes `fired` on that
        # suffix, and a key shaped any other way would be forgotten every
        # tick and re-fire every minute until kickoff.
        key = f"pre-kick-{t:%H%M}:{now_et.date()}"
        if key not in fired:
            out.append((key, "snapshot"))
    return out


def _upcoming_kickoffs():
    from app import SessionLocal, Game
    s = SessionLocal()
    try:
        now = datetime.utcnow()
        return [r[0] for r in s.query(Game.kickoff).filter(
            Game.final == False,  # noqa: E712
            Game.kickoff >= now,
            Game.kickoff <= now + timedelta(days=1),
        ).distinct().all()]
    finally:
        s.close()


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


def _record(job, started, ok, detail):
    """Persist the outcome of a job attempt so /health can see it.

    Deliberately swallows its own errors: health bookkeeping must never be
    the reason a real job fails.
    """
    try:
        from datetime import datetime as _dt
        from app import SessionLocal, JobRun
        s = SessionLocal()
        s.add(JobRun(job=job, started_at=started, finished_at=_dt.utcnow(),
                     ok=ok, detail=(detail or "")[:500]))
        s.commit()
        s.close()
    except Exception as e:
        print(f"scheduler: could not record job run ({e})")


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
        due = due_slots(now_et, fired)
        try:
            due += due_kickoff_slots(now_et, fired, _upcoming_kickoffs())
        except Exception as e:   # a DB hiccup must not stop the fixed slots
            print(f"scheduler: kickoff lookup failed ({e})")
        for key, job in due:
            fired.add(key)
            print(f"scheduler: firing {key} ({job})")
            started = datetime.utcnow()
            try:
                _run(job)
                _record(job, started, True, f"{key} ok")
            except Exception as e:  # log, record and keep the loop alive
                print(f"scheduler: {key} failed: {e}")
                _record(job, started, False, f"{type(e).__name__}: {e}")
        # keep only today's keys so the set can't grow unbounded
        today = str(now_et.date())
        fired = {k for k in fired if k.endswith(today)}
        time.sleep(60)


def start():
    if os.environ.get("RUN_SCHEDULER") != "1":
        return False
    _record("startup", datetime.utcnow(), True, "scheduler thread started")
    threading.Thread(target=_loop, daemon=True, name="closingline-cron").start()
    print("scheduler: started (RUN_SCHEDULER=1)")
    return True
