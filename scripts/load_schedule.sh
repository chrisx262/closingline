#!/bin/bash
# Load the full 2026 schedule into the prod database.
# Additive only: adds missing schedule rows, writes no odds, deletes nothing.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
PYTHONPATH=scripts railway run --service Postgres python3 scripts/load_2026_schedule.py
