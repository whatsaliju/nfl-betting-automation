#!/usr/bin/env python3
"""
Build referee trend rows from public nflverse schedules.

This replaces the GimmeTheDog/SDQL Selenium loop while preserving the output
shape consumed by nfl_pro_analyzer.py and referee_trend_generator.py:

    query, su_record, su_pct, ats_record, ats_pct, ou_record, ou_pct

The old SDQL query asked: with referee X, when the favorite is home/away in a
division/conference/non-division game since 2018, what happened ATS and O/U?
The nflverse schedules file gives us referee, scores, spread_line, total_line,
and div_game, so we compute the same core tendency directly.
"""

import argparse
import os
import re
from functools import lru_cache
from typing import Optional

import pandas as pd

try:
    from analyzers.nfl_common import nflverse_game_types, normalize_season_type
except ImportError:
    from nfl_common import nflverse_game_types, normalize_season_type


SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
DEFAULT_OUTPUT = "data/historical/sdql_results.csv"


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", str(name).lower())


def pct(wins: int, losses: int) -> str:
    total = wins + losses
    if total <= 0:
        return "50.0%"
    return f"{(wins / total) * 100:.1f}%"


def record(wins: int, losses: int, pushes: int = 0) -> str:
    return f"{wins}-{losses}" + (f"-{pushes}" if pushes else "")


@lru_cache(maxsize=4)
def load_schedules(game_types=("REG",)) -> pd.DataFrame:
    usecols = [
        "season",
        "game_type",
        "week",
        "away_team",
        "away_score",
        "home_team",
        "home_score",
        "spread_line",
        "total_line",
        "total",
        "div_game",
        "referee",
    ]
    df = pd.read_csv(SCHEDULES_URL, usecols=usecols)
    df = df[df["game_type"].isin(game_types)].copy()
    df = df.dropna(subset=["referee", "away_score", "home_score", "spread_line", "total_line"])
    df["referee_key"] = df["referee"].apply(normalize_name)
    df["home_margin"] = df["home_score"] - df["away_score"]
    df["away_margin"] = df["away_score"] - df["home_score"]
    # nflverse spread_line is from the home-team perspective:
    # positive = home favored, negative = away favored.
    df["home_cover_margin"] = df["home_margin"] - df["spread_line"]
    df["away_cover_margin"] = df["away_margin"] + df["spread_line"]
    df["game_total"] = df["away_score"] + df["home_score"]
    return df


def find_referee_rows(df: pd.DataFrame, referee: str) -> pd.DataFrame:
    key = normalize_name(referee)
    rows = df[df["referee_key"].eq(key)]
    if not rows.empty:
        return rows

    # Fallback for middle initials, suffixes, or abbreviated first names.
    return df[
        df["referee_key"].apply(lambda candidate: key in candidate or candidate in key)
    ]


def apply_context_filters(rows: pd.DataFrame, favorite: str, game_type: str) -> pd.DataFrame:
    filtered = rows

    if favorite == "HF":
        filtered = filtered[filtered["spread_line"] > 0]
    elif favorite == "AF":
        filtered = filtered[filtered["spread_line"] < 0]
    elif favorite == "PK":
        filtered = filtered[filtered["spread_line"].abs() <= 0.5]

    if game_type == "DIV":
        filtered = filtered[filtered["div_game"].fillna(0).astype(int).eq(1)]
    elif game_type in {"C", "NDIV"}:
        # nflverse schedules has division flag, but not historical conference
        # membership by game. Treat both as non-division for a stable fallback.
        filtered = filtered[filtered["div_game"].fillna(0).astype(int).eq(0)]

    return filtered


