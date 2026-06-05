# Feature Research Report

- Feature rows: 109
- Graded bets: 18
- Result: 14-4 (0.7778)

## Key Observations

- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.
- Best simple overlay in this sample is value_gap_no_conflict: 12-2 over 14 plays.

## Factor Groups

### best_edge_market

### pythagorean_pick_alignment

### value_gap_pick_alignment

### market_expectation_pick_alignment

### overperformance_pick_alignment

### division_game

### data_quality_status

## Policy Simulations

- baseline: 14-4 (0.7778) over 18 plays; removed 0-0
- value_gap_no_conflict: 12-2 (0.8571) over 14 plays; removed 2-2
- pythagorean_no_conflict: 12-2 (0.8571) over 14 plays; removed 2-2
- expectation_no_conflict: 12-2 (0.8571) over 14 plays; removed 2-2
- value_gap_aligned: 12-2 (0.8571) over 14 plays; removed 2-2
- pythagorean_aligned: 11-2 (0.8462) over 13 plays; removed 3-2

## Candidate Policy

- Status: monitor_candidate_overlay
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
