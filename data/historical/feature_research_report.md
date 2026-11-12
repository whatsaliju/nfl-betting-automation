# Feature Research Report

- Feature rows: 235
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Pythagorean side alignment is also promising: aligned 0-0 vs conflict 0-0.
- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 167 games
- spread: 9 games
- total: 5 games

### pythagorean_pick_alignment
- aligned: 4 games
- conflict: 4 games
- neutral: 1 games
- no_pick: 167 games
- non_side_pick: 5 games

### value_gap_pick_alignment
- aligned: 5 games
- neutral: 4 games
- no_pick: 167 games
- non_side_pick: 5 games

### market_expectation_pick_alignment
- aligned: 2 games
- conflict: 6 games
- neutral: 1 games
- no_pick: 167 games
- non_side_pick: 5 games

### overperformance_pick_alignment
- aligned: 2 games
- conflict: 4 games
- neutral: 3 games
- no_pick: 167 games
- non_side_pick: 5 games

### division_game
- false: 109 games
- true: 72 games

### data_quality_status
- DEGRADED: 30 games
- NONE: 16 games
- OK: 135 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
