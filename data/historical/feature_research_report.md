# Feature Research Report

- Feature rows: 164
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Value-gap alignment looks promising but is still a small sample: aligned 0-0 vs conflict 0-0.
- Pythagorean side alignment is also promising: aligned 0-0 vs conflict 0-0.
- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 100 games
- spread: 7 games
- total: 3 games

### pythagorean_pick_alignment
- aligned: 5 games
- conflict: 2 games
- no_pick: 100 games
- non_side_pick: 3 games

### value_gap_pick_alignment
- aligned: 5 games
- conflict: 1 games
- neutral: 1 games
- no_pick: 100 games
- non_side_pick: 3 games

### market_expectation_pick_alignment
- aligned: 1 games
- conflict: 4 games
- neutral: 2 games
- no_pick: 100 games
- non_side_pick: 3 games

### overperformance_pick_alignment
- aligned: 1 games
- conflict: 4 games
- neutral: 2 games
- no_pick: 100 games
- non_side_pick: 3 games

### division_game
- false: 65 games
- true: 45 games

### data_quality_status
- DEGRADED: 30 games
- NONE: 16 games
- OK: 64 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
