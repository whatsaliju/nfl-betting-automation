#!/usr/bin/env python3
"""Stability audit for WARPS betting gates and the 2026 card."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
BETS = ROOT / "warps_betting_value_bets.csv"
CARD = ROOT / "warps_2026_betting_card.csv"
REPORT_JSON = ROOT / "warps_betting_stability_report.json"
REPORT_MD = ROOT / "warps_betting_stability_report.md"
GATE_AUDIT_CSV = ROOT / "warps_betting_gate_stability.csv"
CARD_AUDIT_CSV = ROOT / "warps_2026_card_stability_audit.csv"


GATES = [
    {
        "gate_id": "v23_over_gate",
        "label": "WARPS v2.3 Over gate",
        "model": "WARPS v2.3",
        "side": "OVER",
        "edge_threshold": 0.5,
        "price_edge_threshold": 0.10,
        "model_prob_threshold": 0.60,
        "min_agreement_count": 1,
        "historical_note": "60 bets, +3.45% ROI in gate grid",
    },
    {
        "gate_id": "v23_under_gate",
        "label": "WARPS v2.3 Under gate",
        "model": "WARPS v2.3",
        "side": "UNDER",
        "edge_threshold": 0.5,
        "price_edge_threshold": 0.05,
        "model_prob_threshold": 0.50,
        "min_agreement_count": 1,
        "historical_note": "162 bets, +1.61% ROI in gate grid",
    },
    {
        "gate_id": "v23_all_gate",
        "label": "WARPS v2.3 All-side gate",
        "model": "WARPS v2.3",
        "side": "ALL",
        "edge_threshold": 0.5,
        "price_edge_threshold": 0.05,
        "model_prob_threshold": 0.50,
        "min_agreement_count": 1,
        "historical_note": "263 bets, +1.02% ROI in gate grid",
    },
]


def metrics(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {
            "bets": 0,
            "wins": 0,
            "pushes": 0,
            "losses": 0,
            "win_pct": 0.0,
            "units": 0.0,
            "roi_pct": 0.0,
        }
    wins = int((rows["result"] == "win").sum())
    pushes = int((rows["result"] == "push").sum())
    losses = int((rows["result"] == "loss").sum())
    decisions = wins + losses
    units = float(rows["pnl_units"].sum())
    return {
        "bets": int(len(rows)),
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "win_pct": round(wins / decisions * 100, 2) if decisions else 0.0,
        "units": round(units, 3),
        "roi_pct": round(units / decisions * 100, 2) if decisions else 0.0,
    }


def gate_rows(bets: pd.DataFrame, gate: dict) -> pd.DataFrame:
    rows = bets[
        (bets["model"] == gate["model"])
        & (bets["abs_edge"] >= gate["edge_threshold"])
        & (bets["price_edge"] >= gate["price_edge_threshold"])
        & (bets["model_prob"] >= gate["model_prob_threshold"])
        & (bets["agreement_count"] >= gate["min_agreement_count"])
    ]
    if gate["side"] != "ALL":
        rows = rows[rows["bet_side"] == gate["side"]]
    return rows.copy()


def era_label(season: int) -> str:
    if season <= 2010:
        return "2003-2010"
    if season <= 2016:
        return "2011-2016"
    return "2017-2020"


def audit_gate(bets: pd.DataFrame, gate: dict) -> tuple[dict, list[dict]]:
    rows = gate_rows(bets, gate)
    base = metrics(rows)
    by_season = rows.groupby("season")["pnl_units"].sum().sort_index()
    by_team = rows.groupby("team")["pnl_units"].sum().sort_values()
    era_rows = []
    for era, part in rows.assign(era=rows["season"].map(era_label)).groupby("era"):
        era_rows.append({"gate_id": gate["gate_id"], "slice": f"era:{era}", **metrics(part)})

    loo_units = []
    for season in sorted(rows["season"].unique()):
        part = rows[rows["season"] != season]
        m = metrics(part)
        loo_units.append({"season_removed": int(season), **m})

    best_season = int(by_season.idxmax()) if not by_season.empty else None
    worst_season = int(by_season.idxmin()) if not by_season.empty else None
    best_removed = metrics(rows[rows["season"] != best_season]) if best_season is not None else metrics(rows)
    worst_removed = metrics(rows[rows["season"] != worst_season]) if worst_season is not None else metrics(rows)
    season_count = int(by_season.size)
    profitable_seasons = int((by_season > 0).sum())
    top_team_units = float(by_team.iloc[-1]) if not by_team.empty else 0.0
    bottom_team_units = float(by_team.iloc[0]) if not by_team.empty else 0.0

    summary = {
        **gate,
        **base,
        "seasons": season_count,
        "profitable_seasons": profitable_seasons,
        "profitable_season_pct": round(profitable_seasons / season_count * 100, 2) if season_count else 0.0,
        "best_season": best_season,
        "best_season_units": round(float(by_season.max()), 3) if not by_season.empty else 0.0,
        "worst_season": worst_season,
        "worst_season_units": round(float(by_season.min()), 3) if not by_season.empty else 0.0,
        "units_without_best_season": best_removed["units"],
        "roi_without_best_season": best_removed["roi_pct"],
        "units_without_worst_season": worst_removed["units"],
        "roi_without_worst_season": worst_removed["roi_pct"],
        "top_team": by_team.index[-1] if not by_team.empty else "",
        "top_team_units": round(top_team_units, 3),
        "bottom_team": by_team.index[0] if not by_team.empty else "",
        "bottom_team_units": round(bottom_team_units, 3),
    }

    detail_rows = [
        {"gate_id": gate["gate_id"], "slice": "base", **base},
        {"gate_id": gate["gate_id"], "slice": f"without_best_season:{best_season}", **best_removed},
        {"gate_id": gate["gate_id"], "slice": f"without_worst_season:{worst_season}", **worst_removed},
    ]
    detail_rows.extend(era_rows)
    for item in loo_units:
        detail_rows.append({"gate_id": gate["gate_id"], "slice": f"leave_one_out:{item['season_removed']}", **{k: v for k, v in item.items() if k != "season_removed"}})
    return summary, detail_rows


def card_audit(card: pd.DataFrame, gate_summaries: list[dict]) -> pd.DataFrame:
    summary_by_gate = {row["gate_id"]: row for row in gate_summaries}
    rows = []
    for rec in card.itertuples(index=False):
        if rec.decision != "BET":
            gate_id = "watch_or_pass"
        elif rec.bet_side == "Over":
            gate_id = "v23_over_gate"
        else:
            gate_id = "v23_under_gate"
        hist = summary_by_gate.get(gate_id, {})
        fragility_flags = []
        if hist.get("units_without_best_season", 0) <= 0:
            fragility_flags.append("best-season dependent")
        if hist.get("profitable_season_pct", 0) < 50:
            fragility_flags.append("sub-50% season hit-rate")
        if abs(float(rec.edge)) < 1.0:
            fragility_flags.append("thin forecast edge")
        if float(rec.price_edge) < 0.10:
            fragility_flags.append("thin price edge")
        rows.append(
            {
                "team": rec.team,
                "decision": rec.decision,
                "stake_tier": rec.stake_tier,
                "bet_side": rec.bet_side,
                "line": rec.line,
                "odds": rec.odds,
                "model_prob": rec.model_prob,
                "price_edge": rec.price_edge,
                "edge": rec.edge,
                "gate_id": gate_id,
                "historical_bets": hist.get("bets", 0),
                "historical_roi_pct": hist.get("roi_pct", 0.0),
                "historical_units": hist.get("units", 0.0),
                "profitable_season_pct": hist.get("profitable_season_pct", 0.0),
                "roi_without_best_season": hist.get("roi_without_best_season", 0.0),
                "fragility_flags": "; ".join(fragility_flags) if fragility_flags else "none",
            }
        )
    return pd.DataFrame(rows)


def write_markdown(gate_summaries: list[dict], card_rows: pd.DataFrame) -> None:
    lines = [
        "# WARPS Betting Stability Audit",
        "",
        "This audit stress-tests the historical betting gates used by the 2026 betting card.",
        "",
        "## Gate Stability",
        "",
        "| Gate | Bets | Units | ROI | Profitable Seasons | Best Removed ROI | Worst Season | Flags |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for gate in gate_summaries:
        flags = []
        if gate["roi_without_best_season"] <= 0:
            flags.append("best-season dependent")
        if gate["profitable_season_pct"] < 50:
            flags.append("weak season breadth")
        if gate["roi_pct"] < 2:
            flags.append("thin ROI")
        lines.append(
            f"| {gate['label']} | {gate['bets']} | {gate['units']:+.2f} | {gate['roi_pct']:+.2f}% | "
            f"{gate['profitable_season_pct']:.1f}% | {gate['roi_without_best_season']:+.2f}% | "
            f"{gate['worst_season']} ({gate['worst_season_units']:+.2f}) | {', '.join(flags) or 'none'} |"
        )

    lines.extend([
        "",
        "## 2026 Card Fragility",
        "",
        "| Team | Bet | Tier | Hist ROI | ROI w/o Best | Flags |",
        "|---|---:|---|---:|---:|---|",
    ])
    for rec in card_rows[card_rows["decision"] == "BET"].itertuples(index=False):
        lines.append(
            f"| {rec.team} | {rec.bet_side} {rec.line:g} {rec.odds} | {rec.stake_tier} | "
            f"{rec.historical_roi_pct:+.2f}% | {rec.roi_without_best_season:+.2f}% | {rec.fragility_flags} |"
        )

    REPORT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    bets = pd.read_csv(BETS)
    card = pd.read_csv(CARD)
    gate_summaries = []
    detail_rows = []
    for gate in GATES:
        summary, detail = audit_gate(bets, gate)
        gate_summaries.append(summary)
        detail_rows.extend(detail)

    card_rows = card_audit(card, gate_summaries)
    pd.DataFrame(detail_rows).to_csv(GATE_AUDIT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    card_rows.to_csv(CARD_AUDIT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    REPORT_JSON.write_text(json.dumps({"gates": gate_summaries}, indent=2) + "\n")
    write_markdown(gate_summaries, card_rows)

    print(f"Wrote {GATE_AUDIT_CSV}")
    print(f"Wrote {CARD_AUDIT_CSV}")
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print("\nGate summary:")
    print(pd.DataFrame(gate_summaries)[["gate_id", "bets", "units", "roi_pct", "profitable_season_pct", "roi_without_best_season", "worst_season", "worst_season_units"]].to_string(index=False))


if __name__ == "__main__":
    main()
