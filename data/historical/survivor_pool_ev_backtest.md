# Survivor Pool EV Backtest

- Source: `/Users/lijuv/nfl-betting-automation/data/historical/nfl_market_spine.csv`
- Seasons: 2015-2025
- Trials per scenario: 30
- Method: Simulates public survivor entries using estimated pick popularity from no-vig moneyline probability, spread size, home field, division status, and brand chalk.

| Strategy | Pool | Sim Entries | Payout | Avg ROI Units | Win/Split Rate | Avg Share | Avg Finish Week |
|---|---:|---:|---|---:|---:|---:|---:|
| leverage | 25 | 24 | top_heavy | 0.395 | 7.6% | 0.0558 | 4.64 |
| leverage | 25 | 24 | winner_take_all | 0.395 | 7.6% | 0.0558 | 4.64 |
| pool_ev_balanced | 25 | 24 | top_heavy | 0.395 | 7.6% | 0.0558 | 4.64 |
| pool_ev_balanced | 25 | 24 | winner_take_all | 0.395 | 7.6% | 0.0558 | 4.64 |
| survivor_adjusted | 25 | 24 | top_heavy | 0.395 | 7.6% | 0.0558 | 4.64 |
| survivor_adjusted | 25 | 24 | winner_take_all | 0.395 | 7.6% | 0.0558 | 4.64 |
| highest_win_prob | 25 | 24 | top_heavy | 0.346 | 9.7% | 0.0538 | 5.18 |
| highest_win_prob | 25 | 24 | winner_take_all | 0.346 | 9.7% | 0.0538 | 5.18 |
| leverage | 500 | 80 | top_heavy | 0.064 | 1.8% | 0.0131 | 5.18 |
| leverage | 500 | 80 | winner_take_all | 0.064 | 1.8% | 0.0131 | 5.18 |
| survivor_adjusted | 500 | 80 | top_heavy | 0.064 | 1.8% | 0.0131 | 4.64 |
| survivor_adjusted | 500 | 80 | winner_take_all | 0.064 | 1.8% | 0.0131 | 4.64 |

## Read

- Positive ROI units means the simulated entry returned more than one buy-in on average within the bounded simulated field.
- Large pool sizes still influence the pick score; `Sim Entries` shows the capped opponent field used for runtime.
- This is a strategy backtest using estimated public pick behavior, not real historical pool-pick data.
- If pool-EV beats highest-win-probability, the site should show a leverage pick next to the safe pick.
