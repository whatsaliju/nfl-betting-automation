#!/usr/bin/env python3
"""WARPS betting-value backtest.

This script separates forecast disagreement from sportsbook price value.
It builds row-level season win-total bets using only residuals available before
each season to estimate model-side probabilities.
"""

from __future__ import annotations

import argparse
import csv
import urllib.request
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
WIN_TOTALS_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/win_totals.csv"
DEFAULT_BETS = ROOT / "warps_betting_value_bets.csv"
DEFAULT_SUMMARY = ROOT / "warps_betting_value_summary.csv"
DEFAULT_YEARLY = ROOT / "warps_betting_value_by_year.csv"
DEFAULT_GATE_SUMMARY = ROOT / "warps_betting_value_gate_summary.csv"

ALIASES = {
    "OAK": "LV",
    "STL": "LAR",
    "SD": "LAC",
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "SL": "LAR",
}

MODEL_SPECS = {
    "WARPS v2.3": ("warps_backtest_team_results_v2_3.csv", "proj"),
    "WARPS v1.8": ("warps_backtest_team_results_v1_8.csv", "warps_wins"),
    "WARPS v1.7": ("warps_backtest_team_results_v1_7.csv", "warps_wins"),
    "WARPS v1.6": ("warps_backtest_team_results_v1_6.csv", "warps_wins"),
    "WARPS v1.5d": ("warps_backtest_team_results_v1_5d.csv", "warps_wins"),
}


