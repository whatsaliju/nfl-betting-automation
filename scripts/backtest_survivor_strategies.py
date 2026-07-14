#!/usr/bin/env python3
"""Backtest survivor-pool selection policies against historical NFL markets."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET_SPINE = ROOT / "data" / "historical" / "nfl_market_spine.csv"
DEFAULT_JSON = ROOT / "data" / "historical" / "survivor_backtest_report.json"
DEFAULT_MD = ROOT / "data" / "historical" / "survivor_backtest_report.md"
DEFAULT_SEASONS = "2015-2025"
TEAM_ALIASES = {"WSH": "WAS", "LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"}


def canonical_team(team: str | None) -> str:
    value = str(team or "").strip()
    return TEAM_ALIASES.get(value, value)


def parse_float(value) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def parse_int(value) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def parse_seasons(value: str) -> list[int]:
    seasons: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            seasons.update(range(int(start), int(end) + 1))
        else:
            seasons.add(int(part))
    return sorted(seasons)


def read_rows(path: Path, seasons: set[int]) -> list[dict]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        row for row in rows
        if parse_int(row.get("season")) in seasons and row.get("game_type") == "REG"
    ]


def team_spread(row: dict, side: str) -> float | None:
    key = "home_spread_line" if side == "home" else "away_spread_line"
    return parse_float(row.get(key))


def build_candidates(rows: list[dict]) -> list[dict]:
    raw = []
    for row in rows:
        season = parse_int(row.get("season"))
        week = parse_int(row.get("week"))
        if season is None or week is None:
            continue
        away = canonical_team(row.get("away_team"))
        home = canonical_team(row.get("home_team"))
        winner = canonical_team(row.get("straight_up_winner_team"))
        for side, team, opponent, prob_key in (
            ("away", away, home, "away_ml_no_vig_prob"),
            ("home", home, away, "home_ml_no_vig_prob"),
        ):
            prob = parse_float(row.get(prob_key))
            if prob is None:
                continue
            spread = team_spread(row, side)
            raw.append({
                "season": season,
                "week": week,
                "team": team,
                "opponent": opponent,
                "matchup_key": row.get("matchup_key"),
                "home_away": side,
                "win_probability": prob,
                "team_spread": spread,
                "division_game": str(row.get("div_game") or "0") == "1",
                "winner": winner,
                "won": team == winner,
                "market_favorite": bool(spread is not None and spread < 0),
                "low_margin_spot": bool(spread is None or spread > -3.5),
            })

    by_season_team: dict[tuple[int, str], list[dict]] = {}
    for row in raw:
        by_season_team.setdefault((row["season"], row["team"]), []).append(row)

    candidates = []
    for row in raw:
        future = [
            item for item in by_season_team.get((row["season"], row["team"]), [])
            if item["week"] > row["week"]
        ]
        future_probs = [item["win_probability"] for item in future]
        future_safe = [prob for prob in future_probs if prob >= 0.62]
        future_elite = [prob for prob in future_probs if prob >= 0.70]
        best_future = max(future_probs) if future_probs else None
        future_cost = len(future_safe) * 1.2 + len(future_elite) * 2.5
        if best_future is not None:
            future_cost += max(0.0, best_future - row["win_probability"]) * 18

        volatility = 0.0
        if row["division_game"]:
            volatility += 3.0
        if row["home_away"] == "away":
            volatility += 3.5
        if row["low_margin_spot"]:
            volatility += 2.0
        if row["win_probability"] < 0.55:
            volatility += 4.0

        row["future_safe_spots"] = len(future_safe)
        row["future_elite_spots"] = len(future_elite)
        row["best_future_win_probability"] = best_future
        row["future_value_cost"] = round(future_cost, 3)
        row["volatility_penalty"] = round(volatility, 3)
        row["survivor_score"] = round(row["win_probability"] * 100 - future_cost - volatility, 3)
        row["leverage_score"] = round(row["survivor_score"] - max(0, row["win_probability"] - 0.70) * 20, 3)
        candidates.append(row)
    return candidates


def choose_weekly(candidates: list[dict], season: int, week: int, used: set[str], strategy: str) -> dict | None:
    rows = [
        row for row in candidates
        if row["season"] == season and row["week"] == week and row["team"] not in used
    ]
    if not rows:
        return None
    if strategy == "highest_win_prob":
        return max(rows, key=lambda row: (row["win_probability"], row["market_favorite"], -row["future_value_cost"], row["team"]))
    if strategy == "survivor_adjusted":
        return max(rows, key=lambda row: (row["survivor_score"], row["win_probability"], row["team"]))
    if strategy == "avoid_risky":
        safe = [
            row for row in rows
            if row["win_probability"] >= 0.56 and not row["division_game"] and row["team_spread"] is not None and row["team_spread"] <= -2.5
        ]
        pool = safe or rows
        return max(pool, key=lambda row: (row["survivor_score"], row["win_probability"], row["team"]))
    raise ValueError(f"Unknown strategy: {strategy}")


def optimized_path(candidates: list[dict], season: int, weeks: list[int], beam_size: int = 6000) -> list[dict]:
    by_week = {
        week: sorted(
            [
                row for row in candidates
                if row["season"] == season and row["week"] == week and row["win_probability"] >= 0.50
            ],
            key=lambda row: (-row["survivor_score"], -row["win_probability"], row["team"]),
        )[:18]
        for week in weeks
    }
    paths = [{"used": set(), "picks": [], "log_survival": 0.0, "score": 0.0}]
    for week in weeks:
        next_paths = []
        for path in paths:
            for row in by_week.get(week, []):
                if row["team"] in path["used"]:
                    continue
                next_paths.append({
                    "used": path["used"] | {row["team"]},
                    "picks": path["picks"] + [row],
                    "log_survival": path["log_survival"] + math.log(max(row["win_probability"], 0.001)),
                    "score": path["score"] + row["survivor_score"] / 1000,
                })
        next_paths.sort(key=lambda path: path["log_survival"] + path["score"], reverse=True)
        paths = next_paths[:beam_size]
        if not paths:
            break
    return paths[0]["picks"] if paths else []


def simulate_strategy(candidates: list[dict], season: int, weeks: list[int], strategy: str) -> dict:
    if strategy == "future_path_optimizer":
        picks = optimized_path(candidates, season, weeks)
    else:
        used: set[str] = set()
        picks = []
        for week in weeks:
            pick = choose_weekly(candidates, season, week, used, strategy)
            if not pick:
                break
            picks.append(pick)
            used.add(pick["team"])

    alive = True
    loss_week = None
    graded_picks = []
    for pick in picks:
        if alive and not pick["won"]:
            alive = False
            loss_week = pick["week"]
        graded_picks.append({
            "week": pick["week"],
            "team": pick["team"],
            "opponent": pick["opponent"],
            "home_away": pick["home_away"],
            "win_probability": round(pick["win_probability"], 4),
            "team_spread": pick["team_spread"],
            "survivor_score": pick["survivor_score"],
            "division_game": pick["division_game"],
            "low_margin_spot": pick["low_margin_spot"],
            "won": pick["won"],
            "alive_after_pick": alive if pick["week"] <= (loss_week or 999) else False,
        })

    survived_weeks = len(weeks) if alive and len(picks) == len(weeks) else max(0, (loss_week or weeks[0]) - weeks[0])
    average_pick_probability = sum(p["win_probability"] for p in picks) / len(picks) if picks else None
    path_probability = math.prod(max(p["win_probability"], 0.001) for p in picks) if picks else None
    loss_pick = next((pick for pick in graded_picks if pick["week"] == loss_week), None)
    return {
        "season": season,
        "strategy": strategy,
        "alive": alive and len(picks) == len(weeks),
        "loss_week": loss_week,
        "loss_pick": loss_pick,
        "survived_weeks": survived_weeks,
        "picks_made": len(picks),
        "average_pick_probability": round(average_pick_probability, 4) if average_pick_probability is not None else None,
        "path_market_probability": round(path_probability, 8) if path_probability is not None else None,
        "picks": graded_picks,
    }


def summarize(results: list[dict]) -> list[dict]:
    out = []
    strategies = sorted({row["strategy"] for row in results})
    for strategy in strategies:
        rows = [row for row in results if row["strategy"] == strategy]
        seasons = len(rows)
        full_survivals = sum(1 for row in rows if row["alive"])
        avg_survived = sum(row["survived_weeks"] for row in rows) / seasons if seasons else 0
        avg_loss_week = sum(row["loss_week"] or (row["picks_made"] + 1) for row in rows) / seasons if seasons else 0
        best_single = max((row["survived_weeks"] for row in rows), default=0)
        loss_weeks = [row["loss_week"] for row in rows if row["loss_week"] is not None]
        common_loss_week = max(set(loss_weeks), key=loss_weeks.count) if loss_weeks else None
        out.append({
            "strategy": strategy,
            "seasons": seasons,
            "full_survivals": full_survivals,
            "full_survival_rate": round(full_survivals / seasons, 4) if seasons else None,
            "avg_survived_weeks": round(avg_survived, 2),
            "avg_loss_week_or_finish": round(avg_loss_week, 2),
            "best_single_season_survived_weeks": best_single,
            "most_common_loss_week": common_loss_week,
            "best_seasons": [row["season"] for row in rows if row["alive"]],
        })
    out.sort(key=lambda row: (row["full_survivals"], row["avg_survived_weeks"]), reverse=True)
    return out


def build_report(market_spine: Path, seasons: list[int]) -> dict:
    rows = read_rows(market_spine, set(seasons))
    candidates = build_candidates(rows)
    weeks_by_season = {
        season: sorted({row["week"] for row in candidates if row["season"] == season})
        for season in seasons
    }
    strategies = ["highest_win_prob", "survivor_adjusted", "avoid_risky", "future_path_optimizer"]
    results = []
    for season in seasons:
        weeks = weeks_by_season.get(season) or []
        if not weeks:
            continue
        for strategy in strategies:
            results.append(simulate_strategy(candidates, season, weeks, strategy))
    return {
        "metadata": {
            "model": "Survivor historical strategy backtest v0.1",
            "source": str(market_spine),
            "seasons": seasons,
            "strategy_count": len(strategies),
            "candidate_count": len(candidates),
            "method": "Uses historical no-vig moneyline probabilities as pregame win probabilities; grades against actual straight-up winners.",
        },
        "summary": summarize(results),
        "season_results": results,
    }


def write_md(path: Path, report: dict) -> None:
    lines = [
        "# Survivor Strategy Backtest",
        "",
        f"- Source: `{report['metadata']['source']}`",
        f"- Seasons: {report['metadata']['seasons'][0]}-{report['metadata']['seasons'][-1]}",
        f"- Candidates: {report['metadata']['candidate_count']}",
        f"- Method: {report['metadata']['method']}",
        "",
        "| Strategy | Seasons | Full Survivals | Survival Rate | Avg Survived Weeks | Best Seasons |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in report["summary"]:
        lines.append(
            f"| {row['strategy']} | {row['seasons']} | {row['full_survivals']} | "
            f"{row['full_survival_rate']:.1%} | {row['avg_survived_weeks']:.2f} | "
            f"{', '.join(map(str, row['best_seasons'])) or 'none'} |"
        )
    lines.extend([
        "",
        "| Strategy | Best Single Season | Most Common Loss Week |",
        "|---|---:|---:|",
    ])
    for row in report["summary"]:
        lines.append(
            f"| {row['strategy']} | {row['best_single_season_survived_weeks']} | "
            f"{row['most_common_loss_week'] or 'n/a'} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `highest_win_prob` is the pure safety baseline.",
        "- `survivor_adjusted` applies future-value, road, division, low-margin, and low-probability penalties.",
        "- `avoid_risky` is stricter about division games and short favorites.",
        "- `future_path_optimizer` builds the highest full-season path using a beam search over weekly market probabilities.",
        "",
        "This is a strategy and plumbing backtest, not a betting-edge proof. It uses market probabilities as the win-probability source so the comparison tests selection policy rather than whether we can beat the market.",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-spine", type=Path, default=DEFAULT_MARKET_SPINE)
    parser.add_argument("--seasons", default=DEFAULT_SEASONS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    seasons = parse_seasons(args.seasons)
    report = build_report(args.market_spine, seasons)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2) + "\n")
    write_md(args.md_output, report)
    print(json.dumps({
        "seasons": seasons,
        "candidate_count": report["metadata"]["candidate_count"],
        "best_strategy": report["summary"][0] if report["summary"] else None,
    }, indent=2))


if __name__ == "__main__":
    main()
