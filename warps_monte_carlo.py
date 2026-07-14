#!/usr/bin/env python3
"""WARPS Monte Carlo distribution layer.

Converts WARPS point forecasts into empirical win distributions by sampling
historical WARPS residuals. This is a forecast uncertainty layer, not a priced
betting model.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_SCREEN = ROOT / "warps_2026_screen_v2_3.csv"
DEFAULT_RESIDUALS = ROOT / "warps_backtest_team_results_v2_3.csv"
DEFAULT_CSV = ROOT / "warps_2026_monte_carlo.csv"
DEFAULT_JSON = ROOT / "site" / "src" / "data" / "warpsMonteCarlo.json"


def signal_tier(row: pd.Series) -> str:
    prob_side = max(float(row["prob_over"]), float(row["prob_under"]))
    edge_abs = abs(float(row["edge"]))
    if prob_side >= 0.72 and edge_abs >= 2.0:
        return "strong"
    if prob_side >= 0.64 and edge_abs >= 1.0:
        return "watch"
    return "thin"


def direction(row: pd.Series) -> str:
    if float(row["prob_over"]) > float(row["prob_under"]):
        return "OVER"
    if float(row["prob_under"]) > float(row["prob_over"]):
        return "UNDER"
    return "SPLIT"


def pct(values: np.ndarray, q: float) -> float:
    return round(float(np.percentile(values, q)), 2)


def residuals_from_backtest(residuals_df: pd.DataFrame, residuals_path: Path) -> np.ndarray:
    if "warps_error" in residuals_df.columns:
        errors = pd.to_numeric(residuals_df["warps_error"], errors="coerce")
    elif {"proj", "actual"}.issubset(residuals_df.columns):
        errors = pd.to_numeric(residuals_df["proj"], errors="coerce") - pd.to_numeric(residuals_df["actual"], errors="coerce")
    else:
        raise SystemExit(f"No residual columns found in {residuals_path}")

    residuals = errors.dropna().to_numpy()
    if len(residuals) == 0:
        raise SystemExit(f"No residuals found in {residuals_path}")
    return residuals


def screen_value(rec: pd.Series, *names: str) -> float:
    for name in names:
        if name in rec and not pd.isna(rec[name]):
            return float(rec[name])
    raise KeyError(f"Missing expected screen column; tried {', '.join(names)}")


def build_simulation(
    screen_path: Path,
    residuals_path: Path,
    sims: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    screen = pd.read_csv(screen_path)
    residuals_df = pd.read_csv(residuals_path)
    residuals = residuals_from_backtest(residuals_df, residuals_path)

    rng = np.random.default_rng(seed)
    sampled_errors = rng.choice(residuals, size=(len(screen), sims), replace=True)

    rows = []
    for idx, rec in screen.reset_index(drop=True).iterrows():
        projection = screen_value(rec, "v23_wins", "warps_wins")
        market_total = screen_value(rec, "market", "market_total")
        simulated_wins = np.clip(projection - sampled_errors[idx], 0, 17)
        rounded_wins = np.rint(simulated_wins)

        prob_over = float(np.mean(rounded_wins > market_total))
        prob_under = float(np.mean(rounded_wins < market_total))
        prob_push = float(np.mean(rounded_wins == market_total))
        row = {
            "season": int(rec["season"]) if "season" in rec else 2026,
            "team": rec["team"],
            "warps_wins": round(projection, 3),
            "market_total": market_total,
            "edge": round(projection - market_total, 3),
            "mean_wins": round(float(np.mean(simulated_wins)), 3),
            "median_wins": round(float(np.median(simulated_wins)), 2),
            "p10_wins": pct(simulated_wins, 10),
            "p25_wins": pct(simulated_wins, 25),
            "p75_wins": pct(simulated_wins, 75),
            "p90_wins": pct(simulated_wins, 90),
            "prob_over": round(prob_over, 4),
            "prob_under": round(prob_under, 4),
            "prob_push": round(prob_push, 4),
            "prob_10_plus": round(float(np.mean(rounded_wins >= 10)), 4),
            "prob_12_plus": round(float(np.mean(rounded_wins >= 12)), 4),
            "prob_6_or_less": round(float(np.mean(rounded_wins <= 6)), 4),
            "simulations": sims,
        }
        rows.append(row)

    out = pd.DataFrame(rows)
    out["direction"] = out.apply(direction, axis=1)
    out["tier"] = out.apply(signal_tier, axis=1)
    out = out.sort_values(["tier", "prob_over", "edge"], ascending=[True, False, False])

    metadata = {
        "model": "WARPS v2.3",
        "season": 2026,
        "simulations": sims,
        "seed": seed,
        "residual_source": residuals_path.name,
        "projection_source": screen_path.name,
        "residual_count": int(len(residuals)),
        "residual_mean": round(float(np.mean(residuals)), 4),
        "residual_std": round(float(np.std(residuals, ddof=0)), 4),
        "method": "Empirical residual bootstrap: simulated wins = WARPS projection - sampled historical WARPS error, clipped to 0-17 and rounded for market-side probabilities.",
    }
    return out, metadata


def write_site_json(path: Path, rows: pd.DataFrame, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "teams": rows.to_dict(orient="records"),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WARPS Monte Carlo win distributions.")
    parser.add_argument("--screen", type=Path, default=DEFAULT_SCREEN)
    parser.add_argument("--residuals", type=Path, default=DEFAULT_RESIDUALS)
    parser.add_argument("--sims", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260714)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--site-json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    rows, metadata = build_simulation(args.screen, args.residuals, args.sims, args.seed)
    args.csv_output.write_text(rows.to_csv(index=False, quoting=csv.QUOTE_MINIMAL))
    write_site_json(args.site_json, rows, metadata)

    strongest = rows.sort_values("prob_over", ascending=False).head(3)
    weakest = rows.sort_values("prob_under", ascending=False).head(3)
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.site_json}")
    print("Top over probabilities:")
    for row in strongest.itertuples():
        print(f"  {row.team}: {row.prob_over:.1%} over {row.market_total}")
    print("Top under probabilities:")
    for row in weakest.itertuples():
        print(f"  {row.team}: {row.prob_under:.1%} under {row.market_total}")


if __name__ == "__main__":
    main()
