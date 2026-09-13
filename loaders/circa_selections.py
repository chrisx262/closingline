"""Circa Survivor weekly selections — the real field, straight from Circa.

WHY THIS MATTERS
The survivor tool was built with no pick-popularity input at all, on the
reasoning that Circa's field is a self-selected $1,000-a-head crowd that looks
nothing like a public Yahoo or ESPN pool, and that borrowing public numbers
would mislead rather than inform. That reasoning still holds. The premise that
Circa's own numbers could not be obtained does not: after Saturday's lock Circa
publishes a PDF listing every entry and its pick, and links it from @CircaSports.

    https://www.circasports.com/wp-content/uploads/YYYY/MM/
        Circa-Survivor-YYYY-Week-N-Selections.pdf

Note the two different documents. "Selections" appears after the lock and says
what was picked. "Team Availability" appears after the week resolves and says
what each surviving entry has left. This loader reads the first.

PARSE NOTES, both learned the hard way
  - Rows look like "ENTRY NAME-3 22. CHARGERS PK", three to a line.
  - A team nickname can START WITH A DIGIT (49ERS). A pattern requiring a
    leading letter silently drops ten entries and nobody notices.
  - Entry names can also start with digits ("2 WEEKS OF SWEAT-1"), so the team
    must be matched as a single word and not a greedy run that can swallow the
    name in front of it.
  - Circa's own summary GRAPHIC is not reliable: the Week 1 image omitted the
    Ravens (111) and Broncos (7) entirely, because 29 teams plus a NO PICK row
    fit their three-by-ten layout and 31 did not. The PDF is authoritative and
    the arithmetic proves it -- the graphic's own live-entry figure only
    balances if the missing 118 are counted.

NO PICK is stored as a team named NO_PICK. Those entries paid and were
eliminated without playing, which is worth seeing rather than dropping.
"""

import os
import re
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

URL = ("https://www.circasports.com/wp-content/uploads/{yy}/{mm}/"
       "Circa-Survivor-{season}-Week-{week}-Selections.pdf")

# Circa prints nicknames; the rest of the platform uses nflverse abbreviations.
NICK = {
    "CARDINALS": "ARI", "FALCONS": "ATL", "RAVENS": "BAL", "BILLS": "BUF",
    "PANTHERS": "CAR", "BEARS": "CHI", "BENGALS": "CIN", "BROWNS": "CLE",
    "COWBOYS": "DAL", "BRONCOS": "DEN", "LIONS": "DET", "PACKERS": "GB",
    "TEXANS": "HOU", "COLTS": "IND", "JAGUARS": "JAX", "CHIEFS": "KC",
    "RAMS": "LA", "CHARGERS": "LAC", "RAIDERS": "LV", "DOLPHINS": "MIA",
    "VIKINGS": "MIN", "PATRIOTS": "NE", "SAINTS": "NO", "GIANTS": "NYG",
    "JETS": "NYJ", "EAGLES": "PHI", "STEELERS": "PIT", "SEAHAWKS": "SEA",
    "49ERS": "SF", "BUCS": "TB", "BUCCANEERS": "TB", "TITANS": "TEN",
    "COMMANDERS": "WAS", "WASHINGTON": "WAS",
}


def pdf_url(season: int, week: int, month: int = None) -> str:
    """Circa files under the upload month, which is the month the week is played
    in rather than anything derivable from the week number alone."""
    mm = month or {1: 9, 2: 9, 3: 9, 4: 10, 5: 10, 6: 10, 7: 10, 8: 10,
                   9: 11, 10: 11, 11: 11, 12: 11, 13: 12, 14: 12, 15: 12,
                   16: 12, 17: 12, 18: 1}.get(week, 9)
    yy = season + 1 if mm == 1 else season
    return URL.format(yy=yy, mm=f"{mm:02d}", season=season, week=week)


def fetch(season: int, week: int, month: int = None) -> bytes:
    for m in ([month] if month else [None, 9, 10, 11, 12, 1]):
        u = pdf_url(season, week, m)
        r = requests.get(u, timeout=120)
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            print(f"fetched {u} ({len(r.content)//1024} KB)")
            return r.content
    raise SystemExit(f"no Selections PDF found for {season} week {week}")


def parse(data: bytes):
    """(counts, selections_parsed, pk_markers). counts maps abbreviation ->
    entries, plus NO_PICK when Circa reports any."""
    from pypdf import PdfReader
    import io
    import warnings
    warnings.filterwarnings("ignore")

    reader = PdfReader(io.BytesIO(data))
    counts, n, markers = {}, 0, 0
    unknown = set()
    for page in reader.pages:
        text = page.extract_text() or ""
        markers += text.count(" PK")
        # "<team number>. <NICKNAME> PK" — nicknames are a single token, which
        # is what stops the pattern swallowing the entry name before it.
        for m in re.finditer(r"\d{1,2}\.\s*([A-Z0-9]+)\s+PK", text):
            nick = m.group(1)
            abbr = NICK.get(nick)
            if not abbr:
                unknown.add(nick)
                continue
            counts[abbr] = counts.get(abbr, 0) + 1
            n += 1
        for m in re.finditer(r"NO\s+PICK\s+(\d[\d,]*)", text, re.I):
            counts["NO_PICK"] = int(m.group(1).replace(",", ""))
    if unknown:
        # Loudly, because a nickname we do not know is a team silently missing
        # from the whole distribution -- exactly how the 49ers vanished once.
        print(f"WARNING: unrecognised nicknames {sorted(unknown)} — these picks "
              f"are NOT counted. Add them to NICK.")
    return counts, n, markers


def store(season: int, week: int, counts: dict):
    from app import SessionLocal, CircaSelection, Base, engine
    Base.metadata.create_all(engine)
    s = SessionLocal()
    now = datetime.utcnow()
    wrote = 0
    for team, entries in counts.items():
        row = (s.query(CircaSelection)
                 .filter_by(season=season, week=week, team=team).first())
        if row:
            row.entries, row.captured_at = entries, now
        else:
            s.add(CircaSelection(season=season, week=week, team=team,
                                 entries=entries, captured_at=now))
        wrote += 1
    s.commit()
    s.close()
    return wrote


def run(season: int, week: int, month: int = None, no_pick: int = None):
    counts, n, markers = parse(fetch(season, week, month))
    if no_pick is not None:
        counts["NO_PICK"] = no_pick
    total = sum(counts.values())
    print(f"week {week}: {n:,} selections parsed of {markers:,} markers, "
          f"{len(counts)} teams, {total:,} entries")
    if markers and n < markers - 1:
        print(f"WARNING: {markers - n} selections went unparsed — do not trust "
              f"this distribution until that is explained.")
    print(f"stored {store(season, week, counts)} rows")
    return counts


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit("usage: python loaders/circa_selections.py SEASON WEEK "
                 "[--month M] [--no-pick N]")
    month = int(a[a.index("--month") + 1]) if "--month" in a else None
    npk = int(a[a.index("--no-pick") + 1]) if "--no-pick" in a else None
    run(int(a[0]), int(a[1]), month, npk)
