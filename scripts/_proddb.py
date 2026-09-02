"""Point the app at the prod Postgres over Railway's public TCP proxy.

Run these under `railway run --service Postgres ...` so the connection URL
arrives in the environment. Nothing here ever puts a credential on a command
line or writes one to disk. Import this BEFORE importing app.
"""
import os
import sys

url = os.environ.get("DATABASE_PUBLIC_URL")
if not url:
    sys.exit("no DATABASE_PUBLIC_URL — run under: "
             "railway run --service Postgres python3 <script>")
os.environ["DATABASE_URL"] = url
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
