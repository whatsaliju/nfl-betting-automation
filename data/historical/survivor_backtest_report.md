# Survivor Strategy Backtest

- Source: `/Users/lijuv/nfl-betting-automation/data/historical/nfl_market_spine.csv`
- Seasons: 2015-2025
- Candidates: 5788
- Method: Uses historical no-vig moneyline probabilities as pregame win probabilities; grades against actual straight-up winners.

| Strategy | Seasons | Full Survivals | Survival Rate | Avg Survived Weeks | Best Seasons |
|---|---:|---:|---:|---:|---|
| future_path_optimizer | 11 | 0 | 0.0% | 4.18 | none |
| highest_win_prob | 11 | 0 | 0.0% | 4.18 | none |
| survivor_adjusted | 11 | 0 | 0.0% | 3.64 | none |
| avoid_risky | 11 | 0 | 0.0% | 2.82 | none |

| Strategy | Best Single Season | Most Common Loss Week |
|---|---:|---:|
| future_path_optimizer | 10 | 1 |
| highest_win_prob | 12 | 1 |
| survivor_adjusted | 9 | 5 |
| avoid_risky | 8 | 2 |

## Interpretation

- `highest_win_prob` is the pure safety baseline.
- `survivor_adjusted` applies future-value, road, division, low-margin, and low-probability penalties.
- `avoid_risky` is stricter about division games and short favorites.
- `future_path_optimizer` builds the highest full-season path using a beam search over weekly market probabilities.

This is a strategy and plumbing backtest, not a betting-edge proof. It uses market probabilities as the win-probability source so the comparison tests selection policy rather than whether we can beat the market.
