# Feature Research Report

- Feature rows: 149
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Value-gap alignment looks promising but is still a small sample: aligned 0-0 vs conflict 0-0.
- Pythagorean side alignment is also promising: aligned 0-0 vs conflict 0-0.
- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 82 games
- spread: 10 games
- total: 3 games

### pythagorean_pick_alignment
- aligned: 8 games
- conflict: 2 games
- no_pick: 82 games
- non_side_pick: 3 games

### value_gap_pick_alignment
- aligned: 7 games
- conflict: 1 games
- neutral: 2 games
- no_pick: 82 games
- non_side_pick: 3 games

### market_expectation_pick_alignment
- aligned: 4 games
- conflict: 4 games
- neutral: 2 games
- no_pick: 82 games
- non_side_pick: 3 games

### overperformance_pick_alignment
- aligned: 3 games
- conflict: 6 games
- neutral: 1 games
- no_pick: 82 games
- non_side_pick: 3 games

### division_game
- false: 55 games
- true: 40 games

### data_quality_status
- DEGRADED: 46 games
- NONE: 16 games
- OK: 33 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
