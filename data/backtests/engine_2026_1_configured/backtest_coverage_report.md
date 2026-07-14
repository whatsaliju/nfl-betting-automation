# Backtest Coverage Report

## Current Valid Replay

- Weeks: [11, 12, 13, 14, 15, 16, 17, 18]
- Games: 109
- Engine plays: 18
- Graded selected bets: 18
- Record: 14-4-0
- Win rate: 0.7778

## Full 2025 Replay Attempt

- Requested weeks: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
- Completed weeks: []
- Skipped weeks: [1, 2, 3, 4, 5, 6, 7, 8, 9]
- Failed weeks: [10, 11, 12, 13, 14, 15, 16, 17, 18]

## Verdict

- Status: WEEKLY_PIPELINE_READY_MONITOR
- Recommendation: Current weekly workflows are close to operational for 2026, but full-season historical selector validation remains blocked until old Action market files are normalized or earlier weekly query files are restored.

## Blockers

- Weeks 1-9 are missing weekly query/referee input files.
- Fresh full-season replay hits older raw Action CSV schema without normalized_matchup.

## Next Steps

- Add a raw Action market normalizer for historical dated CSVs.
- Restore or regenerate week1-week9 query/referee files before rerunning full 2025 selector replay.
- Run one 2026 preseason dry run after current 2026 data sources are available.
- Keep WARPS, market router, and CLV gates in monitor mode until the graded selected-bet sample grows.