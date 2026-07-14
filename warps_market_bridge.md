# WARPS Market Bridge

WARPS has two separate jobs:

1. Season futures: price team win-total Over/Under markets.
2. Weekly game priors: provide team-strength baselines for spreads and moneylines.

The season futures card should not be treated as a spread or moneyline selector. A 10-win team can still be a bad weekly spread bet if the market line already prices that strength correctly.

## Season Win Totals

Inputs:
- WARPS v2.3 projected wins
- sportsbook season win total
- Over/Under moneyline price
- Monte Carlo residual distribution
- historical betting gate stability

Output:
- Over/Under bet, watch, or pass
- model probability vs no-vig market probability
- stake tier and fragility flags

Primary files:
- `warps_2026_betting_card.csv`
- `warps_betting_stability_report.md`

## Weekly Spreads

WARPS can become a spread prior by converting projected team-strength gaps into win probability, then translating win probability into a fair point spread.

Current prior formula:

```text
home_win_prob = logistic((home_warps - away_warps + home_field_wins) * 0.15)
fair_home_spread = -NormalInv(home_win_prob) * NFL_MARGIN_SD
```

This produces a fair spread baseline, not a bet. The weekly engine should compare:

```text
book_home_spread vs warps_fair_home_spread
```

Then require confirmation from sharp flow, injuries, referee context, weather, rest/travel, and source quality before promoting a spread play.

Primary file:
- `warps_2026_game_priors.csv`

## Weekly Moneylines

The same game prior gives fair home and away moneylines from the WARPS win probability.

The weekly moneyline process should compare:

```text
book_implied_probability_no_vig vs WARPS game win probability
```

Moneyline is currently research-only in the engine because the graded sample is thin. It should remain a pricing audit until more full-season evidence exists.

Primary files:
- `warps_2026_game_priors.csv`
- `data/backtests/engine_2026_1_configured/moneyline_pricing_audit.csv`

## Current Policy

- Season futures: WARPS may output Over/Under recommendations.
- Weekly spreads: WARPS should be a prior/overlay, not the sole selector.
- Weekly moneylines: WARPS should be a fair-price comparator until sample size improves.
- Totals: WARPS has no direct total model; totals remain driven by weekly context, referee trends, weather, pace/injuries, and sharp flow.