def summarize_rows(rows: pd.DataFrame, favorite: str) -> dict:
    if rows.empty:
        return neutral_summary("No matching nflverse historical rows")

    if favorite == "AF":
        cover_margin = rows["away_cover_margin"]
        favorite_won = rows["away_score"] > rows["home_score"]
    else:
        cover_margin = rows["home_cover_margin"]
        favorite_won = rows["home_score"] > rows["away_score"]

    ats_wins = int((cover_margin > 0).sum())
    ats_losses = int((cover_margin < 0).sum())
    ats_pushes = int((cover_margin == 0).sum())

    over_margin = rows["game_total"] - rows["total_line"]
    ou_wins = int((over_margin > 0).sum())
    ou_losses = int((over_margin < 0).sum())
    ou_pushes = int((over_margin == 0).sum())

    su_wins = int(favorite_won.sum())
    su_losses = int((~favorite_won).sum())

    return {
        "su_record": record(su_wins, su_losses),
        "su_pct": pct(su_wins, su_losses),
        "ats_record": record(ats_wins, ats_losses, ats_pushes),
        "ats_pct": pct(ats_wins, ats_losses),
        "ou_record": record(ou_wins, ou_losses, ou_pushes),
        "ou_pct": pct(ou_wins, ou_losses),
        "sample_size": len(rows),
        "source": "nflverse schedules",
        "note": "",
    }


def neutral_summary(note: str) -> dict:
    return {
        "su_record": "0-0",
        "su_pct": "50.0%",
        "ats_record": "0-0",
        "ats_pct": "50.0%",
        "ou_record": "0-0",
        "ou_pct": "50.0%",
        "sample_size": 0,
        "source": "nflverse schedules",
        "note": note,
    }


def build_referee_trends(
    week: int,
    since: int = 2018,
    output: str = DEFAULT_OUTPUT,
    min_sample: int = 5,
    write_week_copy: bool = True,
    season_type: str = None,
) -> pd.DataFrame:
    season_type = normalize_season_type(season_type, week)
    queries_path = f"data/week{week}/week{week}_queries.csv"
    if not os.path.exists(queries_path):
        raise FileNotFoundError(f"Missing query file: {queries_path}")

    queries = pd.read_csv(queries_path)
    game_types = tuple(nflverse_game_types(season_type))
    schedules = load_schedules(game_types)
    schedules = schedules[schedules["season"] >= since].copy()

    out_rows = []
    for _, query_row in queries.iterrows():
        referee = query_row.get("referee", "")
        favorite = query_row.get("favorite", "HF")
        game_type = query_row.get("game_type", "NDIV")

        ref_rows = find_referee_rows(schedules, referee)
        context_rows = apply_context_filters(ref_rows, favorite, game_type)

        summary = summarize_rows(context_rows, favorite)
        if summary["sample_size"] < min_sample:
            broader_rows = apply_context_filters(ref_rows, favorite, "")
            broader_summary = summarize_rows(broader_rows, favorite)
            if broader_summary["sample_size"] > summary["sample_size"]:
                summary = broader_summary
                summary["note"] = (
                    f"Broadened sample because {favorite}/{game_type} "
                    f"had fewer than {min_sample} games"
                )

        summary.update(
            {
                "query": query_row.get("query", ""),
                "referee": referee,
                "favorite": favorite,
                "game_type": game_type,
            }
        )
        out_rows.append(summary)

    out = pd.DataFrame(out_rows)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    out.to_csv(output, index=False)

    week_output = f"data/week{week}/week{week}_nflverse_referee_trends.csv"
    if write_week_copy:
        os.makedirs(os.path.dirname(week_output), exist_ok=True)
        out.to_csv(week_output, index=False)

    print(f"Saved referee trend rows to {output}")
    if write_week_copy:
        print(f"Saved week copy to {week_output}")
    print(out[["referee", "favorite", "game_type", "sample_size", "ats_pct", "ou_pct"]].to_string(index=False))
    return out


def main():
    parser = argparse.ArgumentParser(description="Build referee trends from nflverse schedules")
    parser.add_argument("week", type=int)
    parser.add_argument("--since", type=int, default=2018)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--min-sample", type=int, default=5)
    parser.add_argument("--season-type", default=None, help="REG or POST. Defaults to POST for weeks above 18.")
    args = parser.parse_args()

    build_referee_trends(
        week=args.week,
        since=args.since,
        output=args.output,
        min_sample=args.min_sample,
        write_week_copy=True,
        season_type=args.season_type,
    )


if __name__ == "__main__":
    main()
