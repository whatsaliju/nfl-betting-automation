# Feature Research Report

- Feature rows: 192
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Pythagorean side alignment is also promising: aligned 0-0 vs conflict 0-0.
- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 127 games
- spread: 8 games
- total: 3 games

### pythagorean_pick_alignment
- aligned: 3 games
- conflict: 5 games
- no_pick: 127 games
- non_side_pick: 3 games

### value_gap_pick_alignment
- aligned: 5 games
- neutral: 3 games
- no_pick: 127 games
- non_side_pick: 3 games

### market_expectation_pick_alignment
- aligned: 1 games
- conflict: 6 games
- neutral: 1 games
- no_pick: 127 games
- non_side_pick: 3 games

### overperformance_pick_alignment
- aligned: 1 games
- conflict: 5 games
- neutral: 2 games
- no_pick: 127 games
- non_side_pick: 3 games

### division_game
- false: 82 games
- true: 56 games

### data_quality_status
- DEGRADED: 44 games
- NONE: 16 games
- OK: 78 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
