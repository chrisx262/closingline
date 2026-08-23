"""Circa Million contest line sheet -> structured games.

WHY THIS IS OCR AND NOT A PARSER
--------------------------------
Circa publishes the weekly contest point spreads as a PDF at a public URL
(no login). Those PDFs contain NO text layer at all: zero fonts, zero text
operators, ~15k vector path operations. The team names and numbers are drawn
as vector OUTLINES. No PDF library can ever extract them. Rendering + OCR is
the only route. Verified 2026-08-22 against Million VI weeks 1/3/9/12/14.

WHAT IS RELIABLE AND WHAT IS NOT
--------------------------------
reliable   : team names, the integer part of each spread, and Circa's own
             1-32 contestant numbers (each game is a consecutive odd/even
             pair -- this is the pairing key; never pair by matching values)
UNRELIABLE : the half-point. Circa renders it as a true U+00BD glyph that is
             taller than the digits and sits below the baseline. Tesseract
             emits '%', ')', '?', ';' or merges it into a digit ("3.5"->"37"),
             and sometimes drops it. NEVER trust OCR alone for the half point.

So every game goes through validate(): the two mirrored rows must have
opposite signs and the same integer part. Anything that fails is FLAGGED for
human confirmation rather than guessed. Empirically ~75-90% of a sheet parses
clean; the remainder is a handful of cells to eyeball. A wrong half-point
would silently corrupt line-value rankings, which is worse than no tool.
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

CONTEST_PAGE = "https://www.circasports.com/circa-million"

# glyphs tesseract emits in place of the half-point symbol
HALF_MARKS = set("%)?;,'’|}]!*½/")

CANON = ("RAVENS CHIEFS PACKERS EAGLES JAGUARS DOLPHINS STEELERS FALCONS VIKINGS "
         "GIANTS PANTHERS SAINTS PATRIOTS BENGALS TITANS BEARS CARDINALS BILLS "
         "TEXANS COLTS RAIDERS CHARGERS COMMANDERS BUCS BRONCOS SEAHAWKS COWBOYS "
         "BROWNS RAMS LIONS JETS 49ERS").split()

ALIAS = {"AOERS": "49ERS", "A9ERS": "49ERS", "4SERS": "49ERS", "AQERS": "49ERS",
         "NINERS": "49ERS", "PAVENS": "RAVENS", "BUCCANEERS": "BUCS"}


@dataclass
class SheetGame:
    slot: int                 # Circa's odd contestant number for the pair
    favorite: str
    underdog: str
    line: float               # positive points the favorite gives
    confident: bool           # False => needs human confirmation


def canon_team(token: str) -> Optional[str]:
    t = re.sub(r"[^A-Z0-9]", "", token.upper())
    if t in ALIAS:
        return ALIAS[t]
    if t in CANON:
        return t
    for c in CANON:                       # tolerate 1-2 char OCR slips
        if len(t) >= 5 and sum(1 for a, b in zip(t, c) if a == b) >= len(c) - 2:
            return c
    return None


def render(pdf_path: str, dpi: int = 400) -> str:
    """PDF -> PNG. Vector art, so it stays crisp at any dpi."""
    # realpath matters: leptonica (tesseract's image layer) will NOT follow a
    # symlinked directory, and on macOS /tmp -> /private/tmp. Passing "/tmp/x.png"
    # fails with "image file not found" even though the file plainly exists.
    pdf_path = os.path.realpath(pdf_path)
    out = pdf_path.rsplit(".", 1)[0] + "_render"
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile",
                    pdf_path, out], check=True, capture_output=True)
    return os.path.realpath(out + ".png")


def _tsv(png: str):
    """Return (page_width, words). Width comes from tesseract's level-1 page
    row, so this module needs no image library at all."""
    tsv = subprocess.run(["tesseract", png, "stdout", "--psm", "6", "tsv"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, errors="replace").stdout
    page_w, words = 0, []
    for r in csv.DictReader(io.StringIO(tsv), delimiter="\t",
                            quoting=csv.QUOTE_NONE):
        try:
            if int(r["level"]) == 1:
                page_w = max(page_w, int(r["width"]))
                continue
        except (ValueError, TypeError, KeyError):
            continue
        text = (r.get("text") or "").strip()
        if not text:
            continue
        try:
            words.append((int(r["left"]), int(r["top"]), int(r["width"]),
                          int(r["height"]), text))
        except (ValueError, TypeError, KeyError):
            continue
    return page_w, words


def read_slots(png: str) -> dict:
    """OCR -> {contestant_number: (team, sign, int_part, saw_half)}.

    The sheet is two columns; split on x before grouping rows by y, otherwise
    psm 6 reads straight across and merges unrelated games onto one line.
    """
    width, words = _tsv(png)
    if not width:
        width = max((w[0] + w[2] for w in words), default=2) 
    mid = width / 2
    slots: dict = {}

    for left_col in (True, False):
        col = [w for w in words if (w[0] < mid) is left_col]
        rows: dict = {}
        for x, y, w, h, t in col:
            key = next((k for k in rows if abs(k - y) <= 40), None)
            if key is None:
                key = y
                rows[key] = []
            rows[key].append((x, t))

        for y in sorted(rows):
            toks = [t for _, t in sorted(rows[y])]
            for i, tok in enumerate(toks):
                team = canon_team(tok)
                if not team:
                    continue
                num = next((int(toks[b]) for b in range(i - 1, -1, -1)
                            if re.fullmatch(r"\d{1,2}", toks[b])), None)
                spread = None
                for f in range(i + 1, len(toks)):
                    m = re.match(r"([+-])\s?(\d{1,2})([^\d\s]{0,2})$", toks[f])
                    if m:
                        spread = (m.group(1), int(m.group(2)),
                                  any(c in HALF_MARKS for c in m.group(3)))
                        break
                if num and 1 <= num <= 32 and spread:
                    slots[num] = (team,) + spread
                break
    return slots


def validate(slots: dict) -> tuple[list, list]:
    """Pair by Circa's consecutive odd/even numbering and cross-check.

    Returns (games, problems). A game is `confident` only when both mirrored
    rows agreed about the half-point. Everything else is surfaced, never
    silently resolved.
    """
    games, problems = [], []
    for lo in range(1, 32, 2):
        a, b = slots.get(lo), slots.get(lo + 1)
        if not a and not b:
            continue                       # bye weeks legitimately skip slots
        if not a or not b:
            problems.append((lo, "only one side of the pair was read"))
            continue
        if a[1] == b[1]:
            problems.append((lo, f"both sides same sign ({a[0]}/{b[0]})"))
            continue
        if a[2] != b[2]:
            problems.append((lo, f"integer mismatch {a[2]} vs {b[2]} "
                                 f"({a[0]}/{b[0]})"))
            continue
        saw_half = a[3] or b[3]
        line = a[2] + (0.5 if saw_half else 0.0)
        fav, dog = (a[0], b[0]) if a[1] == "-" else (b[0], a[0])
        games.append(SheetGame(lo, fav, dog, line, confident=(a[3] == b[3])))
    return games, problems


def parse_pdf(pdf_path: str) -> tuple[list, list]:
    return validate(read_slots(render(pdf_path)))


# ---------------------------------------------------------------- fetching
# Circa's uploads live under /wp-content/uploads/YYYY/MM/. The month is the
# month the sheet was POSTED, which for an NFL week is the Thursday before
# kickoff -- so a week can land in either of two months. We try the plausible
# ones rather than guessing a single mapping.
ROMAN = {2019: "I", 2020: "II", 2021: "III", 2022: "IV", 2023: "V",
         2024: "VI", 2025: "VII", 2026: "VIII"}

SHEET_URL = ("https://www.circasports.com/wp-content/uploads/"
             "{year}/{month:02d}/Circa-Sports-Million-{roman}-"
             "Contest-Point-Spreads-Week-{week}.pdf")


def candidate_urls(season: int, week: int):
    """Plausible URLs for one week's sheet, most likely first."""
    roman = ROMAN.get(season)
    if not roman:
        return []
    # NFL week -> (calendar year, month) the sheet was most likely posted in
    if week <= 4:
        guesses = [(season, 9), (season, 10)]
    elif week <= 8:
        guesses = [(season, 10), (season, 9), (season, 11)]
    elif week <= 13:
        guesses = [(season, 11), (season, 10), (season, 12)]
    elif week <= 17:
        guesses = [(season, 12), (season, 11), (season + 1, 1)]
    else:
        guesses = [(season + 1, 1), (season, 12)]
    return [SHEET_URL.format(year=y, month=m, roman=roman, week=week)
            for y, m in guesses]


def fetch_sheet(season: int, week: int, dest_dir: str = "/tmp/circa") -> Optional[str]:
    """Download one week's sheet. Returns the local path, or None if absent.

    Uses only the public uploads directory -- no login, no scraping of a
    contestant area.
    """
    # requests, not urllib: urllib uses the system trust store, which on macOS
    # has no CA bundle for this interpreter and fails every https call with
    # CERTIFICATE_VERIFY_FAILED. requests ships certifi and just works.
    import requests

    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"million_{season}_wk{week:02d}.pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        return dest

    for url in candidate_urls(season, week):
        try:
            r = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (ClosingLine backtest)"})
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                continue
            with open(dest, "wb") as fh:
                fh.write(r.content)
            return dest
        except requests.RequestException:
            continue
    return None
