#!/usr/bin/env python3
"""
Analyze week-of-season and phase-of-season edges in the WARPS game edges dataset.

Key findings (2015-2025, 3,028 graded REG games, edge>=1.5):
  Week 1:      58.2% win rate, +12.2% ROI  (n=110)
  Week 7:      40.4% win rate, -25.3% ROI  (n=114)  ← consistently bad
  Weeks 1-10 (ex 7): 53.8% win rate, +3.0% ROI (n=1,043)
  Weeks 11-14: 46.0% win rate, -13.4% ROI
  Weeks 15-18: 47.0% win rate, -11.2% ROI
  Postseason WC/CON/SB: 55.1% win rate, +5.6% ROI
  Divisional round: 40.9% win rate, -24.1% ROI  ← consistently bad

Usage:
  python3 scripts/analyze_weekly_phase_edges.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDGES_CSV = ROOT / "data" / "backtests" / "warps_game_edges" / "warps_game_edges.csv"


def roi(wins, total):
    if not total:
        return float('nan')
    return (wins * 1.0 - (total - wins) * 1.1) / total * 100


def report(label, sub):
    w = sub["pick_wins"].sum()
    n = len(sub)
    return f"  {label}: n={n:4d}, win%={w/n:.1%}, ROI={roi(w, n):+.1f}%"


def main():
    edges = pd.read_csv(EDGES_CSV)
    edges = edges[edges["spread_result"].notna() & edges["spread_edge_points"].notna()].copy()
    edges["pick_wins"] = edges["spread_result"] == "win"
    edges["abs_edge"] = edges["spread_edge_points"].abs()
    edges["pick_home"] = edges["spread_pick_side"] == "HOME"
    edges["pick_favorite"] = (
        (edges["spread_pick_side"] == "HOME") & (edges["market_home_spread"] < 0) |
        (edges["spread_pick_side"] == "AWAY") & (edges["market_home_spread"] > 0)
    )
    edges["abs_gap"] = edges["home_strength_gap_wins"].abs()
    edges["gap_aligned"] = (
        ((edges["home_strength_gap_wins"] > 0) & (edges["spread_pick_side"] == "HOME")) |
        ((edges["home_strength_gap_wins"] < 0) & (edges["spread_pick_side"] == "AWAY"))
    )
    reg = edges[edges["game_type"] == "REG"].copy()
    e15 = reg[reg["abs_edge"] >= 1.5]

    print("=== WEEK-BY-WEEK (REG, edge>=1.5) ===")
    for wk in range(1, 19):
        sub = e15[e15["week"] == wk]
        if not len(sub):
            continue
        w = sub["pick_wins"].sum()
        n = len(sub)
        bar = "█" * int(w / n * 20) + "░" * (20 - int(w / n * 20))
        print(f"  Wk{wk:2d}: {bar} {w/n:.1%}  n={n:3d}  ROI={roi(w,n):+.1f}%")

    print("\n=== PHASE GATES ===")
    phases = [
        ("wk 1-10 excl 7",   e15[e15["week"].isin([1,2,3,4,5,6,8,9,10])]),
        ("wk 7 only",         e15[e15["week"] == 7]),
        ("wk 11-14",         e15[(e15["week"] >= 11) & (e15["week"] <= 14)]),
        ("wk 15-18",         e15[e15["week"] >= 15]),
    ]
    for label, sub in phases:
        print(report(label, sub))

    print("\n=== POSTSEASON ===")
    for gt in ["WC", "DIV", "CON", "SB"]:
        sub = edges[edges["game_type"] == gt]
        if not len(sub):
            continue
        print(report(gt, sub))

    print("\n=== STRENGTH GAP + PHASE ===")
    combos = [
        ("gap>=3 aligned + wk1-10",    reg[reg["abs_gap"] >= 3] & reg["gap_aligned"] & (reg["abs_edge"] >= 1.5) & (reg["week"] <= 10)),
        ("gap>=3 aligned all weeks",   reg[(reg["abs_gap"] >= 3) & reg["gap_aligned"] & (reg["abs_edge"] >= 1.5)]),
        ("away dog + wk1-6",           e15[~e15["pick_home"] & ~e15["pick_favorite"] & e15["week"].isin([1,2,3,4,5,6])]),
    ]
    for label, mask in combos:
        sub = reg[mask] if hasattr(mask, 'index') and len(mask) else reg[mask]
        print(report(label, sub))


if __name__ == "__main__":
    main()
