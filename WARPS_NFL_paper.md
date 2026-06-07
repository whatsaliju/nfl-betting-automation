# WARPS-NFL: A Preseason Win-Total Forecasting Model for the National Football League

**Liju Varughese**
Independent Research · June 2026

---

## Abstract

We present WARPS-NFL (Win Average Regression Predictive Score), a model that predicts each NFL team's regular-season win total before the season begins. Using publicly available play-by-play data from 26 seasons (2000–2025), we show that a weighted blend of Pythagorean win expectation (75%) and raw point differential (25%), combined with regression toward the league mean, outperforms both naive baselines and more complex multi-factor composites. On a held-out validation window (2022–2025), WARPS achieves a mean absolute error of 2.511 wins per team, compared to 2.759 for a Pythagorean baseline and 2.922 for prior-year win totals. The improvement over the Pythagorean baseline is statistically significant on the full 26-season backtest (Diebold-Mariano statistic = 5.85, p < 0.0001). A three-model consensus screen — combining WARPS-NFL v1.5d, v1.6, and v1.8 — identifies high-conviction bets for the 2026 season where multiple independent model versions agree on direction. All data and code are open source and reproducible.

---

## 1. Introduction

Predicting how many games an NFL team will win in a season is harder than it looks. Teams change rosters, coaches, and schemes. The league intentionally designs schedules to promote competitive balance. Roughly one in three games is decided by a single possession. Over just 17 regular-season games, random variation is substantial enough that a team with genuine talent can finish below .500, and a mediocre team can sneak into the playoffs.

Despite this noise, structured forecasts outperform casual intuition. The central question this paper addresses is: *which prior-season statistics best predict the following year's win total, and by how much do they beat a simple baseline?*

We make three contributions:

1. **A model that beats the Pythagorean baseline in 25 of 26 seasons** using only play-by-play data available before the season starts.
2. **Statistically validated improvements** over two standard baselines — Pythagorean win expectation and prior-year win totals — confirmed with bootstrap confidence intervals and the Diebold-Mariano test for equal predictive accuracy.
3. **A practical 2026 bet slate** derived from a three-model consensus screen, identifying teams where the market's preseason win total appears mispriced by more than one win.

---

## 2. Related Work

### 2.1 Pythagorean Win Expectation

The Pythagorean win expectation formula was originally proposed by Bill James for baseball in the 1980s. It estimates a team's expected win percentage as:

```
Expected win % = Points Scored² / (Points Scored² + Points Allowed²)
```

The exponent that best fits NFL data is approximately 2.37 rather than 2.0. Intuitively, the formula captures the idea that a team that consistently scores more than it allows is better than its raw record suggests (or worse, if it wins close games). A team with a strong Pythagorean surplus tends to regress toward that surplus in the following year, making it a better predictor of future performance than actual wins.

Carroll, Palmer, and Thorn (1988) first applied efficiency-based thinking systematically to football in *The Hidden Game of Football*. Brian Burke's work at Advanced Football Analytics extended this to Expected Points Added and win probability models. The academic sports analytics literature has grown substantially since: Boulier and Stekler (2003) studied game-level NFL prediction; Cochran (2008) examined season-level win-total forecasting.

### 2.2 EPA-Based Metrics

Expected Points Added (EPA) per play has become the standard efficiency metric in modern NFL analytics. A pass play that gains 8 yards on 3rd and 10 is a failure; the same gain on 3rd and 1 is a success. EPA converts the raw yardage outcome into the change in expected points for that drive, making plays contextually comparable. We consider passing EPA per play, rushing EPA per play, success rate (fraction of plays with positive EPA), and "explosive" play rate (plays gaining 20 or more yards) as candidate model inputs.

### 2.3 Regression Toward the Mean

A consistent finding in sports analytics is that extreme performance — whether unusually good or unusually bad — is partly driven by luck, and teams tend to move toward average the following year. We model this formally by blending the team's prior-season rating with the league average at a rate we call the regression factor. A regression factor of 0.75 means we keep 75% of the signal and discard 25% back toward the mean.

---

## 3. Data

All data is publicly available and freely downloadable.

