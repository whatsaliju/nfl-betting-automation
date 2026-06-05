# Factor Promotion Report

Promotion rules are conservative. Candidate factors may be simulated as soft overlays; production-ready factors still need guardrail testing before changing picks.

| Factor | Status | Plays | W-L | Lift | Allowed | Notes |
|---|---|---:|---:|---:|---|---|
| best_edge_score_bin=4_to_5 | candidate | 9 | 8-1 | 0.1111 | yes | below production threshold 40 |
| value_gap_pick_alignment=aligned | candidate | 8 | 7-1 | 0.0972 | yes | below production threshold 40 |
| market_expectation_side=HOME | monitor | 6 | 6-0 | 0.2222 | no | thin sample below candidate threshold 8 |
| total_score_bin=0_to_3.5 | monitor | 4 | 4-0 | 0.2222 | no | thin sample below candidate threshold 8 |
| total_score_bin=3.5_to_4.5 | monitor | 4 | 4-0 | 0.2222 | no | thin sample below candidate threshold 8 |
| vegas_win_total_delta_bin=abs>=4 | monitor | 4 | 4-0 | 0.2222 | no | thin sample below candidate threshold 8 |
| overperformance_side=AWAY | monitor | 7 | 6-1 | 0.0793 | no | thin sample below candidate threshold 8 |
| pythagorean_pick_alignment=aligned | monitor | 7 | 6-1 | 0.0793 | no | thin sample below candidate threshold 8 |
| pythagorean_wins_delta_bin=abs2_to_4 | monitor | 7 | 6-1 | 0.0793 | no | thin sample below candidate threshold 8 |
| best_edge_market=total | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| market_expectation_pick_alignment=conflict | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| market_expectation_pick_alignment=non_side_pick | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| overperformance_pick_alignment=aligned | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| overperformance_pick_alignment=non_side_pick | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| pythagorean_pick_alignment=non_side_pick | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| spread_score_bin=3.5_to_4.5 | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| total_status=playable | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| value_gap_pick_alignment=non_side_pick | monitor | 6 | 5-1 | 0.0555 | no | thin sample below candidate threshold 8 |
| actual_vs_pythagorean_delta_bin=abs0.5_to_2 | monitor | 11 | 9-2 | 0.0404 | no | below production threshold 40 |
| pythagorean_side=AWAY | monitor | 10 | 8-2 | 0.0222 | no | below production threshold 40 |
| value_gap_side=AWAY | monitor | 10 | 8-2 | 0.0222 | no | below production threshold 40 |
| best_edge_side=HOME | monitor | 5 | 4-1 | 0.0222 | no | thin sample below candidate threshold 8 |
| best_edge_side=UNDER | monitor | 5 | 4-1 | 0.0222 | no | thin sample below candidate threshold 8 |
| vegas_win_total_delta_bin=abs0.5_to_2 | monitor | 5 | 4-1 | 0.0222 | no | thin sample below candidate threshold 8 |
| pythagorean_vs_vegas_delta_bin=abs0.5_to_2 | research | 3 | 3-0 | 0.2222 | no | needs at least 4 graded plays to monitor |
| data_quality_status=DEGRADED | research | 2 | 2-0 | 0.2222 | no | context factor should not directly alter picks; needs at least 4 graded plays to monitor |
| moneyline_selected_ev_bin=<=0 | research | 2 | 2-0 | 0.2222 | no | moneyline is research-only until the pricing model is separately validated; needs at least 4 graded plays to monitor |
| pythagorean_vs_vegas_delta_bin=abs2_to_4 | research | 2 | 2-0 | 0.2222 | no | needs at least 4 graded plays to monitor |
| source_health_status=DEGRADED | research | 2 | 2-0 | 0.2222 | no | context factor should not directly alter picks; needs at least 4 graded plays to monitor |
| spread_score_bin=>=4.5 | research | 2 | 2-0 | 0.2222 | no | needs at least 4 graded plays to monitor |