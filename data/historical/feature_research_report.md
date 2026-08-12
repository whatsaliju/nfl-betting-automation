# Feature Research Report

- Feature rows: 35
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 16 games

### pythagorean_pick_alignment
- no_pick: 16 games

### value_gap_pick_alignment
- no_pick: 16 games

### market_expectation_pick_alignment
- no_pick: 16 games

### overperformance_pick_alignment
- no_pick: 16 games

### division_game
- true: 16 games

### data_quality_status
- NONE: 16 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
