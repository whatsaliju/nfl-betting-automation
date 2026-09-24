# Pick Explanations

| Game | Raw | Gated | Market | Side | Confidence | Reasons |
|---|---|---|---|---|---|---|
| W2 CAR@ATL | play | play | total | OVER | standard | Selector isolated total OVER; Signals: sharp, ref_weather_context |
| W2 CLE@TB | play | play | total | OVER | standard | Selector isolated total OVER; Signals: sharp, ref_weather_context |
| W2 GB@NYJ | play | play | spread | HOME | standard | Selector isolated spread HOME; Signals: sharp, team_rating; Value-gap alignment supports the side; WARPS fair-line prior conflicts toward AWAY |
| W2 SEA@ARI | play | play | spread | HOME | standard | Selector isolated spread HOME; Signals: sharp, team_rating; Value-gap alignment conflicts with the side; WARPS fair-line prior conflicts toward AWAY |
| W2 JAX@DEN | play | play | spread | AWAY | standard | Selector isolated spread AWAY; Signals: sharp, team_rating; Value-gap alignment supports the side; WARPS fair-line prior conflicts toward HOME |
| W2 WAS@DAL | play | play | spread | AWAY | standard | Selector isolated spread AWAY; Signals: sharp, team_rating; Value-gap alignment conflicts with the side; WARPS fair-line prior conflicts toward HOME |
| W3 CIN@PIT | play | play | spread | AWAY | standard | Selector isolated spread AWAY; Signals: sharp, team_rating; Value-gap alignment supports the side; WARPS fair-line prior conflicts toward HOME; WARPS moneyline overlay: HOME +60.6% EV; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 DEN@ATL | play | play | spread | AWAY | standard | Selector isolated spread AWAY; Value-gap alignment supports the side; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 GB@PIT | play | play | spread | HOME | standard | Selector isolated spread HOME; Value-gap alignment supports the side; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE3 SEA@KC | play | play | spread | AWAY | standard | Selector isolated spread AWAY; Signals: sharp; Value-gap alignment supports the side; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE3 ATL@MIA | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 KC@TB | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 CHI@TEN | pass | pass |  |  | none | No isolated selector edge |
| W1 ATL@PIT | lean | watch |  |  | watch | Signals: sharp |
| W1 BAL@IND | lean | watch |  |  | watch | Signals: sharp |
| W1 BUF@HOU | lean | watch |  |  | watch | Signals: sharp |
| W1 CHI@CAR | lean | watch |  |  | watch | Signals: sharp |
| W2 CIN@HOU | lean | watch |  |  | watch | Signals: sharp, injury |
| W2 DET@BUF | pass | pass |  |  | none | No isolated selector edge |
| W2 MIN@CHI | pass | pass |  |  | none | No isolated selector edge |
| W2 NO@BAL | pass | pass |  |  | none | No isolated selector edge |
| W3 ARI@SF | lean | watch |  |  | watch | Signals: sharp, team_rating; WARPS moneyline overlay: AWAY +56.0% EV; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| W3 NYJ@DET | lean | watch |  |  | watch | Signals: sharp, team_rating; WARPS moneyline overlay: HOME +1.3% EV; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| W3 SEA@WAS | lean | watch |  |  | watch | Signals: sharp, team_rating; WARPS moneyline overlay: HOME +50.8% EV; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE2 BAL@MIN | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 DAL@ARI | pass | pass |  |  | none | No isolated selector edge |
| W1 DEN@KC | lean | watch |  |  | watch | Signals: sharp |
| W1 GB@MIN | pass | pass |  |  | none | No isolated selector edge |
| W10 ARI@SEA | lean | watch |  |  | watch | Signals: injury; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| W10 BUF@MIA | lean | watch |  |  | watch | Signals: injury; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE2 NYJ@PIT | pass | pass |  |  | none | No isolated selector edge |
| W2 IND@KC | lean | watch |  |  | watch | Signals: sharp |
| W2 PIT@NE | lean | watch |  |  | watch | No isolated selector edge |
| W3 BAL@DAL | lean | watch |  |  | watch | Signals: sharp; WARPS moneyline overlay: HOME +25.1% EV; Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 ARI@LV | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 CAR@BUF | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 CLE@CHI | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 DAL@SEA | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 DET@CIN | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 IND@NE | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 JAX@NO | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 LAC@HOU | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 LAR@KC | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 MIA@WAS | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 MIN@NYG | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 PHI@BAL | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 TB@NYJ | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE1 TEN@SF | pass | pass |  |  | none | Source warning: source_health_status=DEGRADED, data_quality_status=DEGRADED |
| WPRE2 ATL@IND | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 BUF@CLE | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 CAR@JAX | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 CHI@CIN | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 GB@DEN | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 LV@HOU | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 NO@LAR | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 NYG@MIA | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 PHI@NE | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 SEA@TEN | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 SF@LAC | pass | pass |  |  | none | No isolated selector edge |
| WPRE2 WAS@DET | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 ARI@GB | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 CIN@PHI | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 DET@IND | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 HOU@CAR | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 LAR@LAC | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 MIN@DEN | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 NE@CLE | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 NO@DAL | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 NYG@NYJ | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 PIT@BUF | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 SF@LV | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 TB@JAX | pass | pass |  |  | none | No isolated selector edge |
| WPRE3 WAS@BAL | pass | pass |  |  | none | No isolated selector edge |
| W2.0 WSH@DAL | pass | pass |  |  | none | No isolated selector edge |
| W1 ARI@LAC | pass | pass |  |  | none | No isolated selector edge |
| W1 CLE@JAX | pass | pass |  |  | none | No isolated selector edge |
| W1 DAL@NYG | pass | pass |  |  | none | No isolated selector edge |
| W1 MIA@LV | pass | pass |  |  | none | No isolated selector edge |
| W1 NE@SEA | pass | pass |  |  | none | No isolated selector edge |
| W1 NO@DET | pass | pass |  |  | none | No isolated selector edge |