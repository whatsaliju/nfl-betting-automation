# WARPS-NFL: A Preseason Win-Total Forecasting Model for the National Football League

**Author:** Liju Varughese

**Affiliation:** Independent Researcher

**Email:** lvarughese@gmail.com

**SSRN Preprint:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6926058

**Data and code:** https://github.com/whatsaliju/nfl-betting-automation

---

## Abstract

We present WARPS-NFL, a preseason NFL win-total forecasting model combining Pythagorean win expectation (~75%) and point differential (~25%) with regression toward the league mean. Evaluated on 26 seasons (2000–2025), WARPS achieves a full-sample MAE of 2.376 wins per team, outperforming the Pythagorean baseline in 25 of 26 seasons (Diebold-Mariano p < 0.0001) and all 4 held-out validation seasons (2022–2025).

A 2D parameter sensitivity analysis shows 100% of tested configurations fall within 0.05 wins of the optimum — a completely flat surface. Walk-forward retraining across 16 expanding windows (2010–2025) selects varied configurations (w_pyth: 0.50–1.00, median=0.57), confirming the surface is too flat to identify a consistently superior configuration. Despite this, the fixed representative configuration outperforms window-specific optimization in 12 of 16 out-of-sample trials by 0.012 wins on average — fine-tuning a flat surface adds noise, not signal.

EPA metrics, success rate, explosive play rate, and turnover differential each received zero weight once points-based signals were included. Strength-of-schedule adjustment, era-aware regime shift, and garbage-time filtering each produced null results. Against Vegas preseason lines, WARPS has higher MAE (2.216 vs 2.364, 2015–2025), confirming markets incorporate information beyond statistical models. All data and code are open source.

---

## Keywords

NFL, preseason forecasting, win totals, Pythagorean expectation, point differential, regression toward the mean, walk-forward validation, Diebold-Mariano test, model parsimony, sports analytics
