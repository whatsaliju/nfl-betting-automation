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
POOL_SIZES = (25, 100, 500)
PAYOUT_STYLES = ("top_heavy", "winner_take_all")
PUBLIC_PICK_SOURCE_CONTRACT = {
    "status": "estimated",
    "provider": "internal heuristic",
    "real_data_available": False,
    "method": "Derived from WARPS win probability, team brand chalk, home/road context, division volatility, and pool size.",
    "fields": ["public_pick_pct_25", "public_pick_pct_100", "public_pick_pct"],
}
LIVE_WIN_PROBABILITY_CONTRACT = {
    "status": "prior_only",
    "active_components": ["warps_prior", "schedule_context"],
    "missing_live_components": ["market_moneyline", "injury_qb_status", "weather", "public_survivor_pick_pct"],
    "policy": "Use WARPS priors for offseason planning; blend live market, injury, weather, and real public-pick inputs once weekly feeds publish.",
}
BRAND_CHALK = {
    "BUF": 4.5,
    "KC": 5.5,
    "PHI": 5.0,
    "DAL": 3.5,
    "SF": 4.5,
    "BAL": 4.0,
    "DET": 3.5,
    "GB": 3.0,
    "LAR": 2.5,
    "PIT": 2.5,
    "CIN": 2.5,
    "CHI": 2.0,
    "NE": 2.0,
    "DEN": 1.5,
}


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


def clamp(value, low, high):
    return max(low, min(high, value))


def public_pick_estimate(row, pool_size):
    favorite_component = max(0.0, row["win_probability"] - 0.55) * 62
    brand_component = BRAND_CHALK.get(row["team"], 0.0)
    home_component = 1.2 if row["home_away"] == "home" else -0.6
    pool_component = 1.5 if pool_size >= 100 else -1.2 if pool_size <= 15 else 0.0
    division_discount = -1.4 if row["division_game"] else 0.0
    return clamp(favorite_component + brand_component + home_component + pool_component + division_discount, 1.0, 38.0)


def payout_multiplier(style):
    if style == "winner_take_all":
        return 1.25
    if style == "flat":
        return 0.65
    return 1.0


def pool_ev_score(row, pool_size, payout_style, leverage_weight=0.75):
    public_pick = public_pick_estimate(row, pool_size)
    expected_eliminated = (public_pick / 100.0) * (1.0 - row["win_probability"]) * pool_size
    chalk_penalty = public_pick * payout_multiplier(payout_style)
    survival = row["win_probability"] * 100
    leverage = expected_eliminated * leverage_weight
    return survival + leverage - chalk_penalty * 0.18 - row["future_value_cost"] * 0.7 - row["volatility_penalty"] * 0.8


def pool_strategy_scores(row, pool_size, payout_style):
    public_pick = public_pick_estimate(row, pool_size)
    safe_score = row["win_probability"] * 100 - row["volatility_penalty"] * 0.8
    balanced_score = pool_ev_score(row, pool_size, payout_style, leverage_weight=0.75)
    leverage_score = pool_ev_score(row, pool_size, payout_style, leverage_weight=1.25)
    return {
        "pool_size": pool_size,
        "payout_style": payout_style,
        "public_pick_pct": round(public_pick, 2),
        "expected_entries_eliminated": round((public_pick / 100.0) * (1.0 - row["win_probability"]) * pool_size, 2),
        "safe_score": round(safe_score, 2),
        "balanced_score": round(balanced_score, 2),
        "leverage_score": round(leverage_score, 2),
    }


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
        row["win_probability_source_status"] = "warps_prior_only"
        row["live_win_probability"] = None
        row["live_win_probability_source_status"] = "missing"
        row["public_pick_source_status"] = "estimated"
        row["public_pick_pct_25"] = round(public_pick_estimate(row, 25), 2)
        row["public_pick_pct_100"] = round(public_pick_estimate(row, 100), 2)
        row["pool_ev_25_top_heavy"] = round(pool_ev_score(row, 25, "top_heavy", leverage_weight=0.75), 2)
        row["pool_ev_100_top_heavy"] = round(pool_ev_score(row, 100, "top_heavy", leverage_weight=0.75), 2)
        row["pool_ev_500_top_heavy"] = round(pool_ev_score(row, 500, "top_heavy", leverage_weight=0.75), 2)
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


def pick_for_strategy(rows, strategy, pool_size, payout_style):
    playable = [row for row in rows if row["tier"] != "avoid"]
    pool = playable or rows
    if not pool:
        return None
    if strategy == "safe":
        return max(pool, key=lambda row: (row["win_probability"], -row["volatility_penalty"], -row["future_value_cost"], row["team"]))
    if strategy == "leverage":
        return max(pool, key=lambda row: (pool_ev_score(row, pool_size, payout_style, leverage_weight=1.25), row["win_probability"], row["team"]))
    return max(pool, key=lambda row: (pool_ev_score(row, pool_size, payout_style, leverage_weight=0.75), row["win_probability"], row["team"]))


