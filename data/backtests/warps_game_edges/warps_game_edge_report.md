# WARPS Game Edge Backtest

This audit tests preseason WARPS team-strength priors against historical game markets.
It does not include the weekly engine's injury, referee, weather, sharp-split, or line-movement layers.

## Headline

WARPS game priors are useful as a baseline, but they should not be treated as standalone spread or moneyline picks.
The strongest spread thresholds get close to break-even before vig, while moneyline edges are materially negative in this broad historical sweep.

## Model Setup

- Rows joined: 3028
- Home-field value: 1.6 projected wins
- Win-gap logit scale: 0.15
- Margin standard deviation: 13.45
- Fair spread method: WARPS projected win gap -> win probability -> normal-margin spread
- Market edge method: model spread/probability compared to historical no-vig market line/probability
- Realized units: listed American odds from the market spine

## Threshold Summary

| Market | Threshold Type | Threshold | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| spread | edge_points | 0.5 | 2758 | 1374-1311-73 | 51.2% | -29.67 | -1.08% | 36.4% |
| spread | edge_points | 1.0 | 2499 | 1248-1192-59 | 51.1% | -29.53 | -1.18% | 36.4% |
| spread | edge_points | 1.5 | 2274 | 1129-1089-56 | 50.9% | -39.38 | -1.73% | 36.4% |
| spread | edge_points | 2.0 | 2035 | 1008-976-51 | 50.8% | -39.32 | -1.93% | 36.4% |
| spread | edge_points | 2.5 | 1839 | 909-883-47 | 50.7% | -38.53 | -2.09% | 36.4% |
| spread | edge_points | 3.0 | 1619 | 809-771-39 | 51.2% | -20.35 | -1.26% | 36.4% |
| spread | edge_points | 3.5 | 1423 | 717-676-30 | 51.5% | -10.84 | -0.76% | 27.3% |
| spread | edge_points | 4.0 | 1230 | 621-585-24 | 51.5% | -9.74 | -0.79% | 27.3% |
| moneyline | edge_prob | 0.01 | 2875 | 1003-1863-9 | 35.0% | -130.40 | -4.54% | 27.3% |
| moneyline | edge_prob | 0.02 | 2741 | 947-1786-8 | 34.6% | -114.92 | -4.19% | 36.4% |
| moneyline | edge_prob | 0.03 | 2570 | 868-1695-7 | 33.9% | -117.54 | -4.57% | 36.4% |
| moneyline | edge_prob | 0.04 | 2429 | 805-1618-6 | 33.2% | -119.13 | -4.90% | 27.3% |
| moneyline | edge_prob | 0.05 | 2305 | 764-1538-3 | 33.2% | -96.03 | -4.17% | 27.3% |
| moneyline | edge_prob | 0.06 | 2149 | 686-1460-3 | 32.0% | -123.11 | -5.73% | 27.3% |
| moneyline | edge_prob | 0.08 | 1875 | 572-1301-2 | 30.5% | -118.60 | -6.33% | 27.3% |
| moneyline | edge_prob | 0.1 | 1610 | 468-1140-2 | 29.1% | -121.68 | -7.56% | 36.4% |
| moneyline | ev | 0.02 | 2690 | 915-1767-8 | 34.1% | -118.10 | -4.39% | 36.4% |
| moneyline | ev | 0.05 | 2505 | 829-1669-7 | 33.2% | -116.12 | -4.64% | 45.5% |
| moneyline | ev | 0.08 | 2325 | 750-1570-5 | 32.3% | -107.46 | -4.62% | 27.3% |
| moneyline | ev | 0.1 | 2207 | 695-1509-3 | 31.5% | -110.17 | -4.99% | 27.3% |
| moneyline | ev | 0.15 | 1954 | 588-1363-3 | 30.1% | -103.45 | -5.29% | 27.3% |
| moneyline | ev | 0.2 | 1748 | 499-1247-2 | 28.6% | -115.90 | -6.63% | 27.3% |

## Interpretation

- Spread: the best broad threshold was around 3.5-4.0 points of model-vs-market edge, but it still finished slightly negative after vig.
- Moneyline: broad WARPS probability edges did not clear market pricing. Treat moneyline as a weekly-engine research overlay until confirmed by richer signals.
- Practical use: show WARPS spread/ML as a fair-line prior on the site, then require weekly confirmations before promoting anything to an actionable edge.

## Next Gate

Join this prior to the weekly engine factors and test whether spreads/ML improve when WARPS agrees with injuries, market movement, referee context, and source-health gates.
