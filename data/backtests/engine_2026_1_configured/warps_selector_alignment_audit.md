# WARPS Selector Alignment Audit

This audit joins graded weekly engine picks to historical WARPS fair-line game priors.
It is a quality-gate study, not an ROI calculation.

## Verdict

- Status: MONITOR_ONLY
- Recommendation: Sample is still thin; keep WARPS as an explanation and conflict tag.
- Baseline win rate: 0.7778
- Aligned win rate: 0.8
- Conflict win rate: 0.7143

## Alignment Buckets

| Bucket | Plays | W-L-P | Win Rate |
|---|---:|---:|---:|
| aligned | 5 | 4-1-0 | 0.8 |
| conflict | 7 | 5-2-0 | 0.7143 |

## Policy Simulations

| Policy | Plays | W-L-P | Win Rate | Removed W-L-P | Delta |
|---|---:|---:|---:|---:|---:|
| baseline | 18 | 14-4-0 | 0.7778 | 0-0-0 | 0.0 |
| warps_no_conflict | 11 | 9-2-0 | 0.8182 | 5-2-0 | 0.0404 |
| warps_aligned_only | 11 | 9-2-0 | 0.8182 | 5-2-0 | 0.0404 |
| warps_min_1pt_no_conflict | 11 | 9-2-0 | 0.8182 | 5-2-0 | 0.0404 |
| warps_min_2pt_aligned | 10 | 8-2-0 | 0.8 | 6-2-0 | 0.0222 |

## Notes

- Totals are kept in WARPS policy simulations because this audit is focused on spread-side agreement.
- Use this as a downgrade/upgrade candidate only after enough graded rows accumulate.