# WARPS Betting Stability Audit

This audit stress-tests the historical betting gates used by the 2026 betting card.

## Gate Stability

| Gate | Bets | Units | ROI | Profitable Seasons | Best Removed ROI | Worst Season | Flags |
|---|---:|---:|---:|---:|---:|---|---|
| WARPS v2.3 Over gate | 60 | +2.00 | +3.45% | 44.4% | -0.98% | 2003 (-2.00) | best-season dependent, weak season breadth |
| WARPS v2.3 Under gate | 162 | +2.54 | +1.61% | 50.0% | -0.84% | 2020 (-6.95) | best-season dependent, thin ROI |
| WARPS v2.3 All-side gate | 263 | +2.62 | +1.02% | 55.6% | -2.21% | 2020 (-9.15) | best-season dependent, thin ROI |

## 2026 Card Fragility

| Team | Bet | Tier | Hist ROI | ROI w/o Best | Flags |
|---|---:|---|---:|---:|---|
| ARI | Over 4.5 150 | core | +3.45% | -0.98% | best-season dependent; sub-50% season hit-rate |
| CIN | Under 9.5 130 | core | +1.61% | -0.84% | best-season dependent |
| MIA | Over 4.5 110 | core | +3.45% | -0.98% | best-season dependent; sub-50% season hit-rate |
| DAL | Under 9.5 -125 | core | +1.61% | -0.84% | best-season dependent |
| IND | Over 7.5 -125 | core | +3.45% | -0.98% | best-season dependent; sub-50% season hit-rate |
| LAC | Under 10.5 -145 | core | +1.61% | -0.84% | best-season dependent |
| BAL | Under 11.5 -140 | core | +1.61% | -0.84% | best-season dependent |
| HOU | Over 9.5 -125 | standard | +3.45% | -0.98% | best-season dependent; sub-50% season hit-rate |
| JAX | Over 9.5 120 | small | +3.45% | -0.98% | best-season dependent; sub-50% season hit-rate; thin forecast edge |
| WAS | Under 7.5 110 | small | +1.61% | -0.84% | best-season dependent; thin forecast edge |
| CHI | Under 9.5 -125 | small | +1.61% | -0.84% | best-season dependent; thin price edge |
| GB | Under 10.5 -175 | small | +1.61% | -0.84% | best-season dependent; thin price edge |
| NYJ | Under 5.5 -110 | small | +1.61% | -0.84% | best-season dependent; thin forecast edge; thin price edge |
| SF | Under 10.5 -125 | small | +1.61% | -0.84% | best-season dependent; thin forecast edge; thin price edge |
| KC | Under 10.5 -145 | small | +1.61% | -0.84% | best-season dependent; thin price edge |
| TEN | Under 6.5 -115 | small | +1.61% | -0.84% | best-season dependent; thin forecast edge; thin price edge |
