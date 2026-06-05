# Promotion Overlay Simulation

Soft-rule tests generated from promoted candidate factors.

| Overlay | Plays | W-L | Win Rate | Removed W-L | Delta | Recommendation |
|---|---:|---:|---:|---:|---:|---|
| best_edge_score_bin=4_to_5:only | 9 | 8-1 | 0.8889 | 6-3 | 0.1111 | Too restrictive for production; useful as a confidence tag. |
| value_gap_pick_alignment=aligned:only | 8 | 7-1 | 0.875 | 7-3 | 0.0972 | Too restrictive for production; useful as a confidence tag. |
| value_gap_pick_alignment=aligned:aligned_or_total | 14 | 12-2 | 0.8571 | 2-2 | 0.0793 | Candidate threshold-bump policy; keep monitoring play starvation. |
| value_gap_pick_alignment=aligned:no_conflict | 14 | 12-2 | 0.8571 | 2-2 | 0.0793 | Best candidate for a soft veto simulation, not production gating. |
| baseline | 18 | 14-4 | 0.7778 | - | 0.0 | Current selector baseline. |