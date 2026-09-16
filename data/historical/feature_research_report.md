# Feature Research Report

- Feature rows: 116
- Graded bets: 0
- Result: 0-0 (None)

## Key Observations

- Do not make this a hard gate yet; every expectation row in the current replay uses a thin result sample.

## Factor Groups

### best_edge_market
- NONE: 61 games
- spread: 1 games

### pythagorean_pick_alignment
- conflict: 1 games
- no_pick: 61 games

### value_gap_pick_alignment
- conflict: 1 games
- no_pick: 61 games

### market_expectation_pick_alignment
- aligned: 1 games
- no_pick: 61 games

### overperformance_pick_alignment
- aligned: 1 games
- no_pick: 61 games

### division_game
- false: 30 games
- true: 32 games

### data_quality_status
- DEGRADED: 30 games
- NONE: 16 games
- OK: 16 games

## Candidate Policy

- Status: monitor_only
- Recommendation: Track expectation alignment as an annotation and candidate spread threshold bump. Do not hard-gate production picks until more full-season feature rows are available.
