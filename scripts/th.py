import _proddb  # noqa: F401
from datetime import datetime
from app import SessionLocal, Game, Pick, Agent, JobRun
s=SessionLocal()
print('recent jobs:')
for r in s.query(JobRun).order_by(JobRun.started_at.desc()).limit(5).all():
    print(f"  {r.started_at:%b %d %H:%M} UTC  {r.job:<12} ok={r.ok}  {r.detail[:40]}")
g=s.query(Game).filter(Game.id=='2026_W01_SF_LA').first()
print(f"\nThursday game: {g.away} @ {g.home}, kickoff {g.kickoff} UTC")
for p,a in (s.query(Pick,Agent).join(Agent,Agent.id==Pick.agent_id)
              .filter(Pick.game_id==g.id).order_by(Pick.submitted_at).all()):
    print(f"  {a.name:<20} {p.side} at {p.snap_odds:+}  submitted {p.submitted_at:%b %d %H:%M} UTC  {p.result}")
s.close()
