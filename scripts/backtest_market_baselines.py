#!/usr/bin/env python3
"""Build market-only NFL baselines from the historical market spine.

This is the control group for the betting engine. It does not use WARPS,
injuries, refs, weather, sharp splits, or selector scores. It simply asks how
blind market segments performed across spread, total, and moneyline prices.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET_SPINE = ROOT / "data" / "historical" / "nfl_market_spine.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "backtests" / "historical_market_baselines"


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


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def american_profit_per_unit(odds: float | None) -> float | None:
    if odds is None:
        return None
    return odds / 100 if odds > 0 else 100 / abs(odds)


def roi_for_result(odds: float | None, result: str) -> float | None:
    profit = american_profit_per_unit(odds)
    if profit is None or result not in {"win", "loss", "push"}:
        return None
    if result == "push":
        return 0.0
    return profit if result == "win" else -1.0


def side_pick(row: dict, market: str, side: str) -> dict | None:
    if market == "spread":
        if side == "AWAY":
            odds = parse_float(row.get("away_spread_odds"))
            result = row.get("away_cover_result") or ""
            line = parse_float(row.get("away_spread_line"))
            team = row.get("away_team")
        elif side == "HOME":
            odds = parse_float(row.get("home_spread_odds"))
            result = row.get("home_cover_result") or ""
            line = parse_float(row.get("home_spread_line"))
            team = row.get("home_team")
        elif side == "FAVORITE":
            fav = row.get("favorite_side")
            return side_pick(row, market, fav) if fav in {"AWAY", "HOME"} else None
        elif side == "UNDERDOG":
            fav = row.get("favorite_side")
            dog = "HOME" if fav == "AWAY" else "AWAY" if fav == "HOME" else ""
            return side_pick(row, market, dog) if dog else None
        else:
            return None
    elif market == "total":
        if side == "OVER":
            odds = parse_float(row.get("over_odds"))
            result = row.get("over_result") or ""
        elif side == "UNDER":
            odds = parse_float(row.get("under_odds"))
            result = row.get("under_result") or ""
        else:
            return None
        line = parse_float(row.get("total_line"))
        team = ""
    elif market == "moneyline":
        if side == "AWAY":
            odds = parse_float(row.get("away_moneyline"))
            result = row.get("away_ml_result") or ""
            line = odds
            team = row.get("away_team")
        elif side == "HOME":
            odds = parse_float(row.get("home_moneyline"))
            result = row.get("home_ml_result") or ""
            line = odds
            team = row.get("home_team")
        elif side == "FAVORITE":
            away = parse_float(row.get("away_moneyline"))
            home = parse_float(row.get("home_moneyline"))
            if away is None or home is None:
                return None
            return side_pick(row, market, "AWAY" if away < home else "HOME")
        elif side == "UNDERDOG":
            away = parse_float(row.get("away_moneyline"))
            home = parse_float(row.get("home_moneyline"))
            if away is None or home is None:
                return None
            return side_pick(row, market, "AWAY" if away > home else "HOME")
        else:
            return None
    else:
        return None

    roi = roi_for_result(odds, result)
    if roi is None:
        return None
    return {
        "season": parse_int(row.get("season")),
        "game_type": row.get("game_type") or "",
        "week": parse_int(row.get("week")),
        "game_id": row.get("game_id") or "",
        "matchup_key": row.get("matchup_key") or "",
        "market": market,
        "side": side,
        "team": team or "",
        "line_or_price": line if line is not None else "",
        "odds": odds if odds is not None else "",
        "result": result,
        "roi": round(roi, 4),
        "favorite_side": row.get("favorite_side") or "",
        "favorite_spread": parse_float(row.get("favorite_spread")),
        "total_line": parse_float(row.get("total_line")),
        "div_game": row.get("div_game") or "",
        "roof": row.get("roof") or "",
        "surface": row.get("surface") or "",
        "temp": parse_float(row.get("temp")),
        "wind": parse_float(row.get("wind")),
    }


def spread_bucket(value: float | None) -> str:
    if value is None:
        return "missing"
    value = abs(value)
    if value <= 2.5:
        return "pick_to_2.5"
    if value <= 6.5:
        return "3_to_6.5"
    if value <= 9.5:
        return "7_to_9.5"
    return "10_plus"


def total_bucket(value: float | None) -> str:
    if value is None:
        return "missing"
    if value <= 40:
        return "40_or_less"
    if value <= 44.5:
        return "40.5_to_44.5"
    if value <= 49.5:
        return "45_to_49.5"
    return "50_plus"


def moneyline_bucket(odds: float | None, side: str) -> str:
    if odds is None:
        return "missing"
    if side == "FAVORITE":
        price = abs(odds)
        if price < 120:
            return "pick_to_119"
        if price < 150:
            return "120_to_149"
        if price < 200:
            return "150_to_199"
        if price < 300:
            return "200_to_299"
        return "300_plus"
    price = odds
    if price < 120:
        return "pick_to_119"
    if price < 150:
        return "120_to_149"
    if price < 200:
        return "150_to_199"
    if price < 300:
        return "200_to_299"
    return "300_plus"


def annotate_pick(pick: dict) -> dict:
    market = pick["market"]
    side = pick["side"]
    line = parse_float(pick.get("line_or_price"))
    favorite_spread = parse_float(pick.get("favorite_spread"))
    total_line = parse_float(pick.get("total_line"))
    out = dict(pick)
    out["spread_bucket"] = spread_bucket(favorite_spread)
    out["total_bucket"] = total_bucket(total_line)
    out["moneyline_bucket"] = moneyline_bucket(line, side) if market == "moneyline" and side in {"FAVORITE", "UNDERDOG"} else ""
    out["home_away_bucket"] = "home" if side == "HOME" else "away" if side == "AWAY" else ""
    out["game_type_bucket"] = "postseason" if pick.get("game_type") != "REG" else "regular"
    out["division_bucket"] = "division" if str(pick.get("div_game")) == "1" else "non_division"
    return out


def build_picks(rows: list[dict]) -> list[dict]:
    picks = []
    for row in rows:
        for market, sides in (
            ("spread", ("AWAY", "HOME", "FAVORITE", "UNDERDOG")),
            ("total", ("OVER", "UNDER")),
            ("moneyline", ("AWAY", "HOME", "FAVORITE", "UNDERDOG")),
        ):
            for side in sides:
                pick = side_pick(row, market, side)
                if pick:
                    picks.append(annotate_pick(pick))
    return picks


def summarize(rows: list[dict]) -> dict:
    wins = sum(1 for row in rows if row["result"] == "win")
    losses = sum(1 for row in rows if row["result"] == "loss")
    pushes = sum(1 for row in rows if row["result"] == "push")
    decisions = wins + losses
    roi_values = [parse_float(row.get("roi")) for row in rows if parse_float(row.get("roi")) is not None]
    units = sum(roi_values)
    by_season = defaultdict(float)
    for row in rows:
        season = row.get("season")
        roi = parse_float(row.get("roi"))
        if season is not None and roi is not None:
            by_season[season] += roi
    profitable = sum(1 for value in by_season.values() if value > 0)
    return {
        "plays": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(wins / decisions, 4) if decisions else None,
        "units": round(units, 4),
        "roi_per_play": round(units / len(roi_values), 4) if roi_values else None,
        "profitable_season_pct": round(profitable / len(by_season), 4) if by_season else None,
    }


def bucket_summary(picks: list[dict], section: str, fields: tuple[str, ...], predicate=lambda row: True) -> list[dict]:
    buckets = defaultdict(list)
    for row in picks:
        if not predicate(row):
            continue
        key = tuple(str(row.get(field) or "NONE") for field in fields)
        buckets[key].append(row)
    output = []
    for key, rows in sorted(buckets.items()):
        output.append({
            "section": section,
            "bucket": " / ".join(key),
            **summarize(rows),
        })
    return output


def build_summary_rows(picks: list[dict]) -> list[dict]:
    rows = []
    rows.extend(bucket_summary(picks, "market_side", ("market", "side")))
    rows.extend(bucket_summary(picks, "market_side_regular", ("market", "side"), lambda row: row["game_type_bucket"] == "regular"))
    rows.extend(bucket_summary(picks, "market_side_postseason", ("market", "side"), lambda row: row["game_type_bucket"] == "postseason"))
    rows.extend(bucket_summary(picks, "spread_bucket", ("side", "spread_bucket"), lambda row: row["market"] == "spread" and row["side"] in {"FAVORITE", "UNDERDOG"}))
    rows.extend(bucket_summary(picks, "total_bucket", ("side", "total_bucket"), lambda row: row["market"] == "total"))
    rows.extend(bucket_summary(picks, "moneyline_bucket", ("side", "moneyline_bucket"), lambda row: row["market"] == "moneyline" and row["side"] in {"FAVORITE", "UNDERDOG"}))
    rows.extend(bucket_summary(picks, "market_by_season", ("market", "season")))
    return rows


def best_and_worst(summary_rows: list[dict], min_plays: int) -> tuple[list[dict], list[dict]]:
    candidates = [
        row for row in summary_rows
        if row["plays"] >= min_plays and row["roi_per_play"] is not None
    ]
    best = sorted(candidates, key=lambda row: (row["roi_per_play"], row["plays"]), reverse=True)[:12]
    worst = sorted(candidates, key=lambda row: (row["roi_per_play"], -row["plays"]))[:12]
    return best, worst


def markdown_report(payload: dict, summary_rows: list[dict]) -> str:
    lines = [
        "# Historical Market Baseline Backtest",
        "",
        "This is the control group for the NFL betting engine. It tests blind market segments from the historical market spine before any WARPS, injury, referee, weather, sharp-split, or selector logic is applied.",
        "",
        "## Coverage",
        "",
        f"- Market spine: `{payload['market_spine']}`",
        f"- Rows: {payload['rows']}",
        f"- Seasons: {payload['seasons'][0]}-{payload['seasons'][-1]}",
        f"- Includes postseason: {payload['include_postseason']}",
        "",
        "## Takeaway",
        "",
        payload["takeaway"],
        "",
        "## Best Baseline Buckets",
        "",
        "| Section | Bucket | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["best_buckets"]:
        lines.append(summary_line(row))
    lines.extend([
        "",
        "## Worst Baseline Buckets",
        "",
        "| Section | Bucket | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["worst_buckets"]:
        lines.append(summary_line(row))
    lines.extend([
        "",
        "## Market Side Summary",
        "",
        "| Section | Bucket | Plays | W-L-P | Win Rate | Units | ROI/Play | Profitable Seasons |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in summary_rows:
        if row["section"] == "market_side":
            lines.append(summary_line(row))
    lines.extend([
        "",
        "## Promotion Rule",
        "",
        "A weekly model factor should only be promoted if it beats these market-only baselines out of sample, after source-health gates and realistic listed odds are applied.",
        "",
    ])
    return "\n".join(lines)


def summary_line(row: dict) -> str:
    wl = f"{row['wins']}-{row['losses']}-{row['pushes']}"
    win_rate = "" if row["win_rate"] is None else f"{row['win_rate']:.1%}"
    units = f"{row['units']:+.2f}"
    roi = "" if row["roi_per_play"] is None else f"{row['roi_per_play']:+.2%}"
    prof = "" if row["profitable_season_pct"] is None else f"{row['profitable_season_pct']:.1%}"
    return f"| {row['section']} | {row['bucket']} | {row['plays']} | {wl} | {win_rate} | {units} | {roi} | {prof} |"


def build_payload(market_spine: Path, rows: list[dict], picks: list[dict], summary_rows: list[dict], min_plays: int) -> dict:
    seasons = sorted({parse_int(row.get("season")) for row in rows if parse_int(row.get("season")) is not None})
    best, worst = best_and_worst(summary_rows, min_plays)
    market_side = [row for row in summary_rows if row["section"] == "market_side"]
    takeaway = (
        "Blind market buckets are controls, not betting edges. Use them to judge whether WARPS/engine factors add signal beyond baseline market behavior."
    )
    return {
        "market_spine": str(market_spine),
        "rows": len(rows),
        "picks_scored": len(picks),
        "seasons": seasons,
        "include_postseason": any(row.get("game_type") != "REG" for row in rows),
        "min_plays_for_best_worst": min_plays,
        "takeaway": takeaway,
        "market_side_summary": market_side,
        "best_buckets": best,
        "worst_buckets": worst,
        "output_policy": {
            "uses_model_edges": False,
            "uses_warps": False,
            "uses_weekly_engine": False,
            "purpose": "control_group_for_future_spread_total_moneyline_edge_tests",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest historical market-only NFL baselines")
    parser.add_argument("--market-spine", type=Path, default=DEFAULT_MARKET_SPINE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-plays", type=int, default=100)
    args = parser.parse_args()

    rows = read_csv(args.market_spine)
    picks = build_picks(rows)
    summary_rows = build_summary_rows(picks)
    payload = build_payload(args.market_spine, rows, picks, summary_rows, args.min_plays)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "market_baseline_picks.csv", picks)
    write_csv(args.output_dir / "market_baseline_summary.csv", summary_rows)
    (args.output_dir / "market_baseline_summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    (args.output_dir / "market_baseline_report.md").write_text(markdown_report(payload, summary_rows) + "\n")

    print(json.dumps({
        "rows": len(rows),
        "picks_scored": len(picks),
        "summary": str(args.output_dir / "market_baseline_summary.json"),
        "best_bucket": payload["best_buckets"][0] if payload["best_buckets"] else None,
    }, indent=2))


if __name__ == "__main__":
    main()
