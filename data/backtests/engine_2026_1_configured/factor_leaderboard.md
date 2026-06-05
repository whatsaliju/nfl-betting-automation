# Factor Leaderboard

Research-only ranking of feature buckets against graded replay picks.

| Feature | Value | Type | Plays | W-L | Win Rate | Lift | Sample |
|---|---|---|---:|---:|---:|---:|---|
| value_gap_pick_alignment | aligned | candidate_overlay | 8 | 7-1 | 0.875 | 0.0972 | monitor |
| actual_vs_pythagorean_delta_bin | abs0.5_to_2 | research_feature | 11 | 9-2 | 0.8182 | 0.0404 | monitor |
| pythagorean_side | AWAY | research_feature | 10 | 8-2 | 0.8 | 0.0222 | monitor |
| value_gap_side | AWAY | research_feature | 10 | 8-2 | 0.8 | 0.0222 | monitor |
| expectation_games_tracked_min_bin | <4_games | research_feature | 18 | 14-4 | 0.7778 | 0.0 | monitor |
| value_gap_side | HOME | research_feature | 8 | 6-2 | 0.75 | -0.0278 | monitor |
| market_expectation_side | AWAY | research_feature | 10 | 7-3 | 0.7 | -0.0778 | monitor |
| pythagorean_wins_delta_bin | abs>=4 | research_feature | 10 | 7-3 | 0.7 | -0.0778 | monitor |
| pythagorean_vs_vegas_delta_bin | abs>=4 | research_feature | 13 | 9-4 | 0.6923 | -0.0855 | monitor |
| best_edge_score_bin | 4_to_5 | selector_diagnostic | 9 | 8-1 | 0.8889 | 0.1111 | monitor |
| best_edge_status | play | selector_diagnostic | 18 | 14-4 | 0.7778 | 0.0 | monitor |
| spread_status | playable | selector_diagnostic | 13 | 10-3 | 0.7692 | -0.0086 | monitor |
| best_edge_market | spread | selector_diagnostic | 12 | 9-3 | 0.75 | -0.0278 | monitor |
| total_status | lean | selector_diagnostic | 12 | 9-3 | 0.75 | -0.0278 | monitor |
| spread_score_bin | 0_to_3.5 | selector_diagnostic | 9 | 6-3 | 0.6667 | -0.1111 | monitor |
| total_score_bin | <=0 | selector_diagnostic | 8 | 5-3 | 0.625 | -0.1528 | monitor |
| moneyline_selected_ev_bin | >=0.20 | moneyline_research | 12 | 10-2 | 0.8333 | 0.0555 | monitor |
| moneyline_status | research_thin_sample | moneyline_research | 18 | 14-4 | 0.7778 | 0.0 | monitor |
| moneyline_selected_edge_bin | 0.10_to_0.20 | moneyline_research | 8 | 6-2 | 0.75 | -0.0278 | monitor |
| conference_game | true | context | 14 | 11-3 | 0.7857 | 0.0079 | monitor |
| expectation_sample_warning | true | context | 18 | 14-4 | 0.7778 | 0.0 | monitor |
| data_quality_status | OK | context | 16 | 12-4 | 0.75 | -0.0278 | monitor |
| source_health_status | OK | context | 16 | 12-4 | 0.75 | -0.0278 | monitor |
| division_game | false | context | 11 | 8-3 | 0.7273 | -0.0505 | monitor |
| pythagorean_pick_alignment | aligned | candidate_overlay | 7 | 6-1 | 0.8571 | 0.0793 | thin |
| market_expectation_pick_alignment | conflict | candidate_overlay | 6 | 5-1 | 0.8333 | 0.0555 | thin |
| market_expectation_pick_alignment | non_side_pick | candidate_overlay | 6 | 5-1 | 0.8333 | 0.0555 | thin |
| overperformance_pick_alignment | aligned | candidate_overlay | 6 | 5-1 | 0.8333 | 0.0555 | thin |
| overperformance_pick_alignment | non_side_pick | candidate_overlay | 6 | 5-1 | 0.8333 | 0.0555 | thin |
| pythagorean_pick_alignment | non_side_pick | candidate_overlay | 6 | 5-1 | 0.8333 | 0.0555 | thin |