# Feature Policy Simulation

These simulations are research-only overlays on already graded engine picks.

| Policy | Plays | W-L | Win Rate | Removed W-L | Delta |
|---|---:|---:|---:|---:|---:|
| baseline | 18 | 14-4 | 0.7778 | - | 0.0 |
| value_gap_no_conflict | 14 | 12-2 | 0.8571 | 2-2 | 0.0793 |
| pythagorean_no_conflict | 14 | 12-2 | 0.8571 | 2-2 | 0.0793 |
| expectation_no_conflict | 14 | 12-2 | 0.8571 | 2-2 | 0.0793 |
| value_gap_aligned | 14 | 12-2 | 0.8571 | 2-2 | 0.0793 |
| pythagorean_aligned | 13 | 11-2 | 0.8462 | 3-2 | 0.0684 |

## Notes

- Prefer policies that remove more losses than wins without starving play count.
- Small-sample results should be treated as monitor-only until more full-season data exists.