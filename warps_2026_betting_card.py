#!/usr/bin/env python3
"""Generate the 2026 WARPS gate-applied betting card."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
WARPS_DATA_TS = ROOT / "site" / "src" / "data" / "warpsData.ts"
MONTE_CARLO = ROOT / "warps_2026_monte_carlo.csv"
CSV_OUTPUT = ROOT / "warps_2026_betting_card.csv"
JSON_OUTPUT = ROOT / "site" / "src" / "data" / "warpsBettingCard2026.json"
MD_OUTPUT = ROOT / "warps_2026_betting_card.md"

CARD_PATTERN = re.compile(
    r'\{ team: "(?P<team>[^"]+)",\s*marketTotal:\s*(?P<market>[-\d.]+),\s*'
    r"v18Wins:\s*(?P<wins>[-\d.]+), v18Edge:\s*(?P<v23_edge>[-\d.]+),\s*"
    r"v15dEdge:\s*(?P<v15d_edge>[-\d.]+), v16Edge:\s*(?P<v16_edge>[-\d.]+),\s*"
    r'avgEdge:\s*(?P<avg_edge>[-\d.]+), consensus:\s*"(?P<consensus>[^"]+)",\s*'
    r"overOdds:\s*(?P<over_odds>[-\d]+), underOdds:\s*(?P<under_odds>[-\d]+)",
)


def implied_probability(odds: float) -> float:
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def no_vig_probabilities(over_odds: float, under_odds: float) -> tuple[float, float]:
    over = implied_probability(over_odds)
    under = implied_probability(under_odds)
    total = over + under
    return over / total, under / total


def american_profit(odds: float) -> float:
    return odds / 100 if odds > 0 else 100 / abs(odds)


def odds_label(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def fair_odds(probability: float) -> str:
    if probability <= 0 or probability >= 1:
        return "n/a"
    if probability >= 0.5:
        return f"-{round((probability / (1 - probability)) * 100)}"
    return f"+{round(((1 - probability) / probability) * 100)}"


def load_site_card_rows() -> pd.DataFrame:
    text = WARPS_DATA_TS.read_text()
    rows = []
    for match in CARD_PATTERN.finditer(text):
        row = match.groupdict()
        for key in ["market", "wins", "v23_edge", "v15d_edge", "v16_edge", "avg_edge"]:
            row[key] = float(row[key])
        for key in ["over_odds", "under_odds"]:
            row[key] = int(row[key])
        rows.append(row)
    if len(rows) != 32:
        raise SystemExit(f"Expected 32 site rows, found {len(rows)}")
    return pd.DataFrame(rows)


def gate_label(side: str, edge: float, price_edge: float, model_prob: float) -> tuple[str, str]:
    if side == "OVER" and edge >= 0.5 and price_edge >= 0.10 and model_prob >= 0.60:
        return "BET", "v2.3 over gate: edge>=0.5, price_edge>=10pp, model_prob>=60%"
    if side == "UNDER" and edge >= 0.5 and price_edge >= 0.05 and model_prob >= 0.50:
        return "BET", "v2.3 under gate: edge>=0.5, price_edge>=5pp"
    if edge >= 0.5 and price_edge >= 0.05:
        return "WATCH", "Partial gate: model and price agree, but historical side-specific gate is not fully met"
    return "PASS", "Historical betting gate not met"


def stake_tier(decision: str, edge: float, price_edge: float, model_prob: float, agreement_count: int) -> str:
    if decision != "BET":
        return "none"
    if edge >= 1.5 and price_edge >= 0.15 and model_prob >= 0.70 and agreement_count >= 3:
        return "core"
    if edge >= 1.0 and price_edge >= 0.10 and agreement_count >= 2:
        return "standard"
    return "small"


def build_card() -> pd.DataFrame:
    site_rows = load_site_card_rows()
    mc = pd.read_csv(MONTE_CARLO)
    merged = site_rows.merge(mc, left_on="team", right_on="team", how="inner", suffixes=("", "_mc"))
    rows = []
    for rec in merged.itertuples(index=False):
        edge = float(rec.v23_edge)
        side = "OVER" if edge > 0 else "UNDER" if edge < 0 else "PASS"
        if side == "PASS":
            model_prob = 0.0
            market_prob = 0.0
            odds = 0
            price_edge = 0.0
        else:
            over_no_vig, under_no_vig = no_vig_probabilities(rec.over_odds, rec.under_odds)
            model_prob = float(rec.prob_over if side == "OVER" else rec.prob_under)
            market_prob = over_no_vig if side == "OVER" else under_no_vig
            odds = int(rec.over_odds if side == "OVER" else rec.under_odds)
            price_edge = model_prob - market_prob

        edge_signs = [rec.v23_edge, rec.v15d_edge, rec.v16_edge]
        agreement_count = sum(1 for value in edge_signs if (value > 0 and side == "OVER") or (value < 0 and side == "UNDER"))
        decision, gate = gate_label(side, abs(edge), price_edge, model_prob)
        tier = stake_tier(decision, abs(edge), price_edge, model_prob, agreement_count)
        expected_roi = model_prob * american_profit(odds) - (1 - model_prob) if side != "PASS" else 0.0
        label_bits = []
        if decision == "BET":
            label_bits.append("Model + price")
        if agreement_count >= 3:
            label_bits.append("3-model consensus")
        elif agreement_count == 2:
            label_bits.append("2-model support")
        if abs(edge) < 1.0:
            label_bits.append("thin forecast edge")
        if price_edge < 0.10:
            label_bits.append("thin price edge")

        rows.append(
            {
                "team": rec.team,
                "decision": decision,
                "stake_tier": tier,
                "bet_side": side.title() if side != "PASS" else "Pass",
                "line": rec.market,
                "odds": odds_label(odds) if side != "PASS" else "",
                "warps_v23": round(float(rec.wins), 2),
                "edge": round(edge, 2),
                "avg_edge": round(float(rec.avg_edge), 2),
                "model_prob": round(model_prob, 4),
                "market_no_vig_prob": round(market_prob, 4),
                "price_edge": round(price_edge, 4),
                "fair_odds": fair_odds(model_prob) if side != "PASS" else "",
                "expected_roi": round(expected_roi, 4),
                "agreement_count": agreement_count,
                "consensus": rec.consensus,
                "gate": gate,
                "label": " / ".join(label_bits) if label_bits else "Manual review",
            }
        )

    order = {"BET": 0, "WATCH": 1, "PASS": 2}
    tier_order = {"core": 0, "standard": 1, "small": 2, "none": 3}
    out = pd.DataFrame(rows)
    out["_decision_order"] = out["decision"].map(order)
    out["_tier_order"] = out["stake_tier"].map(tier_order)
    out = out.sort_values(["_decision_order", "_tier_order", "expected_roi"], ascending=[True, True, False])
    return out.drop(columns=["_decision_order", "_tier_order"])


def write_markdown(card: pd.DataFrame) -> None:
    bets = card[card["decision"] == "BET"]
    watches = card[card["decision"] == "WATCH"]
    lines = [
        "# WARPS 2026 Betting Card",
        "",
        "Generated from WARPS v2.3 projections, 2026 Monte Carlo probabilities, and BetMGM lines embedded in the site data.",
        "",
        "Historical gates applied:",
        "- Over gate: edge >= 0.5, no-vig price edge >= 10pp, model probability >= 60%.",
        "- Under gate: edge >= 0.5, no-vig price edge >= 5%.",
        "",
        "## Bet Card",
        "",
        "| Team | Bet | Line | Odds | Tier | Model Prob | Price Edge | WARPS | Gate |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for rec in bets.itertuples(index=False):
        lines.append(
            f"| {rec.team} | {rec.bet_side} | {rec.line:.1f} | {rec.odds} | {rec.stake_tier} | "
            f"{rec.model_prob:.1%} | {rec.price_edge:.1%} | {rec.warps_v23:.2f} | {rec.label} |"
        )
    lines.extend(["", "## Watch List", "", "| Team | Lean | Line | Odds | Model Prob | Price Edge | Reason |", "|---|---:|---:|---:|---:|---:|---|"])
    for rec in watches.itertuples(index=False):
        lines.append(
            f"| {rec.team} | {rec.bet_side} | {rec.line:.1f} | {rec.odds} | {rec.model_prob:.1%} | "
            f"{rec.price_edge:.1%} | {rec.gate} |"
        )
    MD_OUTPUT.write_text("\n".join(lines) + "\n")


def main() -> None:
    card = build_card()
    CSV_OUTPUT.write_text(card.to_csv(index=False, quoting=csv.QUOTE_MINIMAL))
    JSON_OUTPUT.write_text(json.dumps(card.to_dict(orient="records"), indent=2) + "\n")
    write_markdown(card)
    print(f"Wrote {CSV_OUTPUT}")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    print("\nBet card:")
    print(card[card["decision"] == "BET"][["team", "bet_side", "line", "odds", "stake_tier", "model_prob", "price_edge", "edge", "label"]].to_string(index=False))


if __name__ == "__main__":
    main()
