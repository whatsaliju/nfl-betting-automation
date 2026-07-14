#!/usr/bin/env python3
"""Build a 2026 NFL survivor-pool recommendation board from WARPS game priors."""

import argparse
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEDULE = ROOT / "site" / "src" / "data" / "seasonSchedules.json"
DEFAULT_WARPS = ROOT / "site" / "src" / "data" / "warpsMarketOverlay2026.json"
DEFAULT_JSON = ROOT / "data" / "historical" / "survivor_recommendations_2026.json"
DEFAULT_CSV = ROOT / "data" / "historical" / "survivor_recommendations_2026.csv"
DEFAULT_MD = ROOT / "data" / "historical" / "survivor_recommendations_2026.md"
DEFAULT_SITE_JSON = ROOT / "site" / "src" / "data" / "survivorRecommendations2026.json"


def clean_opponent(value):
    return (value or "").replace("@", "").strip()


def game_key(week, away, home):
    return f"{week}:{away}@{home}"


def schedule_context(schedule, week, team, opponent, home_away):
    rows = {row["Team"]: row for row in schedule["scheduleRows"]}
    team_stats = schedule.get("teamStats") or {}
    game_days = schedule.get("gameDays") or {}
    day = (game_days.get(str(week)) or {}).get(team) or "Sun"
    is_division = same_division(team, opponent)
    opp_sos = (team_stats.get(opponent) or {}).get("sos")
    return {
        "day": day,
        "home_away": home_away,
        "division_game": is_division,
        "opponent_sos_rank": opp_sos,
        "team_has_bye_before": previous_week_value(rows, team, week) == "BYE",
        "opponent_has_bye_before": previous_week_value(rows, opponent, week) == "BYE",
    }


DIVISIONS = {
    "AFC East": {"BUF", "MIA", "NE", "NYJ"},
    "AFC North": {"BAL", "CIN", "CLE", "PIT"},
    "AFC South": {"HOU", "IND", "JAX", "TEN"},
    "AFC West": {"DEN", "KC", "LAC", "LV"},
    "NFC East": {"DAL", "NYG", "PHI", "WAS"},
    "NFC North": {"CHI", "DET", "GB", "MIN"},
    "NFC South": {"ATL", "CAR", "NO", "TB"},
    "NFC West": {"ARI", "LAR", "SEA", "SF"},
}


def same_division(left, right):
    return any(left in teams and right in teams for teams in DIVISIONS.values())


def previous_week_value(rows, team, week):
    if week <= 1:
        return None
    row = rows.get(team) or {}
    return row.get(f"W{week - 1}")


def future_profile(candidates_by_team, team, week):
    future = [row for row in candidates_by_team.get(team, []) if row["week"] > week]
    future_probs = [row["win_probability"] for row in future]
    future_safe = [prob for prob in future_probs if prob >= 0.62]
    future_elite = [prob for prob in future_probs if prob >= 0.70]
    best = max(future_probs) if future_probs else None
    return {
        "future_safe_spots": len(future_safe),
        "future_elite_spots": len(future_elite),
        "best_future_win_probability": best,
    }


def risk_band(probability, division_game, home_away):
    if probability >= 0.72 and not division_game:
        return "premium"
    if probability >= 0.66:
        return "strong"
    if probability >= 0.60:
        return "usable"
    if probability >= 0.55 and home_away == "home":
        return "thin"
    return "avoid"


def recommendation_tier(row):
    if row["survivor_score"] >= 66 and row["win_probability"] >= 0.64:
        return "primary"
    if row["survivor_score"] >= 60 and row["win_probability"] >= 0.60:
        return "secondary"
    if row["win_probability"] >= 0.56:
        return "deep_pool"
    return "avoid"


