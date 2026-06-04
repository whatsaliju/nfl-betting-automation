# NFL Selector Model Readiness

Status: **READY_FOR_MONITORING**

Replay and active-policy walk-forward both clear baseline stability checks.

## Replay Summary

| Plays | Wins | Losses | Win Rate | Spread | Total |
| --- | --- | --- | --- | --- | --- |
| 18 | 14 | 4 | 77.8% | 9-3 | 5-1 |

## Walk-Forward

| Policy | Plays | Wins | Losses | Win Rate | Avg Margin |
| --- | --- | --- | --- | --- | --- |
| Active | 14 | 12 | 2 | 85.7% | 7.357 |
| Auto-Optimized | 9 | 6 | 3 | 66.7% | 6.500 |

## Trace Outcomes

| Signal Signature | Plays | Wins | Losses | Win Rate | Avg Margin |
| --- | --- | --- | --- | --- | --- |
| ref_weather_context+sharp | 5 | 4 | 1 | 80.0% | 7.2 |
| sharp+team_rating | 5 | 4 | 1 | 80.0% | 7.8 |
| injury+sharp+team_rating | 4 | 3 | 1 | 75.0% | -1.125 |
| sharp | 3 | 2 | 1 | 66.7% | 0.667 |
| ref_weather_context | 1 | 1 | 0 | 100.0% | 12.5 |

## Pass Profile

| Reason | Passes |
| --- | --- |
| no market cleared threshold | 70 |
| signal classification was LANDMINE | 21 |

## Calibration Notes

| Plays | Wins | Losses | Win Rate | Spread T | Total T | Injury Policy | Total Policy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 9 | 8 | 1 | 88.9% | 4 | 4 | raise_spread_threshold | allow |
| 9 | 8 | 1 | 88.9% | 4 | 4 | raise_spread_threshold | require_ref_weather |
| 8 | 7 | 1 | 87.5% | 5 | 4 | allow | allow |
| 8 | 7 | 1 | 87.5% | 5 | 4 | allow | require_ref_weather |
| 8 | 7 | 1 | 87.5% | 4 | 4 | raise_spread_threshold | require_sharp_and_ref_weather |

Interpretation: use the active policy as the current production candidate; treat auto-optimized policies as research evidence only until more weeks are available.