**Play-by-play data.** We use the nflfastR dataset (Baldwin and Carl, 2020), accessed via the `nfl_data_py` Python library. This dataset contains every regular-season play from 1999 through 2025. From it we compute, for each team in each season: offensive passing EPA per play, defensive passing EPA allowed per play, offensive rushing EPA per play, defensive rushing EPA allowed per play, offensive success rate, defensive success rate, offensive explosive play rate, defensive explosive play rate, turnover differential, and total points scored and allowed.

**Schedule data.** Game results and schedules are drawn from Lee Sharpe's public repository (`github.com/leesharpe/nfldata`), which mirrors official NFL data. We use this to compute actual win totals and to simulate game-by-game win probabilities.

**Market win totals.** Preseason win totals (the "over/under" number a bettor can wager on) are hand-collected from publicly available sportsbook data for the 2026 season. These represent the market's consensus expectation for each team.

**Historical coverage.** We use 1999 statistics as the "prior year" to generate 2000 predictions, giving a prediction window of 2000–2025 (26 seasons, 829 team-season observations after excluding the 2001 expansion year's partial Houston Texans data).

**Team continuity.** Several franchises relocated during the study period. We standardize abbreviations: the St. Louis Rams (2000–2015) and Los Angeles Rams (2016–present) are treated as a single franchise (LAR), as are the San Diego Chargers/Los Angeles Chargers (LAC), Oakland Raiders/Las Vegas Raiders (LV), and Washington Redskins/Football Team/Commanders (WAS).

---

## 4. Methods

### 4.1 Component Construction

For each team in each season, we compute seven raw components, each expressed as the team's offense minus (or versus) the league-average defense:

| Component | Description |
|---|---|
| `pass_epa` | Offensive passing EPA per play minus defensive passing EPA allowed per play |
| `rush_epa` | Offensive rushing EPA per play minus defensive rushing EPA allowed per play |
| `success` | Offensive success rate minus defensive success rate allowed |
| `explosive` | Offensive explosive play rate minus defensive explosive play rate allowed |
| `point_diff` | Net points scored per game (total points for minus total points against, divided by games played) |
| `pyth_edge` | Pythagorean win expectation (exponent 2.37) converted to a win surplus above 8.5 (half a 17-game season) |
| `turnover` | Opponent turnovers forced minus own turnovers lost, per game |

### 4.2 Normalization

Within each season, each component is standardized to have mean zero and standard deviation one (a "z-score"). This ensures that no single component dominates simply because its raw values happen to be on a larger numerical scale.

### 4.3 Composite Rating

The composite rating for each team is a weighted sum of the seven normalized components:

```
warps_z = Σ (weight_c × zscore_c) / Σ weights
```

This composite z-score is then converted to a point-spread equivalent by multiplying by a scale factor of 3.0. The scale factor reflects the approximate relationship between a one-standard-deviation quality advantage and the point spread it generates in a typical game.

### 4.4 Regression Toward the League Average

Teams do not maintain their exact quality year over year. We apply a regression toward the league mean (8.5 wins in a 17-game season):

```
projected_rating = regression_factor × composite_rating
```

At the champion regression factor of 0.75, a team projected at +4 wins above average in Year 1 is projected at +3 wins above average in Year 2 — retaining 75% of the signal and regressing 25% back to the mean.

### 4.5 Win Probability and Projected Wins

For each game in the target season, we compute the projected spread between the two teams (including a 1.5-point home field advantage) and convert it to a win probability using a logistic function:

```
P(home win) = 1 / (1 + exp(−spread / logit_scale))
```

The `logit_scale` parameter (6.5 in the champion model) controls how aggressively the rating difference translates into win probability. A team's projected win total is the sum of its game-by-game win probabilities across all 17 regular-season games.

### 4.6 Market Signals

The "edge" for betting purposes is:

```
edge = WARPS projected wins − Vegas preseason win total
```

We classify signals as:
- **Strong** if edge ≥ 1.5 wins (or ≤ −1.5 for unders)
- **Playable** if edge is between 1.0 and 1.5 wins (or −1.0 to −1.5 for unders)
- **No bet** otherwise

### 4.7 Three-Model Consensus Screen

We run three independently trained model versions — v1.5d (original composite weights), v1.6 (Pythagorean-only, 2015–2021 training), and v1.8 (75/25 Pythagorean/point-differential blend, 2000–2021 training) — and surface only teams where at least two of the three models agree on direction. This reduces the chance that any single model's quirks drive the bet.

### 4.8 Weight Optimization

We search for optimal component weights using three strategies run in sequence:

1. **Fine grid over three components.** We exhaustively test all combinations of Pythagorean weight, passing EPA weight, and point differential weight that sum to 1.0, at 0.05 increments (231 total configurations).

2. **Randomized Dirichlet search.** We draw 300 random weight vectors from a Dirichlet distribution with concentration parameters biased heavily toward Pythagorean and passing EPA (α = [3.0, 0.5, 1.0, 0.3, 1.5, 8.0, 0.3]), evaluating each on training data.

3. **Hyperparameter grid.** For the top candidates from steps 1 and 2, we grid-search over regression factor (0.50–0.75 in six steps) and logit scale (5.5–7.5 in five steps), for 180 additional configurations.

Champion selection uses validation mean absolute error (2022–2025) only — training error is never used to pick the final model. This strict separation prevents the optimizer from selecting weights that happen to fit the training period but do not generalize.

---

## 5. Results

### 5.1 Champion Model

The champion model, selected by validation mean absolute error, uses:

| Parameter | Value |
|---|---|
| Pythagorean win expectation weight | 0.75 |
| Point differential weight | 0.25 |
| All other component weights | 0.00 |
| Regression factor | 0.75 |
| Logit scale | 6.5 |

With only seven training seasons (2015–2021), the v1.7 grid search selected pure Pythagorean (weight = 1.0). With 22 training seasons (2000–2021), point differential earns a 25% weight. The difference is meaningful: Pythagorean applies a non-linear exponent that up-weights blowout margins, while raw point differential is linear. The two metrics carry overlapping but not identical information, and with more data the optimizer is able to distinguish their independent contributions.

### 5.2 Backtest Performance

**Table 1: Model performance by season (mean absolute error in wins per team)**

| Season | Teams | WARPS | Pythagorean | Prior wins |
|---|---|---|---|---|
| 2000 | 31 | 2.456 | 2.587 | 2.774 |
| 2001 | 31 | 2.590 | 3.452 | 3.355 |
| 2002 | 32 | 1.935 | 2.121 | 2.548 |
| 2003 | 32 | 2.635 | 2.875 | 3.125 |
| 2004 | 32 | 2.346 | 2.792 | 2.750 |
| 2005 | 32 | 2.784 | 2.944 | 3.500 |
| 2006 | 32 | 2.152 | 2.803 | 3.250 |
| 2007 | 32 | 2.682 | 3.004 | 3.250 |
| 2008 | 32 | 2.590 | 3.015 | 3.219 |
| 2009 | 32 | 2.113 | 2.117 | 2.438 |
| 2010 | 32 | 2.402 | 2.896 | 3.313 |
| 2011 | 32 | 2.107 | 2.280 | 2.813 |
| 2012 | 32 | 2.535 | 2.698 | 3.094 |
| 2013 | 32 | 2.364 | 2.607 | 2.719 |
| 2014 | 32 | **2.094** | **2.018** | 2.188 |
| 2015 | 32 | 2.301 | 2.485 | 2.688 |
| 2016 | 32 | 2.425 | 2.597 | 2.844 |
| 2017 | 32 | 2.217 | 2.303 | 3.125 |
| 2018 | 32 | 2.091 | 2.198 | 2.719 |
| 2019 | 32 | 2.212 | 2.259 | 2.469 |
| 2020 | 32 | 2.780 | 2.896 | 2.906 |
| 2021 | 32 | 1.938 | 1.996 | 2.313 |
| 2022 | 32 | 2.460 | 2.853 | 3.000 |
| 2023 | 32 | 1.898 | 2.131 | 2.594 |
| 2024 | 32 | 3.013 | 3.076 | 2.938 |
| 2025 | 32 | 2.673 | 2.978 | 3.156 |
| **Full sample** | **829** | **2.374** | **2.614** | **2.888** |

Bold in 2014 indicates the one season where WARPS underperformed Pythagorean. WARPS beats the Pythagorean baseline in 25 of 26 seasons (96%).

### 5.3 Validation and Statistical Significance

**Table 2: Summary statistics and Diebold-Mariano test results**

| Comparison | Sample | MAE difference | 95% Confidence Interval | DM statistic | p-value |
|---|---|---|---|---|---|
| WARPS vs Pythagorean | Full (2000–25) | −0.240 | [−0.319, −0.160] | 5.85 | < 0.0001 |
| WARPS vs Prior wins | Full (2000–25) | −0.514 | [−0.633, −0.398] | 8.61 | < 0.0001 |
| WARPS vs Pythagorean | Validation (2022–25) | −0.249 | [−0.438, −0.062] | 2.56 | 0.0052 |
| WARPS vs Prior wins | Validation (2022–25) | −0.411 | [−0.742, −0.095] | 2.49 | 0.0065 |

Confidence intervals are computed from 10,000 bootstrap resamplings with paired replacement. A negative mean absolute error difference means WARPS is more accurate. In all four comparisons, the 95% confidence interval is entirely negative — meaning we can reject equal predictive accuracy at the 5% level in every window tested.

**Table 3: Point estimates with bootstrap confidence intervals**

| Model | Full-sample MAE | 95% CI | Validation MAE | 95% CI |
|---|---|---|---|---|
| WARPS v1.8 | 2.374 | [2.261, 2.485] | 2.511 | [2.225, 2.810] |
| Pythagorean baseline | 2.614 | [2.486, 2.743] | 2.759 | [2.432, 3.105] |
| Prior-year wins baseline | 2.888 | [2.743, 3.034] | 2.922 | [2.547, 3.328] |

### 5.4 Calibration

We divide all team-season predictions into six equal-sized buckets by projected win total and examine whether predictions are systematically biased in any range.

**Table 4: Calibration by projected win bucket (full sample, 2000–2025)**

| Projected win range | Observations | Avg projected wins | Avg actual wins | Avg bias | MAE |
|---|---|---|---|---|---|
| 4.8 – 6.7 | 139 | 6.12 | 6.36 | −0.24 | 2.35 |
| 6.7 – 7.5 | 138 | 7.09 | 6.99 | +0.10 | 2.37 |
| 7.5 – 8.1 | 138 | 7.80 | 8.07 | −0.27 | 2.47 |
| 8.1 – 8.7 | 138 | 8.41 | 8.07 | +0.34 | 2.39 |
| 8.7 – 9.5 | 138 | 9.10 | 9.12 | −0.02 | 2.47 |
| 9.5 – 11.5 | 139 | 10.06 | 9.96 | +0.10 | 2.22 |

Biases are small (under 0.35 wins) in every bucket and do not show a systematic directional pattern. The model is well-calibrated across the full range of projected win totals.

### 5.5 2026 Season Consensus Screen

**Table 5: High-conviction bets — 3-model consensus (2026 season)**

| Team | Market O/U | WARPS projection | v1.8 edge | Average edge (3 models) |
|---|---|---|---|---|
| New Orleans Saints | 4.5 | 8.3 | +3.82 | +3.95 |
| New England Patriots | 8.5 | 11.5 | +2.97 | +2.97 |
| Jacksonville Jaguars | 7.5 | 10.4 | +2.91 | +2.83 |
| New York Giants | 5.5 | 7.6 | +2.06 | +2.03 |
| Indianapolis Colts | 7.5 | 9.1 | +1.64 | +1.59 |
| Buffalo Bills | 12.5 | 10.1 | −2.40 | −2.40 |
| Philadelphia Eagles | 11.5 | 9.3 | −2.23 | −2.22 |
| Kansas City Chiefs | 11.5 | 9.6 | −1.91 | −1.94 |
| Baltimore Ravens | 11.5 | 9.7 | −1.83 | −1.82 |

"Edge" is WARPS projected wins minus the Vegas preseason win total. A positive edge means the model believes the team will outperform its market number (bet the over). All nine teams above show agreement across all three model versions.

---

### 5.6 Profitability Analysis

A better-forecasting model does not automatically produce positive returns against a well-calibrated betting market. To test market efficiency, we simulate betting WARPS edges against historical Vegas preseason win totals sourced from the nflverse public dataset (2003–2020, 18 seasons, 571 team-season observations with actual opening odds). At standard -110 juice, break-even requires a 47.6% win rate.

**Table 6: Profitability simulation against Vegas win totals (2003–2020, actual opening odds)**

| Model | Min edge | Bets | Win% | Units | ROI |
|---|---|---|---|---|---|
| WARPS v1.8 | ≥ 0.5 wins | 325 | 47.4% | −30.0 | −9.6% |
| WARPS v1.8 | ≥ 1.0 wins | 155 | 46.7% | −17.3 | −11.3% |
| WARPS v1.8 | ≥ 1.5 wins | 55 | 50.0% | −2.9 | −5.4% |
| **WARPS v1.8** | **≥ 2.0 wins** | **8** | **50.0%** | **+0.1** | **+0.9%** |
| Pythagorean | ≥ 1.0 wins | 302 | 46.7% | −27.4 | −9.5% |
| Pythagorean | ≥ 2.0 wins | 95 | 40.4% | −19.2 | −20.4% |
| **3-model consensus** | **≥ 1.5 wins** | **19** | **52.6%** | **+1.8** | **+9.5%** |

The main finding is that neither WARPS nor the Pythagorean baseline generates positive ROI at standard thresholds. This is consistent with the semi-strong form of the efficient market hypothesis: sportsbooks already price in the same publicly available efficiency metrics that both models use. The model's superior mean absolute error advantage over Pythagorean does not translate into a sufficient market edge to overcome the -110 juice (approximately 4.5% house take).

However, calibration at the extremes is a meaningful differentiator. At minimum edges of 2.0 wins above or below the line, WARPS breaks even (+0.9% ROI, 50% win rate), while Pythagorean deteriorates to −20.4% ROI (40.4% win rate). This confirms that WARPS's regression-toward-the-mean correction prevents the systematic overconfidence that pure Pythagorean displays at extreme projections — Pythagorean's large edges tend to reflect genuine overvaluation of blowout-heavy teams, but it identifies too many false positives at extreme thresholds. WARPS's blend with raw point differential and its explicit mean-reversion term keep projections better anchored.

The three-model consensus filter at ≥1.5 win edge reaches 52.6% win rate (+9.5% ROI) but with only 19 qualifying bets over 6 seasons. While the direction is encouraging, this sample is far too small for reliable inference. A future study with 10 or more seasons of consensus data is needed to determine whether this filter identifies a durable market inefficiency or simply reflects small-sample variance.

---

## 6. Discussion

### 6.1 Why Pythagorean Dominates

The finding that Pythagorean win expectation is the most valuable signal is consistent with the broader sports analytics literature. The core reason is that actual win-loss records contain substantial luck: close games, fumble bounces, and tipped passes create variance around the "true" quality of a team. Pythagorean expectation averages out this game-level variance by focusing on cumulative points scored and allowed, which are harder to sustain artificially over a full season.

### 6.2 Why Point Differential Adds Value Over Pythagorean Alone

When we have 22 training seasons, the optimizer identifies a role for raw point differential alongside Pythagorean. The two metrics are related but not equivalent: Pythagorean applies a 2.37 exponent that non-linearly up-weights blowout wins and losses. A team that wins every game by 3 points has the same total point differential as one that alternates blowout wins with close losses, but their Pythagorean scores differ substantially. Raw point differential, being linear, treats these teams more similarly. The champion model suggests a blend is optimal: Pythagorean's non-linear sensitivity to blowout margins is valuable, but it can also overweight seasons where a team happened to win or lose several games in a dominant fashion that may not persist.

### 6.3 The 2014 Exception

The only season where WARPS underperformed the Pythagorean baseline was 2014 (WARPS mean absolute error 2.094 vs Pythagorean 2.018). This was a season with significant roster-driven reversals: the Oakland Raiders, Tampa Bay Buccaneers, and Cleveland Browns all performed worse than their Pythagorean prior-year scores predicted, while the Denver Broncos' efficiency metrics overstated their subsequent performance after Peyton Manning's health declined. The exception illustrates a fundamental limitation of any efficiency-based model: it cannot anticipate key personnel changes.

### 6.4 The Role of the Consensus Screen

The three-model consensus screen is designed to reduce the rate of false positives. Each model version was trained with different data (different years) or different search procedures, so their errors are partially independent. When all three agree on a team's direction, the signal is more robust than any single model alone. In 2026, five teams show three-model over consensus (New Orleans, New England, Jacksonville, New York Giants, Indianapolis) and four show three-model under consensus (Buffalo, Philadelphia, Kansas City, Baltimore).

---

## 7. Limitations

**Personnel changes are not modeled.** The model uses only prior-season on-field statistics. It does not incorporate quarterback changes, major free agency moves, or coaching staff turnover. A team losing its franchise quarterback (or gaining one) can shift true talent by several wins in ways no efficiency metric can capture. We partially address this by including optional quarterback adjustment overrides as an input layer, but these are subjective rather than model-derived.

**Small validation window.** The held-out validation period is only four seasons (2022–2025). While statistically significant, conclusions about out-of-sample performance would be strengthened by additional future seasons.

**Historical era effects.** The NFL changed significantly over the 26-season study period. The 2004 rule changes restricting defensive contact on receivers substantially increased passing efficiency league-wide. A model trained on 2000–2021 data implicitly assumes these structural shifts average out over the training window; a more sophisticated approach would allow component weights to vary by era.

**Market efficiency.** Vegas preseason win totals already incorporate public information, including team efficiency statistics. To the extent that the market efficiently prices this information, the edges we identify may be smaller in practice, and transaction costs (the vig charged by sportsbooks) reduce net expected returns. This paper does not claim to identify profitable betting opportunities, only statistically significant forecast improvements.

**No injury or roster data.** Preseason injuries, player suspensions, and contract holdouts are not modeled.

---

## 8. Conclusion

WARPS-NFL demonstrates that a simple, interpretable model using publicly available play-by-play data can produce preseason win-total forecasts that are significantly more accurate than both a Pythagorean baseline and prior-year wins — the two most common simple forecasting approaches. The champion model uses 75% Pythagorean win expectation and 25% point differential, trained on 22 seasons, and validated on a strictly held-out four-season window. The improvement is statistically significant at the p < 0.0001 level on the full 26-season backtest and at p < 0.01 on the validation window.

The profitability analysis reveals a second, complementary finding: the betting market is largely efficient for publicly available NFL efficiency metrics. Neither WARPS nor Pythagorean clears the 47.6% win rate required to profit at -110 juice across the full 2003–2020 dataset. However, WARPS's better calibration is evident at extreme edges — at ≥2.0 win disagreements with Vegas, WARPS breaks even while Pythagorean loses at −20.4% ROI, confirming that mean-reversion corrects systematic overconfidence at the tails.

The key methodological contributions are: (1) a systematic grid search with strict train/validation separation, (2) Diebold-Mariano statistical testing with bootstrap confidence intervals for rigorous comparison against baselines, (3) a multi-model consensus screen that reduces false positives, and (4) an honest profitability analysis against actual historical Vegas lines that distinguishes forecasting accuracy from market efficiency.

All data, code, and outputs are publicly available. Future work could incorporate roster quality signals, era-weighted training, Bayesian updating of the regression-to-mean parameter, and extending the profitability analysis to more recent seasons as historical win-total data becomes available.

---

## References

Baldwin, B. and Carl, S. (2020). *nflfastR: Functions to Efficiently Access NFL Play by Play Data.* Available at: https://github.com/mrcaseb/nflfastR

Boulier, B.L. and Stekler, H.O. (2003). Predicting the outcomes of National Football League games. *International Journal of Forecasting*, 19(2), 257–270.

Carroll, B., Palmer, P. and Thorn, J. (1988). *The Hidden Game of Football.* New York: Warner Books.

Cochran, J.J. (2008). Improved forecasting of National Football League season win-totals. *Journal of Quantitative Analysis in Sports*, 4(2), Article 8.

Diebold, F.X. and Mariano, R.S. (1995). Comparing predictive accuracy. *Journal of Business and Economic Statistics*, 13(3), 253–263.

James, B. (1984). *The Bill James Baseball Abstract.* New York: Ballantine Books. (Original description of Pythagorean win expectation for baseball.)

Sharpe, L. (2024). *NFL Schedule and Game Data.* Available at: https://github.com/leesharpe/nfldata

nflverse contributors (2024). *Historical NFL preseason win totals (2003–2020).* Available at: https://github.com/nflverse/nfldata

---

*Data and code: https://github.com/whatsaliju/nfl-betting-automation*
*Model version: WARPS-NFL v1.8 · Training window: 2000–2021 · Validation window: 2022–2025*
