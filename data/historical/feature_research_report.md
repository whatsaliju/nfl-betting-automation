# Feature Research Report

- Feature rows: 133
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Value-gap alignment looks promising but is still a small sample: aligned 0-0 vs conflict 0-0.
- Pythagorean side alignment is also promising: aligned 0-0 vs conflict 0-0.
- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 72 games
- spread: 5 games
- total: 2 games

### pythagorean_pick_alignment
- aligned: 3 games
- conflict: 2 games
- no_pick: 72 games
- non_side_pick: 2 games

### value_gap_pick_alignment
- aligned: 3 games
- conflict: 2 games
- no_pick: 72 games
- non_side_pick: 2 games

### market_expectation_pick_alignment
- aligned: 1 games
- conflict: 3 games
- neutral: 1 games
- no_pick: 72 games
- non_side_pick: 2 games

### overperformance_pick_alignment
- aligned: 2 games
- conflict: 3 games
- no_pick: 72 games
- non_side_pick: 2 games

### division_game
- false: 43 games
- true: 36 games

### data_quality_status
- DEGRADED: 30 games
- NONE: 16 games
- OK: 33 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
