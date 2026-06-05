# Source Reliability Report

- Overall status: DEGRADED
- Overall score: 97.6
- Weeks audited: 8

## Recommendations

- Monitor lower-scoring source groups: rotowire.
- Keep degraded source status visible; current sample is too small for a hard veto.
- Do not promote factor overlays to production when critical sources are unsafe or missing.
- For live 2026 runs, require action markets, queries, and referee trends before final recommendations.

## Source Scores

| Source | Weeks | Avg | Min | OK | Degraded | Unsafe | Missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| rotowire | 8 | 87.5 | 0 | 7 | 1 | 0 | 1 |
| action_injuries | 8 | 99.4 | 95 | 8 | 0 | 0 | 0 |
| action_markets | 8 | 99.4 | 95 | 8 | 0 | 0 | 0 |
| action_weather | 8 | 99.4 | 95 | 8 | 0 | 0 | 0 |
| queries | 8 | 100.0 | 100 | 8 | 0 | 0 | 0 |
| referee_trends | 8 | 100.0 | 100 | 8 | 0 | 0 | 0 |

## Performance By Quality Status

| Dimension | Status | Games | Picks | W-L | Win Rate |
|---|---|---:|---:|---:|---:|
| source_health_status | DEGRADED | 16 | 2 | 2-0 | 1.0 |
| source_health_status | OK | 93 | 16 | 12-4 | 0.75 |
| data_quality_status | DEGRADED | 16 | 2 | 2-0 | 1.0 |
| data_quality_status | OK | 93 | 16 | 12-4 | 0.75 |