def reasons(row):
    out = []
    out.append(f"WARPS win probability {row['win_probability']:.1%}")
    if row["home_away"] == "home":
        out.append("Home-field survivor spot")
    else:
        out.append("Road favorite requires extra caution")
    if row["division_game"]:
        out.append("Division game raises upset volatility")
    if row["future_safe_spots"] == 0:
        out.append("Low future opportunity cost")
    elif row["future_elite_spots"]:
        out.append(f"Save risk: {row['future_elite_spots']} future elite spot(s)")
    if row["opponent_has_bye_before"]:
        out.append("Opponent off bye")
    if row["team_has_bye_before"]:
        out.append("Team off bye")
    return out[:5]


def build_candidates(schedule, warps_rows):
    raw = []
    for game in warps_rows:
        if game.get("season") != 2026:
            continue
        week = int(game["week"])
        away = game["away_tla"]
        home = game["home_tla"]
        for team, opponent, prob_key, side in (
            (home, away, "home_win_prob", "home"),
            (away, home, "away_win_prob", "away"),
        ):
            prob = float(game[prob_key])
            context = schedule_context(schedule, week, team, opponent, side)
            raw.append({
                "season": 2026,
                "week": week,
                "team": team,
                "opponent": opponent,
                "matchup_key": f"{away}@{home}",
                "game_key": game_key(week, away, home),
                "home_away": side,
                "day": context["day"],
                "win_probability": prob,
                "fair_moneyline": game["home_fair_moneyline"] if side == "home" else game["away_fair_moneyline"],
                "warps_wins": game["home_warps_wins"] if side == "home" else game["away_warps_wins"],
                "opponent_warps_wins": game["away_warps_wins"] if side == "home" else game["home_warps_wins"],
                "division_game": context["division_game"],
                "opponent_sos_rank": context["opponent_sos_rank"],
                "team_has_bye_before": context["team_has_bye_before"],
                "opponent_has_bye_before": context["opponent_has_bye_before"],
            })

    by_team = {}
    for row in raw:
        by_team.setdefault(row["team"], []).append(row)

    candidates = []
    for row in raw:
        future = future_profile(by_team, row["team"], row["week"])
        row.update(future)
        future_cost = 0.0
        if row["best_future_win_probability"]:
            future_cost += max(0.0, row["best_future_win_probability"] - row["win_probability"]) * 18
        future_cost += row["future_safe_spots"] * 1.2 + row["future_elite_spots"] * 2.5
        volatility = 0.0
        if row["division_game"]:
            volatility += 3.0
        if row["home_away"] == "away":
            volatility += 3.5
        if row["opponent_has_bye_before"]:
            volatility += 2.0
        if row["team_has_bye_before"]:
            volatility -= 1.0
        safety = row["win_probability"] * 100
        row["future_value_cost"] = round(future_cost, 2)
        row["volatility_penalty"] = round(volatility, 2)
        row["safety_score"] = round(safety, 2)
        row["survivor_score"] = round(safety - future_cost - volatility, 2)
        row["risk_band"] = risk_band(row["win_probability"], row["division_game"], row["home_away"])
        row["tier"] = recommendation_tier(row)
        row["reasons"] = reasons(row)
        candidates.append(row)

    return sorted(
        candidates,
        key=lambda row: (row["week"], -row["survivor_score"], -row["win_probability"], row["team"]),
    )


def build_weekly(candidates):
    weekly = []
    for week in range(1, 19):
        rows = [row for row in candidates if row["week"] == week]
        rows.sort(key=lambda row: (-row["survivor_score"], -row["win_probability"], row["team"]))
        safe_rows = sorted(rows, key=lambda row: (-row["win_probability"], row["future_value_cost"], row["team"]))
        weekly.append({
            "week": week,
            "primary": rows[0] if rows else None,
            "safest": safe_rows[0] if safe_rows else None,
            "alternatives": rows[1:6],
            "avoid": [row for row in rows if row["risk_band"] == "avoid"][:6],
        })
    return weekly


