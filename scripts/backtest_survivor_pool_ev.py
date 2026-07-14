#!/usr/bin/env python3
"""Simulate survivor-pool EV strategies with estimated public-pick behavior."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from backtest_survivor_strategies import (
    DEFAULT_MARKET_SPINE,
    DEFAULT_SEASONS,
    build_candidates,
    parse_seasons,
    read_rows,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "historical" / "survivor_pool_ev_backtest.json"
DEFAULT_MD = ROOT / "data" / "historical" / "survivor_pool_ev_backtest.md"
BRAND_CHALK = {
    "NE": 1.4,
    "DAL": 1.25,
    "GB": 1.2,
    "PIT": 1.18,
    "KC": 1.18,
    "PHI": 1.15,
    "BUF": 1.15,
    "SF": 1.14,
    "BAL": 1.12,
    "SEA": 1.1,
    "DEN": 1.08,
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def public_weight(row: dict) -> float:
    prob = row["win_probability"]
    spread = row.get("team_spread")
    spread_strength = max(0.0, abs(spread or 0.0)) / 8.0 if spread is not None and spread < 0 else 0.0
    favorite_gap = max(0.01, prob - 0.42)
    weight = favorite_gap ** 2.15 * (1.0 + spread_strength)
    if row["home_away"] == "home":
        weight *= 1.08
    if row["division_game"]:
        weight *= 0.88
    if row["low_margin_spot"]:
        weight *= 0.78
    weight *= BRAND_CHALK.get(row["team"], 1.0)
    return weight


def annotate_public_picks(candidates: list[dict]) -> None:
    grouped: dict[tuple[int, int], list[dict]] = {}
    for row in candidates:
        grouped.setdefault((row["season"], row["week"]), []).append(row)
    for rows in grouped.values():
        weights = [public_weight(row) for row in rows]
        total = sum(weights) or 1.0
        for row, weight in zip(rows, weights):
            row["public_weight"] = weight
            row["estimated_public_pick_pct"] = round(weight / total, 5)


def normalize_public_choices(rows: list[dict], used: set[str]) -> list[tuple[dict, float]]:
    choices = [row for row in rows if row["team"] not in used]
    weights = [row.get("public_weight") or public_weight(row) for row in choices]
    total = sum(weights)
    if total <= 0:
        return []
    return list(zip(choices, [weight / total for weight in weights]))


def weighted_choice(choices: list[tuple[dict, float]], rng: random.Random) -> dict | None:
    if not choices:
        return None
    roll = rng.random()
    cursor = 0.0
    for row, weight in choices:
        cursor += weight
        if roll <= cursor:
            return row
    return choices[-1][0]


def choose_our_pick(rows: list[dict], used: set[str], strategy: str, pool_size: int, payout_style: str) -> dict | None:
    choices = [row for row in rows if row["team"] not in used]
    if not choices:
        return None
    if strategy == "highest_win_prob":
        return max(choices, key=lambda row: (row["win_probability"], row["team"]))
    if strategy == "survivor_adjusted":
        return max(choices, key=lambda row: (row["survivor_score"], row["win_probability"], row["team"]))
    if strategy == "leverage":
        return max(choices, key=lambda row: (pool_ev_score(row, pool_size, payout_style, 1.25), row["win_probability"], row["team"]))
    if strategy == "pool_ev_balanced":
        return max(choices, key=lambda row: (pool_ev_score(row, pool_size, payout_style, 0.75), row["win_probability"], row["team"]))
    raise ValueError(f"Unknown strategy: {strategy}")


def payout_pressure(payout_style: str) -> float:
    if payout_style == "winner_take_all":
        return 1.25
    if payout_style == "flat":
        return 0.65
    return 1.0


def pool_ev_score(row: dict, pool_size: int, payout_style: str, leverage_weight: float) -> float:
    public_pct = row.get("estimated_public_pick_pct", 0.0)
    expected_eliminated = public_pct * (1.0 - row["win_probability"]) * pool_size
    chalk_penalty = public_pct * 100 * payout_pressure(payout_style)
    survival = row["win_probability"] * 100
    leverage = expected_eliminated * leverage_weight
    return survival + leverage - chalk_penalty * 0.18 - row["future_value_cost"] * 0.7 - row["volatility_penalty"] * 0.8


def simulate_pool(
    candidates_by_week: dict[int, list[dict]],
    weeks: list[int],
    strategy: str,
    pool_size: int,
    payout_style: str,
    max_public_entries: int,
    rng: random.Random,
) -> dict:
    simulated_public_entries = min(pool_size - 1, max_public_entries)
    our_used: set[str] = set()
    public_used = [set() for _ in range(simulated_public_entries)]
    our_alive = True
    public_alive = [True] * simulated_public_entries
    our_death_week: int | None = None
    public_death_weeks: list[int | None] = [None] * simulated_public_entries
    our_picks = []

    for week in weeks:
        rows = candidates_by_week.get(week, [])
        if our_alive:
            pick = choose_our_pick(rows, our_used, strategy, pool_size, payout_style)
            if pick is None:
                our_alive = False
                our_death_week = week
            else:
                our_used.add(pick["team"])
                our_picks.append({
                    "week": week,
                    "team": pick["team"],
                    "opponent": pick["opponent"],
                    "win_probability": round(pick["win_probability"], 4),
                    "public_pick_pct": round(pick.get("estimated_public_pick_pct", 0.0), 4),
                    "pool_ev_score": round(pool_ev_score(pick, pool_size, payout_style, 0.75), 3),
                    "won": pick["won"],
                })
                if not pick["won"]:
                    our_alive = False
                    our_death_week = week

        for index, alive in enumerate(public_alive):
            if not alive:
                continue
            choices = normalize_public_choices(rows, public_used[index])
            pick = weighted_choice(choices, rng)
            if pick is None:
                public_alive[index] = False
                public_death_weeks[index] = week
                continue
            public_used[index].add(pick["team"])
            if not pick["won"]:
                public_alive[index] = False
                public_death_weeks[index] = week

    finish_rank_week = max(weeks) + 1
    our_finish = finish_rank_week if our_alive else our_death_week or 0
    public_finish = [finish_rank_week if alive else death or 0 for alive, death in zip(public_alive, public_death_weeks)]
    best_finish = max([our_finish] + public_finish)
    tied_best = (1 if our_finish == best_finish else 0) + sum(1 for value in public_finish if value == best_finish)
    payout_share = (1.0 / tied_best) if our_finish == best_finish else 0.0
    simulated_pool_size = simulated_public_entries + 1
    roi_units = simulated_pool_size * payout_share - 1.0
    return {
        "won_pool": our_finish == best_finish,
        "outright_or_split_share": payout_share,
        "roi_units": roi_units,
        "our_finish_week": our_finish,
        "our_death_week": our_death_week,
        "public_survivors": sum(1 for value in public_finish if value == finish_rank_week),
        "simulated_pool_size": simulated_pool_size,
        "our_picks": our_picks,
    }


def summarize_trials(rows: list[dict]) -> dict:
    trials = len(rows)
    wins = sum(1 for row in rows if row["won_pool"])
    avg_share = sum(row["outright_or_split_share"] for row in rows) / trials if trials else 0.0
    avg_roi = sum(row["roi_units"] for row in rows) / trials if trials else 0.0
    avg_finish = sum(row["our_finish_week"] for row in rows) / trials if trials else 0.0
    return {
        "trials": trials,
        "pool_win_or_split_rate": round(wins / trials, 4) if trials else None,
        "avg_payout_share": round(avg_share, 5),
        "avg_roi_units": round(avg_roi, 4),
        "avg_finish_week": round(avg_finish, 2),
    }


def run_scenario(
    candidates: list[dict],
    season: int,
    strategy: str,
    pool_size: int,
    payout_style: str,
    trials: int,
    seed: int,
    max_public_entries: int,
) -> dict:
    weeks = sorted({row["week"] for row in candidates if row["season"] == season})
    by_week = {
        week: [row for row in candidates if row["season"] == season and row["week"] == week]
        for week in weeks
    }
    trial_rows = []
    for trial in range(trials):
        rng = random.Random(seed + season * 100000 + pool_size * 1000 + trial)
        trial_rows.append(simulate_pool(by_week, weeks, strategy, pool_size, payout_style, max_public_entries, rng))
    summary = summarize_trials(trial_rows)
    sample = max(trial_rows, key=lambda row: (row["roi_units"], row["our_finish_week"]), default=None)
    return {
        "season": season,
        "strategy": strategy,
        "pool_size": pool_size,
        "simulated_public_entries": min(pool_size - 1, max_public_entries),
        "payout_style": payout_style,
        **summary,
        "sample_best_path": sample["our_picks"] if sample else [],
    }


def aggregate(results: list[dict]) -> list[dict]:
    keys = sorted({(row["strategy"], row["pool_size"], row["payout_style"]) for row in results})
    out = []
    for strategy, pool_size, payout_style in keys:
        rows = [row for row in results if (row["strategy"], row["pool_size"], row["payout_style"]) == (strategy, pool_size, payout_style)]
        out.append({
            "strategy": strategy,
            "pool_size": pool_size,
            "simulated_public_entries": max(row.get("simulated_public_entries", 0) for row in rows),
            "payout_style": payout_style,
            "seasons": len(rows),
            "avg_pool_win_or_split_rate": round(sum(row["pool_win_or_split_rate"] for row in rows) / len(rows), 4),
            "avg_payout_share": round(sum(row["avg_payout_share"] for row in rows) / len(rows), 5),
            "avg_roi_units": round(sum(row["avg_roi_units"] for row in rows) / len(rows), 4),
            "avg_finish_week": round(sum(row["avg_finish_week"] for row in rows) / len(rows), 2),
        })
    out.sort(key=lambda row: (row["avg_roi_units"], row["avg_pool_win_or_split_rate"], row["avg_finish_week"]), reverse=True)
    return out


def build_report(market_spine: Path, seasons: list[int], trials: int, seed: int, max_public_entries: int) -> dict:
    rows = read_rows(market_spine, set(seasons))
    candidates = build_candidates(rows)
    annotate_public_picks(candidates)
    strategies = ["highest_win_prob", "survivor_adjusted", "pool_ev_balanced", "leverage"]
    pool_sizes = [25, 100, 500]
    payout_styles = ["top_heavy", "winner_take_all"]
    scenario_results = []
    for season in seasons:
        for pool_size in pool_sizes:
            size_trials = max(15, trials // 2) if pool_size >= 500 else trials
            for payout_style in payout_styles:
                for strategy in strategies:
                    scenario_results.append(run_scenario(candidates, season, strategy, pool_size, payout_style, size_trials, seed, max_public_entries))
    return {
        "metadata": {
            "model": "Survivor pool EV simulation v0.1",
            "source": str(market_spine),
            "seasons": seasons,
            "trials_per_scenario": trials,
            "max_public_entries": max_public_entries,
            "seed": seed,
            "candidate_count": len(candidates),
            "method": "Simulates public survivor entries using estimated pick popularity from no-vig moneyline probability, spread size, home field, division status, and brand chalk.",
        },
        "summary": aggregate(scenario_results),
        "scenario_results": scenario_results,
    }


def write_md(path: Path, report: dict) -> None:
    top_rows = report["summary"][:12]
    lines = [
        "# Survivor Pool EV Backtest",
        "",
        f"- Source: `{report['metadata']['source']}`",
        f"- Seasons: {report['metadata']['seasons'][0]}-{report['metadata']['seasons'][-1]}",
        f"- Trials per scenario: {report['metadata']['trials_per_scenario']}",
        f"- Method: {report['metadata']['method']}",
        "",
        "| Strategy | Pool | Sim Entries | Payout | Avg ROI Units | Win/Split Rate | Avg Share | Avg Finish Week |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in top_rows:
        lines.append(
            f"| {row['strategy']} | {row['pool_size']} | {row['simulated_public_entries']} | {row['payout_style']} | "
            f"{row['avg_roi_units']:.3f} | {row['avg_pool_win_or_split_rate']:.1%} | "
            f"{row['avg_payout_share']:.4f} | {row['avg_finish_week']:.2f} |"
        )
    lines.extend([
        "",
        "## Read",
        "",
        "- Positive ROI units means the simulated entry returned more than one buy-in on average within the bounded simulated field.",
        "- Large pool sizes still influence the pick score; `Sim Entries` shows the capped opponent field used for runtime.",
        "- This is a strategy backtest using estimated public pick behavior, not real historical pool-pick data.",
        "- If pool-EV beats highest-win-probability, the site should show a leverage pick next to the safe pick.",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-spine", type=Path, default=DEFAULT_MARKET_SPINE)
    parser.add_argument("--seasons", default=DEFAULT_SEASONS)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--max-public-entries", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260714)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    seasons = parse_seasons(args.seasons)
    report = build_report(args.market_spine, seasons, args.trials, args.seed, args.max_public_entries)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2) + "\n")
    write_md(args.md_output, report)
    print(json.dumps({
        "seasons": seasons,
        "candidate_count": report["metadata"]["candidate_count"],
        "best": report["summary"][0] if report["summary"] else None,
    }, indent=2))


if __name__ == "__main__":
    main()
