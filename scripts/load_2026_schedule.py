"""Load the full 2026 schedule into prod. Additive: never wipes.

Games with no betting line yet get a schedule row and NO odds snapshot, so an
estimate can never be mistaken for a market price. The survivor planner needs
every week's matchups to reserve teams for the holiday legs.
"""
import _proddb  # noqa: F401  (must precede the app import)
from loaders.nflverse_loader import load

load([2026], wipe=False)
