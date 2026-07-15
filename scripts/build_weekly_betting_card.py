#!/usr/bin/env python3
"""Build the user-facing weekly betting card from the matrix edge board."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEED = ROOT / "data" / "historical" / "matrix_engine_feed.json"
DEFAULT_JSON = ROOT / "data" / "historical" / "weekly_betting_card.json"
DEFAULT_CSV = ROOT / "data" / "historical" / "weekly_betting_card.csv"
DEFAULT_MD = ROOT / "data" / "historical" / "weekly_betting_card.md"


SOURCE_BAD = {"UNSAFE", "MISSING", "CRITICAL", "FAILED"}


def number_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def market_payload(game, market):
    return (game.get("markets") or {}).get(market) or {}


def selected_market(game):
    best = game.get("best_edge") or {}
    market = best.get("market")
    if market in {"spread", "total", "moneyline"}:
        return market_payload(game, market)
    return {}


def title_market(market):
    return "moneyline" if market == "moneyline" else market


def market_option(game, market):
    payload = market_payload(game, market)
    if market == "moneyline":
        warps = game.get("warps_market_overlay") or {}
        return {
            "market": market,
            "side": warps.get("ml_side"),
            "status": "research_only",
            "promotion_status": "not_promoted",
            "score": payload.get("score"),
            "threshold": payload.get("threshold"),
            "blockers": sorted(set((payload.get("blockers") or []) + ["moneyline selector not promoted"])),
            "signals": payload.get("signals") or [],
            "conflicts": payload.get("conflicts") or [],
            "warps_alignment": warps.get("ml_pick_alignment"),
            "warps_side": warps.get("ml_side"),
            "warps_team": warps.get("ml_team"),
            "edge_value": warps.get("ml_ev"),
        }
    warps = game.get("warps_market_overlay") or {}
    return {
        "market": market,
        "side": payload.get("side"),
        "status": payload.get("status") or "unavailable",
        "score": payload.get("score"),
        "threshold": payload.get("threshold"),
        "blockers": payload.get("blockers") or [],
        "signals": payload.get("signals") or [],
        "conflicts": payload.get("conflicts") or [],
        "warps_alignment": warps.get("spread_pick_alignment") if market == "spread" else None,
        "warps_side": warps.get("spread_side") if market == "spread" else None,
        "warps_team": warps.get("spread_team") if market == "spread" else None,
        "edge_value": warps.get("spread_edge_points") if market == "spread" else None,
    }


def market_options(game):
    return [market_option(game, market) for market in ("spread", "total", "moneyline")]


def route_summary(game, action, market, flags):
    options = market_options(game)
    playable = [row for row in options if row.get("status") in {"playable", "lean"} and row.get("side")]
    if action == "pass":
        if flags:
            reason = f"Blocked by risk/source flags: {', '.join(flags[:3])}"
        elif playable:
            reason = "Candidate markets did not clear the quality gate."
        else:
            reason = "No market cleared selector thresholds."
    elif market:
        selected = next((row for row in options if row["market"] == market), {})
        reason = (
            f"{title_market(market)} routed as best available market"
            f" with status {selected.get('status') or 'unknown'}"
        )
        if selected.get("warps_alignment") == "aligned":
            reason += "; WARPS agrees"
        elif selected.get("warps_alignment") == "conflict":
            reason += "; WARPS conflict keeps risk elevated"
    else:
        reason = "Watchlist only; no final market selected."
    return {
        "selected_market": market,
        "selected_reason": reason,
        "market_options": options,
    }


def line_hint(game, market, side):
    if market == "spread":
        warps = game.get("warps_market_overlay") or {}
        fair = warps.get("fair_away_spread") if side == "AWAY" else warps.get("fair_home_spread")
        if fair is not None:
            return f"Prefer {side} at a better number than WARPS fair {fair:+.1f}"
    if market == "total":
        return "Require current total to still match selector side before betting"
    if market == "moneyline":
        return "Research only until ML selector is promoted"
    return "No target line available"


def risk_flags(game, explanation):
    flags = []
    if game.get("source_health_status") in SOURCE_BAD:
        flags.append(f"source health {game.get('source_health_status')}")
    elif game.get("source_health_status") and game.get("source_health_status") != "OK":
        flags.append(f"source warning {game.get('source_health_status')}")
    if game.get("data_quality_status") in SOURCE_BAD:
        flags.append(f"data quality {game.get('data_quality_status')}")
    warps = game.get("warps_market_overlay") or {}
    if warps.get("spread_pick_alignment") == "conflict":
        flags.append("WARPS spread conflict")
    if (game.get("expectation_context") or {}).get("sample_warning"):
        flags.append("thin expectation sample")
    if explanation:
        if explanation.get("quality_gate") in {"warn", "blocked"}:
            flags.append(f"quality gate {explanation.get('quality_gate')}")
        flags.extend(explanation.get("source_blockers") or [])
    return flags[:6]


def action_for(game, explanation, flags):
    best = game.get("best_edge") or {}
    if not game.get("analysis_available"):
        return "pass"
    if explanation and explanation.get("quality_action"):
        action = explanation.get("quality_action")
        if action == "play" and any("source health" in flag or "data quality" in flag for flag in flags):
            return "watch"
        return action
    if best.get("status") == "play":
        return "watch" if flags else "play"
    return "pass"


def confidence_for(action, explanation, game):
    if explanation and explanation.get("confidence"):
        return explanation.get("confidence")
    if action == "play" and (game.get("best_edge") or {}).get("score"):
        return "standard"
    if action == "watch":
        return "watch"
    return "none"


def reasons_for(game, explanation, action):
    if action == "pass":
        return ["Selector did not clear an actionable market threshold"]
    reasons = []
    if explanation:
        reasons.extend(explanation.get("reasons") or [])
    best = game.get("best_edge") or {}
    if not reasons and best.get("recommendation"):
        reasons.append(best.get("recommendation"))
    if not reasons:
        reasons.append("No isolated selector edge")
    return reasons[:4]


def card_row(game):
    explanation = game.get("explanation") or {}
    best = game.get("best_edge") or {}
    market = best.get("market")
    market_data = selected_market(game) if market else {}
    side = best.get("side") or market_data.get("side")
    flags = risk_flags(game, explanation)
    action = action_for(game, explanation, flags)
    confidence = confidence_for(action, explanation, game)
    if action == "pass":
        market = None
        market_data = {}
        side = None
    route = route_summary(game, action, market, flags)
    return {
        "key": f"{game.get('season')}:{game.get('week')}:{game.get('matchup_key')}",
        "season": game.get("season"),
        "season_type": game.get("season_type"),
        "week": game.get("week"),
        "matchup_key": game.get("matchup_key"),
        "away_tla": game.get("away_tla"),
        "home_tla": game.get("home_tla"),
        "action": action,
        "market": market,
        "side": side,
        "confidence": confidence,
        "selector_score": None if action == "pass" else best.get("score"),
        "classification": None if action == "pass" else best.get("label"),
        "recommendation": None if action == "pass" else best.get("recommendation"),
        "required_line": "No bet" if action == "pass" else line_hint(game, market, side),
        "current_line": market_data.get("line") or "",
        "warps_alignment": (game.get("warps_market_overlay") or {}).get("spread_pick_alignment"),
        "warps_side": (game.get("warps_market_overlay") or {}).get("spread_side"),
        "source_health": game.get("source_health_status"),
        "data_quality": game.get("data_quality_status"),
        "quality_gate": explanation.get("quality_gate"),
        "main_reasons": reasons_for(game, explanation, action),
        "risk_flags": flags,
        "market_status": market_data.get("status"),
        "spread_status": market_payload(game, "spread").get("status"),
        "total_status": market_payload(game, "total").get("status"),
        "moneyline_status": "research_only",
        "moneyline_promotion_status": "not_promoted",
        "route_selected_market": route["selected_market"],
        "route_reason": route["selected_reason"],
        "market_options": route["market_options"],
    }


def sort_key(row):
    action_rank = {"play": 0, "watch": 1, "lean": 1, "pass": 2}
    return (
        action_rank.get(row.get("action"), 3),
        -(number_or_none(row.get("selector_score")) or 0),
        int(row.get("week") or 0),
        row.get("matchup_key") or "",
    )


def build(feed):
    rows = [card_row(game) for game in feed.get("edge_board", [])]
    rows.sort(key=sort_key)
    summary = {
        "feed_version": feed.get("feed_version"),
        "source": "matrix_engine_feed edge_board",
        "card_count": len(rows),
        "plays": sum(1 for row in rows if row["action"] == "play"),
        "watch": sum(1 for row in rows if row["action"] in {"watch", "lean"}),
        "passes": sum(1 for row in rows if row["action"] == "pass"),
    }
    return {
        **summary,
        "cards": rows,
    }


def flatten(row):
    output = dict(row)
    output["main_reasons"] = "; ".join(row.get("main_reasons") or [])
    output["risk_flags"] = "; ".join(row.get("risk_flags") or [])
    output["market_options"] = json.dumps(row.get("market_options") or [], separators=(",", ":"))
    return output


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    flat = [flatten(row) for row in rows]
    fields = list(flat[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(flat)


def write_md(path, payload):
    lines = [
        "# Weekly Betting Card",
        "",
        f"- Plays: {payload['plays']}",
        f"- Watch: {payload['watch']}",
        f"- Passes: {payload['passes']}",
        "",
        "| Week | Game | Action | Market | Side | Confidence | Route | Reasons | Risk |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["cards"]:
        lines.append(
            f"| {row['week']} | {row['matchup_key']} | {row['action']} | {row.get('market') or ''} | "
            f"{row.get('side') or ''} | {row['confidence']} | {row.get('route_reason') or ''} | "
            f"{'; '.join(row.get('main_reasons') or [])} | "
            f"{'; '.join(row.get('risk_flags') or [])} |"
        )
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, default=DEFAULT_FEED)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build(json.loads(args.feed.read_text()))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2))
    write_csv(args.csv_output, payload["cards"])
    write_md(args.md_output, payload)
    print(json.dumps({
        "cards": payload["card_count"],
        "plays": payload["plays"],
        "watch": payload["watch"],
        "passes": payload["passes"],
    }, indent=2))


if __name__ == "__main__":
    main()