def build_path(candidates, beam_size=4000):
    by_week = {
        week: sorted(
            [row for row in candidates if row["week"] == week and row["win_probability"] >= 0.54],
            key=lambda row: (-row["survivor_score"], -row["win_probability"]),
        )[:16]
        for week in range(1, 19)
    }
    paths = [{
        "used": set(),
        "picks": [],
        "log_survival": 0.0,
        "strategy_score": 0.0,
    }]
    for week in range(1, 19):
        next_paths = []
        for path in paths:
            for row in by_week[week]:
                if row["team"] in path["used"]:
                    continue
                next_paths.append({
                    "used": path["used"] | {row["team"]},
                    "picks": path["picks"] + [row],
                    "log_survival": path["log_survival"] + math.log(max(row["win_probability"], 0.001)),
                    "strategy_score": path["strategy_score"] + row["survivor_score"] / 1000,
                })
        next_paths.sort(key=lambda path: path["log_survival"] + path["strategy_score"], reverse=True)
        paths = next_paths[:beam_size]
        if not paths:
            break
    if not paths:
        return {"available": False, "picks": [], "survival_probability": None}
    best = paths[0]
    return {
        "available": True,
        "survival_probability": round(math.exp(best["log_survival"]), 6),
        "average_pick_probability": round(math.exp(best["log_survival"] / len(best["picks"])), 4),
        "picks": best["picks"],
    }


def flatten(row):
    out = dict(row)
    out["reasons"] = "; ".join(row.get("reasons") or [])
    return out


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(flatten(rows[0]).keys()) if rows else []
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(flatten(row) for row in rows)


def write_md(path, payload):
    lines = [
        "# 2026 Survivor Recommendations",
        "",
        f"- Model: {payload['metadata']['model']}",
        f"- Games scored: {payload['metadata']['candidate_count']}",
        "",
        "| Week | Pick | Game | Win Prob | Survivor Score | Tier | Reasons |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for week in payload["weekly"]:
        pick = week["primary"]
        if not pick:
            continue
        lines.append(
            f"| {week['week']} | {pick['team']} | {pick['matchup_key']} | "
            f"{pick['win_probability']:.1%} | {pick['survivor_score']:.1f} | {pick['tier']} | "
            f"{'; '.join(pick.get('reasons') or [])} |"
        )
    path.write_text("\n".join(lines) + "\n")


def build_payload(schedule, warps_rows):
    candidates = build_candidates(schedule, warps_rows)
    weekly = build_weekly(candidates)
    path = build_path(candidates)
    return {
        "metadata": {
            "season": 2026,
            "model": "WARPS survivor intelligence v0.1",
            "source": "WARPS game priors + schedule matrix context",
            "policy": "Maximize win probability while penalizing future opportunity cost and volatility.",
            "candidate_count": len(candidates),
        },
        "weekly": weekly,
        "optimal_path": path,
        "candidates": candidates,
    }


def site_payload(payload):
    return {
        "metadata": payload["metadata"],
        "optimal_path": payload["optimal_path"],
        "candidates": payload["candidates"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE)
    parser.add_argument("--warps", type=Path, default=DEFAULT_WARPS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--site-json-output", type=Path, default=DEFAULT_SITE_JSON)
    args = parser.parse_args()

    schedules = json.loads(args.schedule.read_text())
    schedule = schedules["2026"]
    warps_rows = json.loads(args.warps.read_text())
    payload = build_payload(schedule, warps_rows)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2) + "\n")
    args.site_json_output.write_text(json.dumps(site_payload(payload), separators=(",", ":")) + "\n")
    write_csv(args.csv_output, payload["candidates"])
    write_md(args.md_output, payload)
    print(json.dumps({
        "candidate_count": payload["metadata"]["candidate_count"],
        "week1_primary": payload["weekly"][0]["primary"]["team"],
        "path_survival_probability": payload["optimal_path"]["survival_probability"],
    }, indent=2))


if __name__ == "__main__":
    main()
