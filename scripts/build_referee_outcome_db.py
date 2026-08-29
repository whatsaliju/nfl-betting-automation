#!/usr/bin/env python3
"""
Build a game-level referee outcome database from nflverse schedules.

Produces data/historical/referee_outcome_db.csv — one row per graded game
with the actual referee, favorite side, ATS result, and O/U result.
This is the foundation for backtesting how much referee ATS history
matters as an edge signal.
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
DEFAULT_OUTPUT = ROOT / "data" / "historical" / "referee_outcome_db.csv"


def build(since: int = 2000, output: Path = DEFAULT_OUTPUT) -> pd.DataFrame:
    usecols = [
        "season", "game_type", "week", "game_id", "gameday",
        "away_team", "home_team", "away_score", "home_score",
        "spread_line", "total_line", "div_game", "referee",
    ]
    print("Downloading nflverse schedules…")
    df = pd.read_csv(SCHEDULES_URL, usecols=usecols)
    df = df[df["game_type"].isin(["REG", "POST", "WC", "DIV", "CON", "SB"])].copy()
    df = df[df["season"] >= since].copy()
    df = df.dropna(subset=["referee", "away_score", "home_score", "spread_line", "total_line"])
    df = df[df["spread_line"] != 0].copy()  # drop pick'em (no defined favorite)

    # nflverse spread_line: positive = away underdog / home favorite
    #                       negative = away favorite / home underdog
    df["favorite_side"] = df["spread_line"].apply(lambda x: "HF" if x > 0 else "AF")

    # ATS cover margin from the favorite's perspective
    df["home_margin"] = df["home_score"] - df["away_score"]
    df["away_margin"] = df["away_score"] - df["home_score"]
    df["home_cover_margin"] = df["home_margin"] - df["spread_line"]   # HF side
    df["away_cover_margin"] = df["away_margin"] + df["spread_line"]   # AF side

    def favorite_cover(row):
        if row["favorite_side"] == "HF":
            m = row["home_cover_margin"]
        else:
            m = row["away_cover_margin"]
        if m > 0:
            return "win"
        if m < 0:
            return "loss"
        return "push"

    df["favorite_ats"] = df.apply(favorite_cover, axis=1)

    game_total = df["away_score"] + df["home_score"]
    ou_margin = game_total - df["total_line"]
    df["ou_result"] = ou_margin.apply(lambda x: "over" if x > 0 else ("under" if x < 0 else "push"))
    df["actual_total"] = game_total
    df["favorite_cover_margin"] = df.apply(
        lambda r: r["home_cover_margin"] if r["favorite_side"] == "HF" else r["away_cover_margin"],
        axis=1,
    )

    out = df[[
        "game_id", "season", "game_type", "week", "gameday",
        "away_team", "home_team", "away_score", "home_score",
        "spread_line", "total_line", "actual_total", "div_game",
        "referee", "favorite_side",
        "favorite_ats", "favorite_cover_margin",
        "ou_result",
    ]].copy()

    out = out.sort_values(["season", "week", "game_id"]).reset_index(drop=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)

    print(f"Saved {len(out):,} games → {output}")
    seasons = sorted(out["season"].unique())
    print(f"Seasons: {seasons[0]}–{seasons[-1]}")
    win_pct = (out["favorite_ats"] == "win").mean()
    print(f"Overall favorite ATS win rate: {win_pct:.1%}")
    refs = out["referee"].nunique()
    print(f"Unique referees: {refs}")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=int, default=2000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(since=args.since, output=args.output)


if __name__ == "__main__":
    main()
