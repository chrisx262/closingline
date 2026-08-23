# Circa Millions line-value backtest — result: NO demonstrated edge

Run 2026-08-22 over the public Circa contest-sheet archive.

**Sample:** 53 sheets, seasons 2023–2025 (Million V, VI, VII), 646 games
parsed by `loaders/circa_sheet.py` (98.3% confident), joined to nflverse
closing lines and final scores. 0 unmatched.

## The headline that looks good and is not trustworthy

Picking each week's 5 biggest Circa-vs-close divergences graded **54.7% ATS**
(141-117-2) against Circa's own number. Higher thresholds looked better still:
61.4% at ≥2 pts, 70.8% at ≥2.5 pts. Sanity check passed — taking *every* side
of every game graded exactly 50.0% (631-631-30), so the harness is unbiased.

**This result is contaminated by lookahead and must not be used.** It computes
line value against the **closing** line. Picks lock Saturday 4:00pm PT; Sunday
games have not closed. You cannot know that number when you pick. This
violates invariant #3 directly.

Stripped of spin, it rediscovers a known fact: closing lines are efficient and
predict outcomes. If you could see the close you would profit. You cannot.

## Why a clean test is not possible with free data

nflverse `games.csv` carries exactly one spread column (`spread_line` =
closing). No opening line, no intraday. Measuring the *knowable* divergence —
Circa's frozen Thursday line vs the market on Saturday afternoon — needs
historical intraday odds we do not have. The Odds API sells historical
snapshots; that is a paid decision for the owner, not a free one.

## What the data does say, without lookahead

Descriptive statistics on drift (close − Circa), 646 games:

| stat | value |
|---|---|
| mean signed drift | **+0.084 pts** |
| mean absolute drift | 0.62 pts |
| median absolute drift | 0.50 pts |
| games drifting > 1 pt | 11.3% |
| games drifting > 2 pts | 3.7% |

Two things follow.

**Circa's lines are sharp.** A mean signed drift of +0.08 points over three
seasons means they are essentially unbiased against the eventual close. There
is no systematic softness to harvest. This matches Circa's reputation — they
post early and take real limits.

**The divergences are too rare to fill a card even with foresight.** Only 3.7%
of games move more than 2 points. That is roughly 8 games a season in the
bucket that graded well, against a requirement of 5 picks every week (90 a
season). The high-threshold win rates rest on 24–45 plays across three full
seasons and cannot be scaled into a contest entry.

## Conclusion

We cannot demonstrate a tradeable line-value edge in Circa Millions with free
data. The apparent edge is lookahead, and the underlying divergences are small
and rare because Circa prices sharply. Reported per invariant #6: publish
negative results without spin.

## The one honest way forward

Capture the divergence live, going forward:

- snapshot the market **Thu 13:05 ET** (as Circa's line freezes)
- snapshot again **Sat 18:45 ET** (just before picks lock)
- store Circa's sheet each Thursday

That measures the *knowable* Thursday→Saturday move — the only version of this
signal a picker could actually act on. Cost is ~26 Odds API credits/month on
top of the current ~66 of 500. After 4–6 weeks there is a real sample.

## Cost of buying the answer instead

`loaders/circa_historical.py` is ready to run. Verified 2026-08-22:

- The Odds API historical endpoint is **paid-only** on any plan above free
  (confirmed by probe: `HISTORICAL_UNAVAILABLE_ON_FREE_USAGE_PLAN`, HTTP 401,
  which costs 0 credits — the probe is free to run).
- Historical costs 10 credits per region per market vs 1 live; one call
  returns every game at that timestamp.
- 3 seasons x 18 weeks x 2 timestamps (Thu freeze + Sat lock) = 108 calls.
  At 1 market that is 1,080 credits; at 3 markets, 3,240.
- The 20K plan is **$30/month** = 20,000 credits. The full pull uses 16% of a
  single month. It is a one-time historical pull: subscribe, run, cancel.
- Ongoing live capture stays FREE — current-odds calls are 3 credits, so the
  two extra weekly snapshots are ~26/month against the free tier's 500.

Run `python loaders/circa_historical.py probe` FIRST after subscribing. It
spends one call to confirm the archive returns real data for an old timestamp
before committing to the full pull. Coverage for 2023-2025 is documented
(5-minute snapshots from Sept 2022) but UNVERIFIED — the free tier is rejected
before any data is returned, so it could not be checked without paying.

Expectation management: given Circa's mean signed drift versus the close is
+0.084 pts, the knowable Thu->Sat portion is likely SMALLER than the total
drift already measured. The $30 most likely buys a firm negative rather than
an edge. Worth it to know definitively; not worth it as a hope.

Until that exists, **no Circa Millions pick tool should claim an edge**, and
nothing here should inform the owner's decision about buying into an entry.
The only established edge in this contest remains the structural overlay
(~+3–5% EV/entry, from Circa covering a $6M guarantee the field has not filled
in two years) — which is unrelated to picking skill.
