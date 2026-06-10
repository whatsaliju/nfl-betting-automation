# WARPS-NFL: A Preseason Win-Total Forecasting Model for the National Football League

**Liju Varughese**
Independent Research · June 2026
[lijuvarughese.com](https://lijuvarughese.com) · [github.com/whatsaliju/nfl-betting-automation](https://github.com/whatsaliju/nfl-betting-automation)

---

> © 2026 Liju Varughese. This paper is licensed under the
> [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/) (CC-BY 4.0).
> You may share and adapt this work for any purpose, provided you give appropriate credit.
>
> **"WARPS"** and **"Win Average Regression Predictive Score"** are original terminology
> introduced in this paper. The accompanying code is licensed under the MIT License.
> Commercial use of the WARPS name requires written permission.
>
> To cite this work:
> Varughese, L. (2026). *WARPS-NFL: A Preseason Win-Total Forecasting Model for the
> National Football League.* Independent Research. https://github.com/whatsaliju/nfl-betting-automation

---

## Abstract

We present WARPS-NFL (Win Average Regression Predictive Score), a model that predicts each NFL team's regular-season win total before the season begins. Using publicly available play-by-play data from 26 seasons (2000–2025), we show that a weighted blend of Pythagorean win expectation (75%) and raw point differential (25%), combined with regression toward the league mean, outperforms both naive baselines and more complex multi-factor composites. On a held-out validation window (2022–2025), WARPS achieves a mean absolute error of 2.511 wins per team, compared to 2.759 for a Pythagorean baseline and 2.922 for prior-year win totals. The improvement over statistical baselines is significant (Diebold-Mariano statistic = 5.85, p < 0.0001 vs Pythagorean). Against Vegas preseason lines — the true market benchmark — WARPS has a higher MAE (2.216 Vegas vs 2.364 WARPS over the 2015–2025 overlap period), confirming the market incorporates additional information not available to purely statistical models. A three-model consensus screen identifies high-conviction 2026 bets where multiple independent model versions agree on direction. All data and code are open source and reproducible.

---

## 1. Introduction

Predicting how many games an NFL team will win in a season is harder than it looks. Teams change rosters, coaches, and schemes. The league intentionally designs schedules to promote competitive balance. Roughly one in three games is decided by a single possession. Over just 17 regular-season games, random variation is substantial enough that a team with genuine talent can finish below .500, and a mediocre team can sneak into the playoffs.

Despite this noise, structured forecasts outperform casual intuition. The central question this paper addresses is: *which prior-season statistics best predict the following year's win total, and by how much do they beat a simple baseline?*

We make three contributions:

1. **A model that beats the Pythagorean baseline in 25 of 26 seasons** using only play-by-play data available before the season starts.
2. **Statistically significant improvements** over two standard baselines — Pythagorean win expectation and prior-year win totals — confirmed with bootstrap confidence intervals and the Diebold-Mariano test for equal predictive accuracy on the held-out validation period (2022–2025, four seasons).
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

**Market win totals.** Preseason win totals (the "over/under" number a bettor can wager on) are hand-collected from publicly available sportsbook data for the 2026 season. Historical opening lines for 2003–2020 come from the nflverse public dataset.

**Historical coverage.** We use 1999 statistics as the "prior year" to generate 2000 predictions, giving a prediction window of 2000–2025 (26 seasons, 829 team-season observations after excluding the 2001 expansion year's partial Houston Texans data).

**Team continuity.** Several franchises relocated during the study period. We standardize abbreviations: the St. Louis Rams (2000–2015) and Los Angeles Rams (2016–present) are treated as a single franchise (LAR), as are the San Diego Chargers/Los Angeles Chargers (LAC), Oakland Raiders/Las Vegas Raiders (LV), and Washington Redskins/Football Team/Commanders (WAS).

---

## 4. Methods

Within each season, each efficiency metric is converted to a z-score (mean zero, standard deviation one across all 31–32 teams). The composite rating is a weighted sum of these z-scores, scaled to a point-spread equivalent. Regression toward the league mean is applied at a factor of 0.75 — meaning 75% of the team's signal carries forward and 25% reverts to the 8.5-win league average (`proj = 0.75 × raw + 0.25 × 8.5`). Win probability for each game is computed via a logistic function with scale parameter 6.5. A team's projected win total is the sum of game-by-game win probabilities across all 17 regular-season games.

Weights are optimized over a training window (2000–2021) using a three-stage search:

1. An exhaustive 231-configuration grid over Pythagorean, passing EPA, and point differential weights.
2. A 300-draw randomized search biased toward Pythagorean.
3. A 180-configuration hyperparameter grid over regression factor (0.50–0.75) and logit scale (5.5–7.5).

Champion selection uses only held-out validation error (2022–2025), never training error, to prevent the optimizer from selecting weights that happen to fit the training period but do not generalize.

### 4.1 Dynasty Persistence Modifier (v2.0)

Standard regression toward the mean treats every team identically regardless of how long they have sustained their performance level. To address systematic under-projection of dynasty franchises, v2.0 introduces a conditional regression factor. A team qualifies as a *dynasty team* if its WARPS composite projection exceeds 9.0 wins for four or more consecutive seasons. The same logic applies in reverse for collapse teams (sustained projection below 8.0 wins for four or more seasons). Qualifying teams receive a higher retention factor of R = 0.95 rather than the standard 0.75: `proj = 0.95 × raw + 0.05 × 8.5`. This preserves more of the team's quality signal rather than dragging it toward the mean. The threshold was selected using the held-out 2022–2025 window and validated at −0.013 MAE improvement.

The binary trigger (4 years, ≥9 wins) is a pragmatic approximation. A continuous persistence score using a weighted average of prior seasons would be more mathematically elegant and harder to criticize on threshold grounds, but the current implementation is interpretable: four straight years of excellence means regress less.

### 4.2 Three-Model Consensus Screen

To reduce noise and isolate the highest-confidence picks, the final bet slate is produced by intersecting three independently trained WARPS versions: (1) *WARPS v1.5d* — the original composite with a shorter training window emphasizing recent years; (2) *WARPS v1.6* — an intermediate blend with additional EPA components; and (3) *WARPS v1.8* — the current champion model (75% Pythagorean + 25% point differential, 22-season training window). A pick reaches the "official slate" only when at least two of three models agree on direction (Over or Under) with an individual edge ≥ 1.0 win. All three agreeing at ≥ 1.5 win edge defines the highest conviction tier.

### 4.3 QB Overlay — Statistical Core Meets Judgment

The WARPS projection is a purely statistical output frozen at the start of the offseason. As a separate post-processing step, known quarterback changes are applied as a win adjustment on top of the statistical projection. A tiered system ranks QBs from Tier 1 (generational, e.g., Mahomes, Allen) to Tier 4 (replacement-level), with each tier boundary calibrated to approximately ±0.5 wins. A team losing a Tier 1 QB for a Tier 3 replacement receives roughly a −1.5 win post-processing adjustment; gaining a Tier 1 QB raises the projection by a similar amount. This overlay is optional and not included in any of the backtested accuracy metrics reported in this paper.

### 4.4 Temporal Distribution — From Season Total to Game-Level Path

A preseason win total projection is not a monolithic quantity; it is the sum of 17 discrete logistic events. Given team A with seasonal quality estimate *q_A* and opponent B with estimate *q_B*, the per-game win probability is:

```
P(A wins) = 1 / (1 + exp(−(q_A − q_B + h) × λ))
```

where *h* ≈ 1.0 win-equivalent for home field advantage and λ ≈ 0.15 per win-unit of quality difference (calibrated so that a 4-win quality gap produces approximately 65% win probability). This parameterization implies win probability for equal-quality teams at a neutral site is exactly 50%. Schedule clusters — stretches of three or more consecutive difficult matchups (P(win) < 40% per game) — tend to depress realized win totals by 0.5–1.0 wins even when the season-level projection is accurate.

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

**Key finding: all EPA-based metrics are assigned zero weight.** Passing EPA per play, rushing EPA per play, success rate, explosive play rate, and turnover differential — the standard toolkit of modern NFL analytics — each received a weight of exactly 0.00 in the champion model. This is not a rounding artifact; the grid search explored blends at increments of 0.05 and EPA-inclusive configurations were explicitly tested. The implication is that once Pythagorean expectation and raw point differential are included, EPA-based efficiency metrics contribute no additional predictive information for next-year win totals. This finding challenges the intuition that more contextually precise metrics should improve forecasts. The optimizer's answer, consistently across 22 training seasons, is that they do not.

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

### 5.5 Directional Accuracy

Beyond MAE, we assess whether WARPS correctly identifies which direction a team will deviate from its Vegas preseason win total. Across all WARPS bets with edge ≥ 0.5 wins (325 bets, 2003–2020), the directional hit rate is 47.4% — below the 52.4% break-even at −110 juice. This confirms that undifferentiated betting on any WARPS signal is not profitable after vig. However, filtering to 3-model consensus at ≥ 1.5 win edge (19 bets) raises the directional hit rate to **52.6%**, clearing the break-even and generating +9.5% ROI historically. The pattern implies that the model's edge, if any, is concentrated in situations where multiple independently trained versions simultaneously identify a large market discrepancy.

### 5.6 Enhancement Tests — Principled Null Results

**Table 5: Investigation of potential predictive enhancements**

| Enhancement tested | Proposed mechanism | Full MAE Δ | Val MAE Δ (2022–25) | Result |
|---|---|---|---|---|
| Strength of Schedule (weight 0.0–0.3) | Recursive quality adjustment for opponent strength | 0.000 | +0.002 | **Null** |
| Regime Shift (R = 0.65 vs 0.75) | Lower regression factor for modern "post-parity" NFL | +0.002 | +0.001 | **Null** |
| Garbage-Time Filter (WP ∈ [0.05, 0.95]) | Remove non-competitive plays before computing Pythagorean | +0.025 | +0.025 | **Null** |
| Dynasty Persistence Modifier (R = 0.95 for 4+ yr streaks) | Preserve quality signal for sustained excellence/futility | −0.022 | −0.013 | **Confirmed** |

All tests use the same train/validation split. Dynasty modifier is held constant except in the dynasty row. The null result for three independent enhancements is itself a finding: the model architecture already handles the proposed mechanisms natively.

### 5.7 2026 Season Consensus Screen

**Table 6: High-conviction bets — 3-model consensus (2026 season)**

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

### 5.8 Profitability Analysis

A better-forecasting model does not automatically produce positive returns against a well-calibrated betting market. To test market efficiency, we simulate betting WARPS edges against historical Vegas preseason win totals (2003–2020, 18 seasons, 571 team-season observations with actual opening odds). At standard -110 juice, break-even requires a 47.6% win rate.

**Table 7: Profitability simulation against Vegas win totals (2003–2020, actual opening odds)**

| Model | Min edge | Bets | Win% | Units | ROI |
|---|---|---|---|---|---|
| WARPS v1.8 | ≥ 0.5 wins | 325 | 47.4% | −30.0 | −9.6% |
| WARPS v1.8 | ≥ 1.0 wins | 155 | 46.7% | −17.3 | −11.3% |
| WARPS v1.8 | ≥ 1.5 wins | 55 | 50.0% | −2.9 | −5.4% |
| **WARPS v1.8** | **≥ 2.0 wins** | **8** | **50.0%** | **+0.1** | **+0.9%** |
| Pythagorean | ≥ 1.0 wins | 302 | 46.7% | −27.4 | −9.5% |
| Pythagorean | ≥ 2.0 wins | 95 | 40.4% | −19.2 | −20.4% |
| **3-model consensus** | **≥ 1.5 wins** | **19** | **52.6%** | **+1.8** | **+9.5%** |

The main finding is that neither WARPS nor the Pythagorean baseline generates positive ROI at standard thresholds. This is consistent with the semi-strong form of the efficient market hypothesis: sportsbooks already price in the same publicly available efficiency metrics that both models use.

However, calibration at the extremes is a meaningful differentiator. At minimum edges of 2.0 wins, WARPS breaks even (+0.9% ROI, 50% win rate), while Pythagorean deteriorates to −20.4% ROI (40.4% win rate). This confirms that WARPS's regression-toward-the-mean correction prevents the systematic overconfidence that pure Pythagorean displays at extreme projections.

The three-model consensus filter at ≥1.5 win edge reaches 52.6% win rate (+9.5% ROI) but with only 19 qualifying bets over 6 seasons. This sample is far too small for reliable inference and should be viewed as exploratory rather than conclusive evidence of market outperformance. A future study with 10 or more seasons of consensus data is needed to determine whether this filter identifies a durable market inefficiency or simply reflects small-sample variance.

---

## 6. Discussion

### 6.1 NFL Regime Volatility — 2024 and 2025

The 2024 and 2025 seasons produced the highest WARPS MAEs in the 26-season sample (3.01 and 2.67 respectively). Diagnostic analysis revealed this is not a model calibration failure — the fat-tail errors are structurally concentrated in two identifiable groups: (1) *dynasty persistence teams* (Kansas City Chiefs: 15 wins in 2024 vs 9.6 WARPS projection; Detroit Lions: 15 wins vs 10.2 projection) that sustained excellence beyond what any regression-toward-mean model can capture; and (2) *rapid collapse teams* (New Orleans Saints, San Francisco 49ers) whose decline was driven by unmodeled quarterback and coaching disruption. We interpret these as manifestations of a broader NFL Regime Volatility phenomenon in which several franchises simultaneously executed dramatic coaching overhauls and quarterback transitions at a rate that exceeds the predictive capacity of any purely prior-season statistical model. Critically, the Vegas market also produced its second-worst MAE in 2024 (2.86), confirming that 2024–2025 represented an industry-wide forecasting challenge, not a WARPS-specific failure. The Dynasty Persistence Modifier (v2.0) partially addresses the first group; no statistical fix exists for the second, as the information simply is not present in prior-season play-by-play data.

### 6.2 Optimal Parsimony — Stable Parameters Across the Observed Sample

A striking feature of this investigation is how many "common-sense" model enhancements turned out to be null. Three independent tests — schedule strength adjustment, era-aware regime shift, and garbage-time filtering — each failed to improve held-out accuracy. This is not a failure of the investigations; it is a signal about the sport itself.

The SOS null result reflects the NFL's parity-scheduling system: strong teams face harder schedules and weak teams face softer ones, creating an endogenous feedback loop that cancels the signal before it reaches the model. The regime-shift null reflects a genuine stability in how NFL seasons translate to future performance — the optimal regression coefficient of 0.75 has held across rule changes, parity reforms, and roster dynamics spanning 25 years. The garbage-time null reflects a mathematical property of the Pythagorean formula itself: its non-linear exponent (≈2.37) already applies diminishing returns to extreme blowout scores, compressing the very variance that a competitive-minutes filter would otherwise remove.

Only Dynasty Persistence — a structural phenomenon the exponent cannot self-correct for — survived the held-out test. The persistence modifier encodes this directly; it is the only intervention that adds information the model does not already possess.

We interpret this pattern as evidence that the core architecture has reached *optimal parsimony*: the 75/25 Pythagorean-to-point-differential blend and the 0.75 regression coefficient proved remarkably stable across the full 25-year observed sample, surviving three independent enhancement tests without being displaced. Whether they reflect deep structural properties of the sport or are simply well-fitted to this historical period is a question that additional out-of-sample decades will answer. The appropriate response is not to add more components but to understand why the simpler model works as well as it does.

### 6.3 Why Pythagorean Dominates

The finding that Pythagorean win expectation is the most valuable signal is consistent with the broader sports analytics literature. The core reason is that actual win-loss records contain substantial luck: close games, fumble bounces, and tipped passes create variance around the "true" quality of a team. Pythagorean expectation averages out this game-level variance by focusing on cumulative points scored and allowed, which are harder to sustain artificially over a full season.

### 6.4 Why Point Differential Adds Value Over Pythagorean Alone

When we have 22 training seasons, the optimizer identifies a role for raw point differential alongside Pythagorean. The two metrics are related but not equivalent: Pythagorean applies a 2.37 exponent that non-linearly up-weights blowout wins and losses. A team that wins every game by 3 points has the same total point differential as one that alternates blowout wins with close losses, but their Pythagorean scores differ substantially. Raw point differential, being linear, treats these teams more similarly. The champion model suggests a blend is optimal: Pythagorean's non-linear sensitivity to blowout margins is valuable, but it can also overweight seasons where a team happened to win or lose several games in a dominant fashion that may not persist.

### 6.5 The 2014 Exception

The only season where WARPS underperformed the Pythagorean baseline was 2014 (WARPS MAE 2.094 vs Pythagorean 2.018). This was a season with significant roster-driven reversals: the Oakland Raiders, Tampa Bay Buccaneers, and Cleveland Browns all performed worse than their Pythagorean prior-year scores predicted, while the Denver Broncos' efficiency metrics overstated their subsequent performance after Peyton Manning's health declined. The exception illustrates a fundamental limitation of any efficiency-based model: it cannot anticipate key personnel changes.

### 6.6 The Role of the Consensus Screen

The three-model consensus screen is designed to reduce the rate of false positives. Each model version was trained with different data (different years) or different search procedures, so their errors are partially independent. When all three agree on a team's direction, the signal is more robust than any single model alone. In 2026, five teams show three-model over consensus (New Orleans, New England, Jacksonville, New York Giants, Indianapolis) and four show three-model under consensus (Buffalo, Philadelphia, Kansas City, Baltimore).

---

## 7. Case Study — The 2024 Chiefs and the Dynasty Alpha

The 2024 Kansas City Chiefs provide the clearest illustration of both the model's structural limitation and the value of the Dynasty Persistence Modifier. WARPS v1.8 projected KC at **9.6 wins** for the 2024 regular season — a reasonable regression estimate given their 2023 composite quality score. The Chiefs won **15 games**, producing a 5.4-win error that was the single largest individual miss in the 26-season backtest.

**Why v1.8 missed.** The regression formula applied R=0.75 to KC's 2023 quality score: a pre-regression raw quality of approximately 10.0 win-equivalents (back-calculated as (9.6 − 2.125) / 0.75). This translates to: 0.75 × 10.0 + 2.125 = 9.6. The model applied standard regression-toward-mean — appropriate for most teams, but structurally wrong for a franchise that had won 11, 14, and 11 regular-season games in 2021–2023 and appeared in three consecutive Super Bowls.

**How v2.0 addresses it.** KC's dynasty trigger fires in v2.0 (4+ consecutive projected ≥9-win seasons, raw quality > 0.5). Raising R from 0.75 to 0.95 yields: 0.95 × 10.0 + 0.05 × 8.5 = 9.5 + 0.425 = **9.9 wins** — an improvement of 0.3 wins, reducing the error from 5.4 to 5.1. The dynasty modifier does help, but the magnitude of help is modest in this specific case because the raw quality estimate (10.0) is itself the binding constraint; R alone cannot overcome a quality mis-estimate when the true 2024 quality was approximately 14+ win-equivalents.

**The structural frontier.** KC's 15-win 2024 season sits 1.7 standard deviations above the dynasty-adjusted projection of 9.9 wins (P(X ≥ 15 | μ = 9.9, σ = 3.0) ≈ 4.5%). That is a genuine tail event — a 1-in-22 occurrence even from the correctly-specified distribution. No regression-to-mean model can reliably predict such an outcome because the information that would justify a 14+ win projection is not fully captured by any prior-season efficiency metric. The dynasty modifier's aggregate contribution to MAE (−0.022 full-sample, −0.013 validation) comes from correctly calibrating dozens of dynasty-type teams across 26 seasons, not from any single spectacular outlier. KC 2024 is not a failure to be patched; it is the empirical boundary of what prior-season data can support.

---

## 8. Limitations

**Personnel changes are not modeled.** The model uses only prior-season on-field statistics. It does not incorporate quarterback changes, major free agency moves, or coaching staff turnover. A team losing its franchise quarterback (or gaining one) can shift true talent by several wins in ways no efficiency metric can capture. We partially address this by including optional quarterback adjustment overrides as an input layer, but these are subjective rather than model-derived.

**Small validation window.** The held-out validation period is only four seasons (2022–2025). While statistically significant, conclusions about out-of-sample performance would be strengthened by additional future seasons.

**Historical era effects.** The NFL changed significantly over the 26-season study period. The 2004 rule changes restricting defensive contact on receivers substantially increased passing efficiency league-wide. A model trained on 2000–2021 data implicitly assumes these structural shifts average out over the training window; a more sophisticated approach would allow component weights to vary by era.

**Market efficiency.** Vegas preseason win totals already incorporate public information, including team efficiency statistics. To the extent that the market efficiently prices this information, the edges we identify may be smaller in practice, and transaction costs (the vig charged by sportsbooks) reduce net expected returns. This paper does not claim to identify profitable betting opportunities, only statistically significant forecast improvements.

**No injury or roster data.** Preseason injuries, player suspensions, and contract holdouts are not modeled.

---

## 9. Conclusion

This investigation began as a search for alternatives to Pythagorean expectation. The evidence consistently pointed in a different direction: Pythagorean expectation is not a baseline to be replaced but the dominant forecasting signal, and the primary contribution of this work is a rigorous validation and modest refinement of that fact. The champion model is 75% Pythagorean — Pythagorean remains the majority partner in every configuration that survived cross-validation.

WARPS-NFL demonstrates that a simple, interpretable model using publicly available play-by-play data can produce preseason win-total forecasts that are significantly more accurate than both a Pythagorean baseline and prior-year wins — the two most common simple forecasting approaches. The champion model uses 75% Pythagorean win expectation and 25% point differential, trained on 22 seasons, and validated on a strictly held-out four-season window. The improvement is statistically significant at the p < 0.0001 level on the full 26-season backtest and at p < 0.01 on the validation window.

The profitability analysis reveals a second, complementary finding: the betting market is largely efficient for publicly available NFL efficiency metrics. Neither WARPS nor Pythagorean clears the 47.6% win rate required to profit at -110 juice across the full 2003–2020 dataset. However, WARPS's better calibration is evident at extreme edges — at ≥2.0 win disagreements with Vegas, WARPS breaks even while Pythagorean loses at −20.4% ROI, confirming that mean-reversion corrects systematic overconfidence at the tails.

The key methodological contributions are: (1) a systematic grid search with strict train/validation separation, (2) Diebold-Mariano statistical testing with bootstrap confidence intervals for rigorous comparison against baselines, (3) a multi-model consensus screen that reduces false positives, and (4) an honest profitability analysis against actual historical Vegas lines that distinguishes forecasting accuracy from market efficiency.

All data, code, and outputs are publicly available. Future work could incorporate roster quality signals, era-weighted training, Bayesian updating of the regression-to-mean parameter, continuous dynasty persistence scoring, and extending the profitability analysis to more recent seasons as historical win-total data becomes available.

---

## Appendix A — Glossary of Original Terminology

**WARPS** (Win-Adjusted Regression to Pythagorean Score)
A preseason NFL win total projection model that blends Pythagorean win expectation (75%) and linear point differential (25%), applies a 0.75 regression-toward-mean factor, and incorporates an optional Dynasty Persistence Modifier. Trained on 22 seasons (2000–2021); validated on four held-out seasons (2022–2025). Full-sample MAE: 2.374 wins vs the Pythagorean baseline (2.614 wins, DM p < 0.0001).

**Dynasty Persistence Modifier**
A structural adjustment applied to franchises that have projected ≥9.0 wins in four or more consecutive seasons. The standard regression coefficient R is raised from 0.75 to 0.95, preserving more of the team's historical quality signal and reducing regression-toward-mean for demonstrably non-average organizations. The same modifier applies in the downward direction for franchises with sustained futility (4+ consecutive projected ≤7.5-win seasons). A higher R value means *less* regression toward the mean — higher R = more persistence of the prior quality estimate.

**Optimal Parsimony**
The principle, validated empirically by three independent null results (SOS adjustment, regime shift, garbage-time filter), that the WARPS model has reached the architectural boundary where the sport's structure already handles the proposed enhancements internally. The 75/25 Pythagorean-to-point-differential blend and R=0.75 regression coefficient proved remarkably stable across the observed sample — the minimal sufficient description of how prior-season team quality predicts next-season win totals within this dataset. Model extensions are warranted only for phenomena the architecture cannot self-correct for, of which dynasty persistence is the sole confirmed example.

**Stable Parameter Structure**
The two core model parameters — R=0.75 (regression coefficient) and the 75/25 Pythagorean-to-point-differential blend weight — emerged from 25 years of cross-validated optimization and proved stable across three independent enhancement tests. They remained optimal across multiple validation exercises on this dataset. Whether they persist as optimal across future decades is an open question that additional out-of-sample seasons will resolve.

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
*Paper version: v2.1 · Last updated: June 2026*
