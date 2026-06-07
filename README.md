# NFL Betting Automation

NFL win-total forecasting and market analysis, including the **WARPS-NFL™** research model.

## WARPS-NFL™

**Win Average Regression Predictive Score** — a preseason NFL win-total forecasting model.

- 26-season backtest (2000–2025), mean absolute error 2.374 wins/team
- Beats Pythagorean baseline in 25 of 26 seasons (p < 0.0001, Diebold-Mariano test)
- Champion model: 75% Pythagorean win expectation + 25% point differential + 0.75 regression factor
- Three-model consensus screen (v1.5d · v1.6 · v1.8) for high-conviction 2026 picks
- Live dashboard: [lijuvarughese.com/labs/nfl-edge](https://lijuvarughese.com/labs/nfl-edge/)

**Research paper:** [WARPS_NFL_paper.md](./WARPS_NFL_paper.md)

**To cite:**
```
Varughese, L. (2026). WARPS-NFL: A Preseason Win-Total Forecasting Model
for the National Football League. https://github.com/whatsaliju/nfl-betting-automation
```

### Run the model

```bash
pip install nfl_data_py pandas numpy scipy
python warps_nfl_model_v1_8.py       # full backtest + 2026 projections
python warps_bootstrap_v1_8.py       # bootstrap confidence intervals
python warps_profitability_backtest.py  # P&L vs historical Vegas lines
```

### Key output files

| File | Contents |
|---|---|
| `warps_backtest_team_results_v1_8.csv` | Per-team predictions vs actuals, 2000–2025 |
| `warps_2026_screen_v1_8.csv` | 2026 projections and Vegas edges for all 32 teams |
| `warps_profitability_summary.csv` | P&L by model and edge threshold (2003–2020) |
| `warps_profitability_by_year.csv` | Year-by-year betting P&L |
| `WARPS_NFL_paper.md` | Full research paper with methods, results, and references |

---

## Weekly Market Analysis

Automated NFL betting analysis with sharp money tracking, referee trends, and line movement detection.

### Workflows

1. **Referee Collection** — Wed 6 PM ET
2. **Initial Market Data** — After workflow 1
3. **Market Update** — Thu/Sat/Sun (manual)
4. **Pro Analysis** — After workflows 2 & 3

### Configuration

Add these secrets in GitHub Settings:
- `GIMMETHEDOG_EMAIL` / `GIMMETHEDOG_PASSWORD`
- `ODDS_API_KEY`
- `ACTION_NETWORK_COOKIES`
- `GMAIL_USERNAME` / `GMAIL_APP_PASSWORD`

---

## License

Code: [MIT License](./LICENSE) — free to use with attribution.
Paper: [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) — free to share and adapt with credit.
"WARPS" and "Win Average Regression Predictive Score" are original terminology by Liju Varughese.
Commercial use of the WARPS name requires written permission.

© 2026 Liju Varughese
