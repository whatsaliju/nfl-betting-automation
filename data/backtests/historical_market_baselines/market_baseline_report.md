# Historical Market Baseline Backtest

This is the control group for the NFL betting engine. It tests blind market segments from the historical market spine before any WARPS, injury, referee, weather, sharp-split, or selector logic is applied.

## Coverage

- Market spine: `/Users/lijuv/nfl-betting-automation/data/historical/nfl_market_spine.csv`
- Rows: 3028
- Seasons: 2015-2025
- Includes postseason: True

## Takeaway

Blind market buckets are controls, not betting edges. Use them to judge whether WARPS/engine factors add signal beyond baseline market behavior.

## Best Baseline Buckets

| Section | Bucket | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |
|---|---|---:|---:|---:|---:|---:|---:|
| market_side_postseason | spread / HOME | 266 | 142-120-4 | 54.2% | +12.69 | +4.77% | 63.6% |
| total_bucket | UNDER / 40.5_to_44.5 | 1091 | 569-513-9 | 52.6% | +21.11 | +1.94% | 45.5% |
| total_bucket | UNDER / 50_plus | 434 | 222-206-6 | 51.9% | +3.03 | +0.70% | 63.6% |
| market_by_season | moneyline / 2015 | 1068 | 535-533-0 | 50.1% | +5.02 | +0.47% | 100.0% |
| market_side_postseason | total / UNDER | 133 | 68-63-2 | 51.9% | +0.59 | +0.44% | 54.5% |
| total_bucket | OVER / 40_or_less | 352 | 181-169-2 | 51.7% | -0.21 | -0.06% | 27.3% |
| market_side_regular | spread / AWAY | 5784 | 2889-2749-146 | 51.2% | -32.32 | -0.56% | 45.5% |
| market_side | total / UNDER | 3027 | 1535-1464-28 | 51.2% | -21.39 | -0.71% | 54.5% |
| market_side_regular | total / UNDER | 2894 | 1467-1401-26 | 51.1% | -21.98 | -0.76% | 54.5% |
| market_by_season | moneyline / 2021 | 1140 | 568-568-4 | 50.0% | -8.85 | -0.78% | 0.0% |
| market_side | spread / AWAY | 6050 | 3009-2891-150 | 51.0% | -60.42 | -1.00% | 36.4% |
| market_by_season | spread / 2015 | 1068 | 514-514-40 | 50.0% | -20.87 | -1.95% | 0.0% |

## Worst Baseline Buckets

| Section | Bucket | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |
|---|---|---:|---:|---:|---:|---:|---:|
| market_side_postseason | spread / AWAY | 266 | 120-142-4 | 45.8% | -28.10 | -10.57% | 36.4% |
| total_bucket | OVER / 40.5_to_44.5 | 1091 | 513-569-9 | 47.4% | -90.34 | -8.28% | 0.0% |
| market_by_season | moneyline / 2024 | 1140 | 571-569-0 | 50.1% | -91.68 | -8.04% | 0.0% |
| market_side_postseason | moneyline / AWAY | 266 | 98-168-0 | 36.8% | -19.38 | -7.29% | 45.5% |
| market_side_postseason | total / OVER | 133 | 63-68-2 | 48.1% | -9.30 | -6.99% | 45.5% |
| total_bucket | UNDER / 40_or_less | 352 | 169-181-2 | 48.3% | -23.00 | -6.53% | 18.2% |
| total_bucket | OVER / 50_plus | 434 | 206-222-6 | 48.1% | -28.20 | -6.50% | 27.3% |
| market_by_season | moneyline / 2022 | 1136 | 563-565-8 | 49.9% | -62.60 | -5.51% | 0.0% |
| market_side | total / OVER | 3027 | 1464-1535-28 | 48.8% | -164.52 | -5.44% | 18.2% |
| market_side_regular | total / OVER | 2894 | 1401-1467-26 | 48.9% | -155.22 | -5.36% | 18.2% |
| market_side_regular | spread / HOME | 5784 | 2749-2889-146 | 48.8% | -305.00 | -5.27% | 9.1% |
| market_by_season | moneyline / 2025 | 1140 | 567-569-4 | 49.9% | -58.20 | -5.11% | 0.0% |

## Market Side Summary

| Section | Bucket | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |
|---|---|---:|---:|---:|---:|---:|---:|
| market_side | moneyline / AWAY | 6038 | 2709-3309-20 | 45.0% | -159.99 | -2.65% | 36.4% |
| market_side | moneyline / HOME | 6070 | 3323-2727-20 | 54.9% | -297.77 | -4.91% | 9.1% |
| market_side | spread / AWAY | 6050 | 3009-2891-150 | 51.0% | -60.42 | -1.00% | 36.4% |
| market_side | spread / HOME | 6050 | 2891-3009-150 | 49.0% | -292.31 | -4.83% | 0.0% |
| market_side | total / OVER | 3027 | 1464-1535-28 | 48.8% | -164.52 | -5.44% | 18.2% |
| market_side | total / UNDER | 3027 | 1535-1464-28 | 51.2% | -21.39 | -0.71% | 54.5% |

## Promotion Rule

A weekly model factor should only be promoted if it beats these market-only baselines out of sample, after source-health gates and realistic listed odds are applied.