def load_win_totals() -> pd.DataFrame:
    req = urllib.request.Request(WIN_TOTALS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        win_totals = pd.read_csv(StringIO(response.read().decode()))
    win_totals["team"] = win_totals["team"].replace(ALIASES)
    return win_totals


def normalize_backtest(path: Path, projection_col: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df["team"] = df["team"].replace(ALIASES)

    if "actual" in df.columns:
        actual_col = "actual"
    elif "wins" in df.columns:
        actual_col = "wins"
    else:
        raise SystemExit(f"{path} does not contain actual wins")

    if projection_col not in df.columns:
        raise SystemExit(f"{path} does not contain projection column {projection_col}")

    out = df[["season", "team", projection_col, actual_col]].copy()
    out = out.rename(columns={projection_col: "projection", actual_col: "actual_wins"})
    out["projection"] = pd.to_numeric(out["projection"], errors="coerce")
    out["actual_wins"] = pd.to_numeric(out["actual_wins"], errors="coerce")
    out = out.dropna(subset=["projection", "actual_wins"])
    out["residual"] = out["projection"] - out["actual_wins"]
    return out


def american_profit(odds: float) -> float:
    return odds / 100 if odds > 0 else 100 / abs(odds)


def implied_probability(odds: float) -> float:
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def no_vig_probabilities(over_odds: float, under_odds: float) -> tuple[float, float]:
    over = implied_probability(over_odds)
    under = implied_probability(under_odds)
    total = over + under
    return over / total, under / total


def estimate_side_probs(projection: float, line: float, prior_residuals: np.ndarray) -> tuple[float, float, float]:
    simulated_wins = projection - prior_residuals
    return (
        float(np.mean(simulated_wins > line)),
        float(np.mean(simulated_wins < line)),
        float(np.mean(simulated_wins == line)),
    )


def result_for_side(side: str, actual_wins: float, line: float) -> str:
    if actual_wins == line:
        return "push"
    if side == "OVER":
        return "win" if actual_wins > line else "loss"
    return "win" if actual_wins < line else "loss"


def build_model_bets(
    model_name: str,
    model_df: pd.DataFrame,
    win_totals: pd.DataFrame,
    min_prior_residuals: int,
) -> pd.DataFrame:
    merged = model_df.merge(
        win_totals[["season", "team", "line", "over_odds", "under_odds"]],
        on=["season", "team"],
        how="inner",
    )
    merged = merged.dropna(subset=["line", "over_odds", "under_odds"])
    merged = merged[(merged["over_odds"] != 0) & (merged["under_odds"] != 0)]
    rows: list[dict] = []

    for rec in merged.sort_values(["season", "team"]).itertuples(index=False):
        prior = model_df.loc[model_df["season"] < rec.season, "residual"].dropna().to_numpy()
        if len(prior) < min_prior_residuals:
            continue

        over_prob, under_prob, push_prob = estimate_side_probs(float(rec.projection), float(rec.line), prior)
        over_no_vig, under_no_vig = no_vig_probabilities(float(rec.over_odds), float(rec.under_odds))
        edge = float(rec.projection) - float(rec.line)
        side = "OVER" if edge > 0 else "UNDER" if edge < 0 else "PASS"
        if side == "PASS":
            continue

        model_prob = over_prob if side == "OVER" else under_prob
        market_prob = over_no_vig if side == "OVER" else under_no_vig
        odds = float(rec.over_odds) if side == "OVER" else float(rec.under_odds)
        profit = american_profit(odds)
        result = result_for_side(side, float(rec.actual_wins), float(rec.line))
        pnl = profit if result == "win" else 0.0 if result == "push" else -1.0
        loss_prob = 1 - model_prob - push_prob
        expected_units = model_prob * profit - loss_prob

        rows.append(
            {
                "season": int(rec.season),
                "team": rec.team,
                "model": model_name,
                "line": float(rec.line),
                "over_odds": int(rec.over_odds),
                "under_odds": int(rec.under_odds),
                "bet_side": side,
                "bet_odds": int(odds),
                "projection": round(float(rec.projection), 3),
                "actual_wins": float(rec.actual_wins),
                "edge": round(edge, 3),
                "abs_edge": round(abs(edge), 3),
                "model_prob": round(model_prob, 4),
                "market_no_vig_prob": round(market_prob, 4),
                "price_edge": round(model_prob - market_prob, 4),
                "push_prob": round(push_prob, 4),
                "expected_units": round(expected_units, 4),
                "result": result,
                "pnl_units": round(pnl, 4),
                "prior_residuals": int(len(prior)),
            }
        )

    return pd.DataFrame(rows)


def add_consensus_features(bets: pd.DataFrame) -> pd.DataFrame:
    enriched = bets.copy()
    for _, group in bets.groupby(["season", "team", "line"], sort=False):
        sides = group.set_index("model")["bet_side"].to_dict()
        edges = group.set_index("model")["edge"].to_dict()
        available_models = len(sides)
        for idx, row in group.iterrows():
            same_side_models = sorted(model for model, side in sides.items() if side == row["bet_side"])
            opposite_side_models = sorted(model for model, side in sides.items() if side != row["bet_side"])
            v23_edge = edges.get("WARPS v2.3")
            v18_edge = edges.get("WARPS v1.8")
            enriched.at[idx, "available_models"] = available_models
            enriched.at[idx, "agreement_count"] = len(same_side_models)
            enriched.at[idx, "consensus_share"] = len(same_side_models) / available_models if available_models else 0.0
            enriched.at[idx, "same_side_models"] = "|".join(same_side_models)
            enriched.at[idx, "opposite_side_models"] = "|".join(opposite_side_models)
            enriched.at[idx, "v23_edge"] = v23_edge if v23_edge is not None else np.nan
            enriched.at[idx, "v18_edge"] = v18_edge if v18_edge is not None else np.nan
            enriched.at[idx, "v23_agrees"] = sides.get("WARPS v2.3") == row["bet_side"] if "WARPS v2.3" in sides else np.nan
            enriched.at[idx, "v18_agrees"] = sides.get("WARPS v1.8") == row["bet_side"] if "WARPS v1.8" in sides else np.nan

    enriched["available_models"] = enriched["available_models"].astype(int)
    enriched["agreement_count"] = enriched["agreement_count"].astype(int)
    return enriched


def performance_metrics(selected: pd.DataFrame) -> dict:
    if selected.empty:
        return {
            "bets": 0,
            "wins": 0,
            "pushes": 0,
            "losses": 0,
            "win_pct": 0.0,
            "units": 0.0,
            "roi_pct": 0.0,
            "seasons": 0,
            "profitable_seasons": 0,
            "profitable_season_pct": 0.0,
            "worst_season_units": 0.0,
        }

    wins = int((selected["result"] == "win").sum())
    pushes = int((selected["result"] == "push").sum())
    losses = int((selected["result"] == "loss").sum())
    decisions = wins + losses
    units = float(selected["pnl_units"].sum())
    by_season = selected.groupby("season")["pnl_units"].sum()
    seasons = int(by_season.size)
    profitable = int((by_season > 0).sum())
    return {
        "bets": int(len(selected)),
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "win_pct": round(wins / decisions * 100, 2) if decisions else 0.0,
        "units": round(units, 3),
        "roi_pct": round(units / decisions * 100, 2) if decisions else 0.0,
        "seasons": seasons,
        "profitable_seasons": profitable,
        "profitable_season_pct": round(profitable / seasons * 100, 2) if seasons else 0.0,
        "worst_season_units": round(float(by_season.min()), 3) if seasons else 0.0,
    }


def summarize_bets(bets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edge_thresholds = [0.5, 1.0, 1.5, 2.0]
    price_thresholds = [0.0, 0.05, 0.10]
    summary_rows = []
    yearly_rows = []

    for model, model_bets in bets.groupby("model"):
        for edge_t in edge_thresholds:
            for price_t in price_thresholds:
                selected = model_bets[
                    (model_bets["abs_edge"] >= edge_t)
                    & (model_bets["price_edge"] >= price_t)
                ].copy()
                summary_rows.append(
                    {
                        "model": model,
                        "edge_threshold": edge_t,
                        "price_edge_threshold": price_t,
                        **{k: v for k, v in performance_metrics(selected).items() if k in {"bets", "wins", "pushes", "losses", "win_pct", "units", "roi_pct"}},
                    }
                )

        default = model_bets[(model_bets["abs_edge"] >= 1.0) & (model_bets["price_edge"] >= 0.05)]
        for season, season_bets in default.groupby("season"):
            wins = int((season_bets["result"] == "win").sum())
            pushes = int((season_bets["result"] == "push").sum())
            losses = int((season_bets["result"] == "loss").sum())
            decisions = wins + losses
            units = float(season_bets["pnl_units"].sum())
            yearly_rows.append(
                {
                    "model": model,
                    "season": int(season),
                    "bets": int(len(season_bets)),
                    "wins": wins,
                    "pushes": pushes,
                    "losses": losses,
                    "win_pct": round(wins / decisions * 100, 2) if decisions else 0.0,
                    "units": round(units, 3),
                    "roi_pct": round(units / decisions * 100, 2) if decisions else 0.0,
                }
            )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["model", "edge_threshold", "price_edge_threshold"]
    )
    yearly = pd.DataFrame(yearly_rows).sort_values(["model", "season"])
    return summary, yearly


def build_gate_summary(bets: pd.DataFrame) -> pd.DataFrame:
    rows = []
    edge_thresholds = [0.5, 1.0, 1.5, 2.0]
    price_thresholds = [0.0, 0.05, 0.10]
    model_prob_thresholds = [0.50, 0.55, 0.60]
    min_agreements = [1, 2, 3, 4]
    side_filters = ["ALL", "OVER", "UNDER"]

    for model, model_bets in bets.groupby("model"):
        for side_filter in side_filters:
            side_bets = model_bets if side_filter == "ALL" else model_bets[model_bets["bet_side"] == side_filter]
            for edge_t in edge_thresholds:
                for price_t in price_thresholds:
                    for prob_t in model_prob_thresholds:
                        for min_agree in min_agreements:
                            selected = side_bets[
                                (side_bets["abs_edge"] >= edge_t)
                                & (side_bets["price_edge"] >= price_t)
                                & (side_bets["model_prob"] >= prob_t)
                                & (side_bets["agreement_count"] >= min_agree)
                            ]
                            rows.append(
                                {
                                    "model": model,
                                    "side": side_filter,
                                    "edge_threshold": edge_t,
                                    "price_edge_threshold": price_t,
                                    "model_prob_threshold": prob_t,
                                    "min_agreement_count": min_agree,
                                    **performance_metrics(selected),
                                }
                            )

    return pd.DataFrame(rows).sort_values(
        ["model", "side", "edge_threshold", "price_edge_threshold", "model_prob_threshold", "min_agreement_count"]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build WARPS betting-value backtest artifacts.")
    parser.add_argument("--min-prior-residuals", type=int, default=64)
    parser.add_argument("--bets-output", type=Path, default=DEFAULT_BETS)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--yearly-output", type=Path, default=DEFAULT_YEARLY)
    parser.add_argument("--gate-summary-output", type=Path, default=DEFAULT_GATE_SUMMARY)
    args = parser.parse_args()

    win_totals = load_win_totals()
    all_bets = []
    for model_name, (filename, projection_col) in MODEL_SPECS.items():
        path = ROOT / filename
        if not path.exists():
            continue
        model_df = normalize_backtest(path, projection_col)
        all_bets.append(build_model_bets(model_name, model_df, win_totals, args.min_prior_residuals))

    if not all_bets:
        raise SystemExit("No model betting rows were created")

    bets = add_consensus_features(pd.concat(all_bets, ignore_index=True))
    summary, yearly = summarize_bets(bets)
    gate_summary = build_gate_summary(bets)

    bets.to_csv(args.bets_output, index=False, quoting=csv.QUOTE_MINIMAL)
    summary.to_csv(args.summary_output, index=False, quoting=csv.QUOTE_MINIMAL)
    yearly.to_csv(args.yearly_output, index=False, quoting=csv.QUOTE_MINIMAL)
    gate_summary.to_csv(args.gate_summary_output, index=False, quoting=csv.QUOTE_MINIMAL)

    print(f"Wrote {args.bets_output} ({len(bets)} rows)")
    print(f"Wrote {args.summary_output}")
    print(f"Wrote {args.yearly_output}")
    print(f"Wrote {args.gate_summary_output}")
    print("\nDefault gate: abs(edge) >= 1.0 and price_edge >= 5pp")
    default = summary[(summary["edge_threshold"] == 1.0) & (summary["price_edge_threshold"] == 0.05)]
    print(default[["model", "bets", "wins", "pushes", "losses", "win_pct", "units", "roi_pct"]].to_string(index=False))
    robust = gate_summary[(gate_summary["bets"] >= 20) & (gate_summary["seasons"] >= 5)].sort_values(
        ["roi_pct", "units"], ascending=False
    ).head(12)
    print("\nTop richer gates with at least 20 bets and 5 seasons:")
    print(
        robust[
            [
                "model",
                "side",
                "edge_threshold",
                "price_edge_threshold",
                "model_prob_threshold",
                "min_agreement_count",
                "bets",
                "seasons",
                "win_pct",
                "units",
                "roi_pct",
                "profitable_season_pct",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
