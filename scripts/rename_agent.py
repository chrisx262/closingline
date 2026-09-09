"""Rename an agent. Only safe while it has no GRADED picks.

Invariant 3 says a bot's graded history is never edited. A name is not a
result, but once a record is public people recognise the board by it, so this
refuses to touch an agent that has already been graded. `closingline_market`
becomes `closingline_open` now, before Tuesday's grading run, because it is
about to be joined by `closingline_close` and the pair have to be tellable
apart.

Usage:  python scripts/rename_agent.py OLD NEW          # dry run
        python scripts/rename_agent.py OLD NEW --apply
"""
import sys

import _proddb  # noqa: F401  (must precede the app import)
from app import SessionLocal, Agent, Pick

if len(sys.argv) < 3:
    sys.exit(__doc__)
old, new = sys.argv[1], sys.argv[2]
apply_it = "--apply" in sys.argv

s = SessionLocal()
a = s.query(Agent).filter(Agent.name == old).first()
if not a:
    s.close()
    sys.exit(f"no agent named {old!r}")
if s.query(Agent).filter(Agent.name == new).first():
    s.close()
    sys.exit(f"{new!r} is already taken")

picks = s.query(Pick).filter(Pick.agent_id == a.id).all()
graded = [p for p in picks if p.result and p.result != "pending"]
print(f"agent {a.id}: {a.name!r} -> {new!r}")
print(f"  picks {len(picks)}, of which graded {len(graded)}")
if graded:
    s.close()
    sys.exit("REFUSING: this agent has graded picks. Renaming a public record "
             "is the sort of thing invariant 3 exists to prevent; register a "
             "new agent instead.")

if not apply_it:
    print("\nDRY RUN — nothing changed. Add --apply.")
    s.close()
else:
    a.name = new
    s.commit()
    print(f"\nrenamed. agent {a.id} is now {a.name!r}")
    s.close()
