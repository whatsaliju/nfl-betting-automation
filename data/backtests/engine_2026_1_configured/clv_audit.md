# Closing Line Value Audit

This report compares selected engine bets against the historical market spine close/reference line.

## Verdict

- Status: BUILDING_SAMPLE
- Recommendation: Track CLV, but do not promote price gates until the selected-bet sample is larger.
- Selected bets: 18
- Avg CLV: 0.0278
- Beat-close rate: 0.5714

## Buckets

| Section | Bucket | Plays | W-L-P | Avg CLV | Beat Close |
|---|---|---:|---:|---:|---:|
| market | spread | 12 | 9-3-0 | 0.0 | 0.6 |
| market | total | 6 | 5-1-0 | 0.0833 | 0.5 |
| clv_direction | beat_close | 4 | 3-1-0 | 0.875 | 1.0 |
| clv_direction | lost_to_close | 3 | 1-2-0 | -1.0 | 0.0 |
| clv_direction | push_close | 11 | 10-1-0 | 0.0 | None |
| warps_spread_pick_alignment | aligned | 5 | 4-1-0 | 0.1 | 0.6667 |
| warps_spread_pick_alignment | conflict | 7 | 5-2-0 | -0.0714 | 0.5 |
| warps_spread_pick_alignment | non_spread_pick | 6 | 5-1-0 | 0.0833 | 0.5 |
| value_gap_pick_alignment | aligned | 8 | 7-1-0 | 0.0 | 0.6667 |
| value_gap_pick_alignment | conflict | 4 | 2-2-0 | 0.0 | 0.5 |
| value_gap_pick_alignment | non_side_pick | 6 | 5-1-0 | 0.0833 | 0.5 |

## Notes

- Spread CLV is measured from the selected side perspective.
- Total CLV is positive when an over has a lower picked line than close or an under has a higher picked line than close.
- Moneyline CLV is measured as closing implied probability minus picked implied probability.