def pool_pick_payload(row, strategy, pool_size, payout_style):
    if not row:
        return None
    scores = pool_strategy_scores(row, pool_size, payout_style)
    return {
        "strategy": strategy,
        "pool_size": pool_size,
        "payout_style": payout_style,
        "team": row["team"],
        "opponent": row["opponent"],
        "week": row["week"],
        "matchup_key": row["matchup_key"],
        "home_away": row["home_away"],
        "win_probability": row["win_probability"],
        "survivor_score": row["survivor_score"],
        "future_value_cost": row["future_value_cost"],
        "volatility_penalty": row["volatility_penalty"],
        "risk_band": row["risk_band"],
        "tier": row["tier"],
        "division_game": row["division_game"],
        "public_pick_pct": scores["public_pick_pct"],
        "public_pick_source_status": "estimated",
        "expected_entries_eliminated": scores["expected_entries_eliminated"],
        "live_win_probability": row.get("live_win_probability"),
        "live_win_probability_source_status": row.get("live_win_probability_source_status"),
        "safe_score": scores["safe_score"],
        "balanced_score": scores["balanced_score"],
        "leverage_score": scores["leverage_score"],
        "reasons": row.get("reasons") or [],
    }


def build_pool_cards(candidates):
    cards = []
    for week in range(1, 19):
        rows = [row for row in candidates if row["week"] == week]
        for pool_size in POOL_SIZES:
            for payout_style in PAYOUT_STYLES:
                safe = pick_for_strategy(rows, "safe", pool_size, payout_style)
                balanced = pick_for_strategy(rows, "balanced", pool_size, payout_style)
                leverage = pick_for_strategy(rows, "leverage", pool_size, payout_style)
                cards.append({
                    "week": week,
                    "pool_size": pool_size,
                    "payout_style": payout_style,
                    "safe": pool_pick_payload(safe, "safe", pool_size, payout_style),
                    "balanced": pool_pick_payload(balanced, "balanced", pool_size, payout_style),
                    "leverage": pool_pick_payload(leverage, "leverage", pool_size, payout_style),
                })
    return cards


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
        f"- Win probability source: {payload['metadata']['live_win_probability_model']['status']} "
        f"({', '.join(payload['metadata']['live_win_probability_model']['active_components'])})",
        f"- Public pick source: {payload['metadata']['public_pick_source']['status']} "
        f"({payload['metadata']['public_pick_source']['provider']})",
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
    lines.extend([
        "",
        "## Pool-EV Card",
        "",
        "| Week | Pool | Payout | Safe | Balanced | Leverage |",
        "|---:|---:|---|---|---|---|",
    ])
    for card in payload.get("pool_cards", []):
        if card["payout_style"] != "top_heavy":
            continue
        safe = card.get("safe") or {}
        balanced = card.get("balanced") or {}
        leverage = card.get("leverage") or {}
        lines.append(
            f"| {card['week']} | {card['pool_size']} | {card['payout_style']} | "
            f"{safe.get('team', 'n/a')} ({safe.get('win_probability', 0):.1%}) | "
            f"{balanced.get('team', 'n/a')} ({balanced.get('balanced_score', 0):.1f}) | "
            f"{leverage.get('team', 'n/a')} ({leverage.get('public_pick_pct', 0):.1f}% public) |"
        )
    path.write_text("\n".join(lines) + "\n")


def build_payload(schedule, warps_rows):
    candidates = build_candidates(schedule, warps_rows)
    weekly = build_weekly(candidates)
    path = build_path(candidates)
    pool_cards = build_pool_cards(candidates)
    return {
        "metadata": {
            "season": 2026,
            "model": "WARPS survivor intelligence v0.1",
            "source": "WARPS game priors + schedule matrix context",
            "policy": "Maximize win probability while penalizing future opportunity cost and volatility.",
            "candidate_count": len(candidates),
            "public_pick_source": PUBLIC_PICK_SOURCE_CONTRACT,
            "live_win_probability_model": LIVE_WIN_PROBABILITY_CONTRACT,
        },
        "weekly": weekly,
        "optimal_path": path,
        "pool_cards": pool_cards,
        "candidates": candidates,
    }


def site_payload(payload):
    return {
        "metadata": payload["metadata"],
        "optimal_path": payload["optimal_path"],
        "pool_cards": payload["pool_cards"],
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
