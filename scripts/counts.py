"""Print prod row counts. Read-only."""
import _proddb  # noqa: F401  (must precede app import)
from app import SessionLocal, Game, OddsSnapshot, Agent, Pick

s = SessionLocal()
print("  2026 games :", s.query(Game).filter(Game.season == 2026).count())
print("  2025 games :", s.query(Game).filter(Game.season == 2025).count())
print("  snapshots  :", s.query(OddsSnapshot).count())
print("  agents     :", s.query(Agent).count())
print("  picks      :", s.query(Pick).count())
s.close()
