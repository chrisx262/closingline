"""Power ratings fitted to the market's own prices, used to fill in the weeks
nobody has posted a line for yet.

WHY THIS EXISTS
The survivor planner has to reason about the whole season at once -- you cannot
decide whether to spend Buffalo in week 3 without knowing what Buffalo is worth
in week 16. But books only post lines a few weeks out, so most of the season has
no price on it. Something has to stand in for those weeks.

WHAT WE FIT TO
Not last season's results. The games that ARE priced this season, which is the
market's current opinion of all 32 teams -- post-draft, post-free-agency,
post-whatever happened in camp. Every team appears several times in the priced
weeks, so the fit is well determined.

THE MODEL, and it is deliberately the simplest thing that works:

    expected home margin = rating[home] - rating[away] + home_field

Each priced game gives one equation, since the market's expected margin is just
the negated home spread. That is 100-ish equations for 33 unknowns, solved by
least squares.

Note there is almost NO shrinkage toward the league average, which is the
opposite of what you do when fitting power ratings the usual way. The usual way
fits to game RESULTS, where a single margin is enormously noisy (an NFL final
margin has a standard deviation of about 13.5 points) and regressing hard is
what keeps a 40-7 result from convincing you a team is unbeatable. We are not
fitting to results. We are fitting to LINES, which are the market's estimate
AFTER it has done that regression itself. Shrinking them again just blurs a
signal that was already clean, and it blurs in a specific and harmful
direction: every projected game drifts toward a coin flip, which for a survivor
tool means systematically understating the best team available. Six-fold
cross-validation against held-out lines says so plainly -- held-out error rises
monotonically from 0.66 points at no shrinkage to 2.36 at the value this file
originally shipped with, while the spread between the best and worst team
collapses from a realistic 13 points to a nonsensical 7.

Solved by coordinate descent because this project has no numpy and does not need
it: each update is the plain-English statement that a team's rating is the
average of (opponent's rating + margin), adjusted for who was at home.

WHAT THIS IS NOT
It is not a forecast that competes with a real line. A market price beats this
every time, which is why callers must replace a prior the moment a genuine line
appears, and why the API tags these `wp_source: "prior"`. It carries no injury,
rest, weather or roster information. Treat the output as "roughly how good is
this team", never as a number to bet into.
"""


# Ridge strength, in units of "games of evidence needed to move a team off
# average". Kept barely above zero: cross-validation on real lines says any real
# shrinkage makes projections worse (see the module docstring). The 0.1 is
# insurance, not regularisation -- it keeps the solve well behaved if a team
# ever turns up with only one or two priced games, which cannot happen today
# (every team has 6-9) but could early in a season.
RIDGE = 0.1

# Fitted home field is clamped to this range. The modern NFL number is ~1.5-2
# points; anything outside this band means the fit is chasing noise in a thin
# slate, so we refuse it rather than propagate it into 200 projected games.
HFA_MIN, HFA_MAX = 0.0, 3.5
HFA_DEFAULT = 1.8

ITERATIONS = 300


def fit(priced_games):
    """Fit team ratings from games that carry a real market spread.

    `priced_games` is an iterable of (home, away, spread_home_line) using this
    project's convention: spread_home_line negative = home favoured.

    Returns (ratings, home_field). `ratings` maps team -> points above an
    average team. A team with no priced game lands at exactly 0.0, i.e. average,
    which is the honest answer when we have been told nothing about it.
    """
    rows = [(h, a, -float(sp)) for h, a, sp in priced_games if sp is not None]
    teams = sorted({t for h, a, _ in rows for t in (h, a)})
    ratings = {t: 0.0 for t in teams}
    if not rows:
        return ratings, HFA_DEFAULT

    # games each team appears in, as (opponent, margin, team_was_home)
    played = {t: [] for t in teams}
    for h, a, margin in rows:
        played[h].append((a, margin, True))
        played[a].append((h, margin, False))

    hfa = HFA_DEFAULT
    for _ in range(ITERATIONS):
        moved = 0.0
        for t in teams:
            games = played[t]
            # A team's rating is the average over its games of what the market
            # implies it is worth: the opponent's rating plus the margin it is
            # expected to win by, with home field taken back out.
            acc = 0.0
            for opp, margin, was_home in games:
                acc += (ratings[opp] + margin - hfa) if was_home else \
                       (ratings[opp] - margin + hfa)
            new = acc / (len(games) + RIDGE)
            moved = max(moved, abs(new - ratings[t]))
            ratings[t] = new

        # Home field is whatever margin is left over once ratings explain the
        # rest. Clamped: a thin or lopsided slate can push this somewhere silly.
        resid = sum(m - (ratings[h] - ratings[a]) for h, a, m in rows)
        hfa = min(HFA_MAX, max(HFA_MIN, resid / len(rows)))

        if moved < 1e-9:
            break

    # Only rating differences are meaningful, so centre them. This makes 0.0
    # read as "league average" rather than an arbitrary offset.
    mean = sum(ratings.values()) / len(ratings)
    for t in ratings:
        ratings[t] -= mean
    return ratings, hfa


def projected_spread(ratings, hfa, home, away):
    """Home spread this fit implies, in the project's sign convention
    (negative = home favoured). None if either team is unknown."""
    if home not in ratings or away not in ratings:
        return None
    return -(ratings[home] - ratings[away] + hfa)


def fit_quality(priced_games, ratings, hfa):
    """Mean absolute error, in points, of the fit against the lines it was fit
    to. Reported so the size of the guess is visible rather than implied.

    This is in-sample and will flatter the fit; the number that matters is the
    held-out one, which is about 0.7 points per game. Both are small because a
    market spread is close to an additive function of team strength by
    construction -- that is WHY this approach works at all."""
    rows = [(h, a, -float(sp)) for h, a, sp in priced_games if sp is not None]
    if not rows:
        return None
    err = sum(abs((ratings[h] - ratings[a] + hfa) - m) for h, a, m in rows)
    return err / len(rows)
