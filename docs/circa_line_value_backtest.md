# Circa Millions line-value backtest — FINAL: no edge, and not provable

Run 2026-08-22. Superseded the earlier free-data attempt; this version is
lookahead-free and used paid historical odds.

## Method

- **Circa lines:** 53 public contest sheets, 2023–2025, 646 games parsed by
  `loaders/circa_sheet.py` (98.3% confident).
- **Market at pick time:** The Odds API historical snapshots at the Saturday
  6:45pm ET lock — the last number a picker can actually see. 132 snapshots
  pulled by `loaders/circa_historical.py`, 1,320 credits.
- **Grading:** ATS against *Circa's own line*, which is what the contest scores.
- 590 games had both a Circa line and a Saturday market price.

The earlier version compared Circa to the **closing** line. That was lookahead
— picks lock Saturday, Sunday games have not closed — and it inflated the
result to 54.7%. This version only uses information available at pick time.

## Result: nothing is statistically significant

| bucket | W-L | win% | 95% CI | p vs 52.4% |
|---|---|---|---|---|
| top-5/wk (contest format) | 137-118 | 53.7% | [47.6, 59.8] | 0.359 |
| top-5/wk, confident parses | 137-116 | 54.2% | [48.0, 60.3] | 0.311 |
| value ≥ 0.5 pts | 154-156 | 49.7% | [44.1, 55.2] | 0.845 |
| value ≥ 1.0 pts | 60-42 | 58.8% | [49.3, 68.4] | 0.115 |
| value ≥ 1.5 pts | 27-19 | 58.7% | [44.5, 72.9] | 0.240 |
| value ≥ 2.0 pts | 16-13 | 55.2% | [37.1, 73.3] | 0.456 |
| value ≥ 2.5 pts | 14-10 | 58.3% | [38.6, 78.1] | 0.354 |

**Every p-value is above 0.05.** Every confidence interval contains 50%. The
headline 53.7% is indistinguishable from a coin flip.

Sanity check passed: taking every side of every game graded exactly 50.0%
(577-577-26), so the harness is unbiased.

Note the ≥0.5 bucket grades 49.7% — *below* break-even — which breaks any
tidy "more divergence, more edge" story. The higher buckets look better but
rest on 24–102 plays.

## Why this can never be settled

Proving a 53.7% edge at p<0.05 needs **~12,610 picks — about 140 seasons** of
a five-pick-per-week contest.

Even if the effect is real, it is too small to verify inside a human lifetime
of playing this contest, and far too small to overcome variance in any single
season. That is a stronger negative than "we didn't find anything": the
question is not answerable at the sample sizes this contest produces.

## What the divergence actually looks like

| moment | mean \|Circa − market\| | median |
|---|---|---|
| Thursday, as the line freezes | 0.39 pts | **0.00 pts** |
| Saturday, at pick lock | 0.57 pts | 0.50 pts |

Circa's contest line *is* the market at the moment it's posted — median
difference of exactly zero. Over the next ~54 hours the market drifts about
half a point away. That drift is real and knowable, but half a point is not
enough to beat the spread reliably, and the data above shows it doesn't.

## Conclusion

**Do not build a Circa Millions pick tool, and do not let one influence a
real entry.** There is no demonstrated edge in line value, and the sample
sizes this contest generates can never demonstrate one.

The only established edge remains the structural **overlay** — Circa covering
a $6M guarantee the field has not filled in two years, worth roughly +3–5% EV
per entry — which has nothing to do with picking skill and requires no model.

Reported per invariant #6: negative results published without spin.

## Cost accounting

$30 for one month of the 20K plan. 1,330 of 20,000 credits used (10 probe +
1,320 pull). **Cancel the subscription** — this was a one-time pull and
nothing ongoing needs the paid tier. Next invoice would be Sep 22, 2026.
The raw snapshots are kept in `/tmp/circa_hist/` (10MB); move them somewhere
permanent if the question should ever be revisited without paying again.
