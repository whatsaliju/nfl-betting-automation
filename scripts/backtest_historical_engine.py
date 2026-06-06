#!/usr/bin/env python3
"""Backtest reconstructable NFL betting factors across historical seasons.

This is intentionally separate from the live weekly engine. Historical seasons
do not have the same Action splits, injury snapshots, stage timing, or source
health state, so this script only uses inputs that can be reconstructed without
pretending we had live-week data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "backtests" / "historical_engine"
DEFAULT_SOURCE = ROOT / "data" / "historical" / "nflverse_games.csv"
TMP_SOURCE = Path("/private/tmp/nflverse_games.csv")
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
PYTHAGOREAN_EXPONENT = 2.37
CURRENT_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}
TEAM_ALIASES = {
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "WSH": "WAS",
}


@dataclass
class TeamState:
    games: int = 0
    wins: int = 0
    losses: int = 0
    points_for: float = 0.0
    points_against: float = 0.0

    def update(self, points_for: float, points_against: float) -> None:
        self.games += 1
        self.points_for += points_for
        self.points_against += points_against
        if points_for > points_against:
            self.wins += 1
        elif points_against > points_for:
            self.losses += 1

    @property
    def win_pct(self) -> float | None:
        return self.wins / self.games if self.games else None

    @property
    def pythagorean_pct(self) -> float | None:
        if not self.games:
            return None
        pf = max(self.points_for, 0) ** PYTHAGOREAN_EXPONENT
        pa = max(self.points_against, 0) ** PYTHAGOREAN_EXPONENT
        return pf / (pf + pa) if pf + pa else None

    @property
    def avg_total(self) -> float | None:
        if not self.games:
            return None
        return (self.points_for + self.points_against) / self.games


@dataclass
class RefState:
    games: int = 0
    overs: int = 0
    unders: int = 0
    pushes: int = 0

    def update(self, total_points: float, total_line: float | None) -> None:
        if total_line is None:
            return
        self.games += 1
        if total_points > total_line:
            self.overs += 1
        elif total_points < total_line:
            self.unders += 1
        else:
            self.pushes += 1

    @property
    def over_pct(self) -> float | None:
        decisions = self.overs + self.unders
        return self.overs / decisions if decisions else None


@dataclass
class LeagueState:
    games: int = 0
    total_points: float = 0.0

    def update(self, total_points: float) -> None:
        self.games += 1
        self.total_points += total_points

    @property
    def avg_total(self) -> float | None:
        return self.total_points / self.games if self.games else None


def canonical(team: str) -> str:
    return TEAM_ALIASES.get(str(team).strip(), str(team).strip())


def parse_float(value) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def american_roi(odds: float | None, won: bool, push: bool = False) -> float | None:
    if odds is None:
        return None
    if push:
        return 0.0
    if not won:
        return -1.0
    return odds / 100 if odds > 0 else 100 / abs(odds)


def american_implied_prob(odds: float | None) -> float | None:
    if odds is None:
        return None
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def normalize_probs(left: float | None, right: float | None) -> tuple[float | None, float | None]:
    if left is None or right is None or left + right <= 0:
        return None, None
    total = left + right
    return left / total, right / total


def read_games(path_or_url: str | Path) -> list[dict]:
    source = str(path_or_url)
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source, timeout=30) as response:
            text = response.read().decode("utf-8")
        return list(csv.DictReader(text.splitlines()))
    with Path(source).open(newline="") as f:
        return list(csv.DictReader(f))


def source_path(arg_source: str | None) -> str | Path:
    if arg_source:
        return arg_source
    if DEFAULT_SOURCE.exists():
        return DEFAULT_SOURCE
    if TMP_SOURCE.exists():
        return TMP_SOURCE
    return SCHEDULES_URL


def wanted_game(row: dict, seasons: set[int]) -> bool:
    season = parse_int(row.get("season"))
    if season not in seasons:
        return False
    if row.get("game_type") != "REG":
        return False
    away = canonical(row.get("away_team", ""))
    home = canonical(row.get("home_team", ""))
    return away in CURRENT_TEAMS and home in CURRENT_TEAMS


def game_sort_key(row: dict) -> tuple:
    return (
        parse_int(row.get("season")) or 0,
        row.get("gameday") or "",
        row.get("gametime") or "",
        row.get("game_id") or "",
    )


def grade_spread(pick_side: str, away_margin: float, spread_line: float | None) -> tuple[str, float | None]:
    if spread_line is None:
        return "missing_line", None
    # nflverse spread_line is from the away team's perspective.
    cover_margin = away_margin + spread_line if pick_side == "AWAY" else -(away_margin + spread_line)
    if cover_margin > 0:
        return "win", cover_margin
    if cover_margin < 0:
        return "loss", cover_margin
    return "push", 0.0


def grade_total(pick_side: str, total_points: float, total_line: float | None) -> tuple[str, float | None]:
    if total_line is None:
        return "missing_line", None
    margin = total_points - total_line if pick_side == "OVER" else total_line - total_points
    if margin > 0:
        return "win", margin
    if margin < 0:
        return "loss", margin
    return "push", 0.0


def grade_moneyline(pick_side: str, away_score: float, home_score: float) -> tuple[str, float | None]:
    if away_score == home_score:
        return "push", 0.0
    winner = "HOME" if home_score > away_score else "AWAY"
    return ("win" if pick_side == winner else "loss"), None


def pick_odds(row: dict, market: str, side: str) -> float | None:
    if market == "spread":
        return parse_float(row.get("home_spread_odds" if side == "HOME" else "away_spread_odds"))
    if market == "total":
        return parse_float(row.get("over_odds" if side == "OVER" else "under_odds"))
    if market == "moneyline":
        return parse_float(row.get("home_moneyline" if side == "HOME" else "away_moneyline"))
    return None


def add_pick(picks: list[dict], row: dict, policy: str, market: str, side: str, reason: str, signal_score: float | None, features: dict) -> None:
    away_score = parse_float(row.get("away_score"))
    home_score = parse_float(row.get("home_score"))
    if away_score is None or home_score is None:
        return

    spread_line = parse_float(row.get("spread_line"))
    total_line = parse_float(row.get("total_line"))
    total_points = away_score + home_score
    away_margin = away_score - home_score

    if market == "spread":
        result, margin = grade_spread(side, away_margin, spread_line)
    elif market == "total":
        result, margin = grade_total(side, total_points, total_line)
    elif market == "moneyline":
        result, margin = grade_moneyline(side, away_score, home_score)
    else:
        return

    odds = pick_odds(row, market, side)
    roi = american_roi(odds, result == "win", result == "push")
    away = canonical(row["away_team"])
    home = canonical(row["home_team"])
    picks.append({
        "season": parse_int(row.get("season")),
        "week": parse_int(row.get("week")),
        "game_id": row.get("game_id"),
        "gameday": row.get("gameday"),
        "policy": policy,
        "market": market,
        "side": side,
        "pick_team": home if side == "HOME" else away if side == "AWAY" else side,
        "away_team": away,
        "home_team": home,
        "away_score": away_score,
        "home_score": home_score,
        "spread_line": spread_line,
        "total_line": total_line,
        "odds": odds,
        "result": result,
        "margin": margin,
        "roi": roi,
        "signal_score": signal_score,
        "reason": reason,
        **features,
    })


def diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def maybe_add_policy_picks(picks: list[dict], row: dict, teams: dict, refs: dict, league: LeagueState, args) -> None:
    season = parse_int(row["season"])
    week = parse_int(row["week"])
    if season is None or week is None or week < args.min_week:
        return

    away = canonical(row["away_team"])
    home = canonical(row["home_team"])
    away_state = teams[(season, away)]
    home_state = teams[(season, home)]
    away_pyth = away_state.pythagorean_pct
    home_pyth = home_state.pythagorean_pct
    away_wp = away_state.win_pct
    home_wp = home_state.win_pct
    pyth_diff = diff(home_pyth, away_pyth)
    win_pct_diff = diff(home_wp, away_wp)
    rest_diff = diff(parse_float(row.get("home_rest")), parse_float(row.get("away_rest")))
    avg_total = league[season].avg_total
    team_total_avg = None
    if away_state.avg_total is not None and home_state.avg_total is not None:
        team_total_avg = (away_state.avg_total + home_state.avg_total) / 2

    features = {
        "home_pyth_pct": round(home_pyth, 4) if home_pyth is not None else "",
        "away_pyth_pct": round(away_pyth, 4) if away_pyth is not None else "",
        "pyth_diff_home": round(pyth_diff, 4) if pyth_diff is not None else "",
        "win_pct_diff_home": round(win_pct_diff, 4) if win_pct_diff is not None else "",
        "rest_diff_home": round(rest_diff, 2) if rest_diff is not None else "",
        "team_total_avg": round(team_total_avg, 2) if team_total_avg is not None else "",
        "league_total_avg": round(avg_total, 2) if avg_total is not None else "",
        "referee": row.get("referee") or "",
    }

    if pyth_diff is not None and abs(pyth_diff) >= args.pyth_spread_threshold:
        side = "HOME" if pyth_diff > 0 else "AWAY"
        add_pick(
            picks, row, "pyth_spread", "spread", side,
            f"prior pythagorean diff {pyth_diff:+.3f}",
            abs(pyth_diff),
            features,
        )

    if rest_diff is not None and abs(rest_diff) >= args.rest_threshold:
        side = "HOME" if rest_diff > 0 else "AWAY"
        add_pick(
            picks, row, "rest_spread", "spread", side,
            f"rest diff {rest_diff:+.1f} days",
            abs(rest_diff),
            features,
        )

    if pyth_diff is not None and win_pct_diff is not None and rest_diff is not None:
        score = (pyth_diff * 6.0) + (win_pct_diff * 2.0) + (rest_diff * 0.08)
        if abs(score) >= args.combined_spread_threshold:
            side = "HOME" if score > 0 else "AWAY"
            add_pick(
                picks, row, "combined_spread", "spread", side,
                f"combined pyth/win/rest score {score:+.2f}",
                abs(score),
                features,
            )

    if team_total_avg is not None and avg_total is not None:
        total_signal = team_total_avg - avg_total
        if abs(total_signal) >= args.total_form_threshold:
            side = "OVER" if total_signal > 0 else "UNDER"
            add_pick(
                picks, row, "team_total_form", "total", side,
                f"team total form vs league {total_signal:+.1f}",
                abs(total_signal),
                features,
            )

    referee = row.get("referee") or ""
    ref_state = refs[referee] if referee else None
    ref_over_pct = ref_state.over_pct if ref_state else None
    ref_features = {
        **features,
        "ref_games": ref_state.games if ref_state else "",
        "ref_over_pct": round(ref_over_pct, 4) if ref_over_pct is not None else "",
    }
    if ref_state and ref_state.games >= args.ref_min_games and ref_over_pct is not None:
        if ref_over_pct >= args.ref_over_threshold:
            add_pick(
                picks, row, "ref_total_trend", "total", "OVER",
                f"ref over rate {ref_over_pct:.1%} over {ref_state.games} games",
                ref_over_pct,
                ref_features,
            )
        elif ref_over_pct <= 1 - args.ref_over_threshold:
            add_pick(
                picks, row, "ref_total_trend", "total", "UNDER",
                f"ref under rate {1 - ref_over_pct:.1%} over {ref_state.games} games",
                1 - ref_over_pct,
                ref_features,
            )

    if pyth_diff is not None:
        home_raw_prob = min(max(0.5 + (pyth_diff * 0.80) + 0.03, 0.05), 0.95)
        away_model_prob = 1 - home_raw_prob
        home_market_prob, away_market_prob = normalize_probs(
            american_implied_prob(parse_float(row.get("home_moneyline"))),
            american_implied_prob(parse_float(row.get("away_moneyline"))),
        )
        if home_market_prob is not None and away_market_prob is not None:
            home_edge = home_raw_prob - home_market_prob
            away_edge = away_model_prob - away_market_prob
            if home_edge >= args.ml_edge_threshold:
                add_pick(
                    picks, row, "pyth_ml_value", "moneyline", "HOME",
                    f"model ML edge {home_edge:+.1%}",
                    home_edge,
                    {**features, "model_prob": round(home_raw_prob, 4), "market_prob": round(home_market_prob, 4)},
                )
            elif away_edge >= args.ml_edge_threshold:
                add_pick(
                    picks, row, "pyth_ml_value", "moneyline", "AWAY",
                    f"model ML edge {away_edge:+.1%}",
                    away_edge,
                    {**features, "model_prob": round(away_model_prob, 4), "market_prob": round(away_market_prob, 4)},
                )


def update_states(row: dict, teams: dict, refs: dict, leagues: dict) -> None:
    season = parse_int(row.get("season"))
    away = canonical(row.get("away_team", ""))
    home = canonical(row.get("home_team", ""))
    away_score = parse_float(row.get("away_score"))
    home_score = parse_float(row.get("home_score"))
    if season is None or away_score is None or home_score is None:
        return
    teams[(season, away)].update(away_score, home_score)
    teams[(season, home)].update(home_score, away_score)
    total_points = away_score + home_score
    leagues[season].update(total_points)
    referee = row.get("referee") or ""
    if referee:
        refs[referee].update(total_points, parse_float(row.get("total_line")))


def summarize(rows: list[dict]) -> dict:
    decisions = [row for row in rows if row["result"] in {"win", "loss"}]
    pushes = [row for row in rows if row["result"] == "push"]
    wins = sum(1 for row in decisions if row["result"] == "win")
    losses = len(decisions) - wins
    roi_rows = [row for row in rows if row.get("roi") not in (None, "")]
    roi = sum(float(row["roi"]) for row in roi_rows) if roi_rows else None
    return {
        "plays": len(rows),
        "graded": len(decisions) + len(pushes),
        "wins": wins,
        "losses": losses,
        "pushes": len(pushes),
        "win_rate": round(wins / len(decisions), 4) if decisions else None,
        "roi_units": round(roi, 4) if roi is not None else None,
        "roi_per_play": round(roi / len(roi_rows), 4) if roi_rows else None,
        "avg_signal_score": round(sum(float(row["signal_score"] or 0) for row in rows) / len(rows), 4) if rows else None,
    }


def grouped_summary(rows: list[dict], keys: Iterable[str]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    output = []
    for key_values, group_rows in sorted(groups.items()):
        item = {key: value for key, value in zip(keys, key_values)}
        item.update(summarize(group_rows))
        output.append(item)
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_backtest(games: list[dict], seasons: set[int], args) -> list[dict]:
    teams: dict[tuple[int, str], TeamState] = defaultdict(TeamState)
    refs: dict[str, RefState] = defaultdict(RefState)
    leagues: dict[int, LeagueState] = defaultdict(LeagueState)
    picks: list[dict] = []

    for row in sorted((row for row in games if wanted_game(row, seasons)), key=game_sort_key):
        maybe_add_policy_picks(picks, row, teams, refs, leagues, args)
        update_states(row, teams, refs, leagues)
    return picks


def parse_seasons(value: str) -> set[int]:
    seasons = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            seasons.update(range(int(start), int(end) + 1))
        else:
            seasons.add(int(part))
    return seasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest reconstructable NFL historical betting factors")
    parser.add_argument("--source", default=None, help="Path or URL for nflverse games.csv")
    parser.add_argument("--seasons", default="2015-2025")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--min-week", type=int, default=4)
    parser.add_argument("--pyth-spread-threshold", type=float, default=0.12)
    parser.add_argument("--rest-threshold", type=float, default=3.0)
    parser.add_argument("--combined-spread-threshold", type=float, default=1.0)
    parser.add_argument("--total-form-threshold", type=float, default=4.0)
    parser.add_argument("--ref-min-games", type=int, default=16)
    parser.add_argument("--ref-over-threshold", type=float, default=0.58)
    parser.add_argument("--ml-edge-threshold", type=float, default=0.06)
    args = parser.parse_args()

    seasons = parse_seasons(args.seasons)
    source = source_path(args.source)
    games = read_games(source)
    rows = run_backtest(games, seasons, args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "source": str(source),
        "source_url": SCHEDULES_URL,
        "seasons": sorted(seasons),
        "method": "historical_reconstructable_factors",
        "limitations": [
            "No Action public/sharp split history is included.",
            "No historical injury snapshot or live source-health state is included.",
            "All team form and referee trends are computed only from games before the tested game.",
        ],
        "thresholds": {
            "min_week": args.min_week,
            "pyth_spread_threshold": args.pyth_spread_threshold,
            "rest_threshold": args.rest_threshold,
            "combined_spread_threshold": args.combined_spread_threshold,
            "total_form_threshold": args.total_form_threshold,
            "ref_min_games": args.ref_min_games,
            "ref_over_threshold": args.ref_over_threshold,
            "ml_edge_threshold": args.ml_edge_threshold,
        },
        "overall": summarize(rows),
        "by_policy": grouped_summary(rows, ["policy"]),
        "by_policy_market": grouped_summary(rows, ["policy", "market"]),
        "by_season_policy": grouped_summary(rows, ["season", "policy"]),
    }

    write_csv(output_dir / "historical_engine_picks.csv", rows)
    write_csv(output_dir / "historical_engine_summary.csv", summary["by_policy_market"])
    (output_dir / "historical_engine_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps({
        "plays": summary["overall"]["plays"],
        "wins": summary["overall"]["wins"],
        "losses": summary["overall"]["losses"],
        "win_rate": summary["overall"]["win_rate"],
        "roi_units": summary["overall"]["roi_units"],
        "output_dir": str(output_dir),
    }, indent=2))
    print(f"Wrote {output_dir / 'historical_engine_picks.csv'}")
    print(f"Wrote {output_dir / 'historical_engine_summary.csv'}")
    print(f"Wrote {output_dir / 'historical_engine_summary.json'}")


if __name__ == "__main__":
    main()
