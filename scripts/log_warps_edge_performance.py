#!/usr/bin/env python3
"""Log WARPS edge plays and their outcomes to data/historical/warps_edge_log.csv.

Run after grading (week master JSON must have scores). Appends one row per
game per week where the overlay has a priced edge, recording:
  - WARPS fair spread vs market spread and the resulting edge
  - ML edge and EV
  - Whether the weekly engine confirmed a play
  - Actual result (did the WARPS-suggested spread side cover?)

Usage:
    python3 scripts/log_warps_edge_performance.py --week 1 --season 2026
    python3 scripts/log_warps_edge_performance.py  # auto-detect from current_week.json
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
from nfl_common import get_current_season

LOG_PATH = ROOT / "data" / "historical" / "warps_edge_log.csv"

LOG_FIELDS = [
    "season", "week", "matchup_key", "away_tla", "home_tla", "game_date",
    "warps_fair_spread",       # home spread (neg = home fav)
    "market_spread",           # home spread from market
    "spread_edge_pts",         # positive = value on away team
    "spread_overlay_side",     # AWAY or HOME
    "spread_overlay_team",
    "ml_edge_prob",            # away ML edge in probability (positive = value on away)
    "ml_overlay_ev",           # expected value on away ML
    "market_total",            # closing total line
    "engine_confirmed",        # True/False: weekly engine said PLAY
    "engine_market",           # spread/total/moneyline or blank
    "engine_side",             # AWAY/HOME/OVER/UNDER or blank
    "engine_stage",            # stage at which engine confirmed (initial/update/lock/final)
    "away_score", "home_score",
    "spread_result",           # cover/miss/push/no_bet (for overlay side)
    "ml_result",               # win/loss/no_bet (for overlay ML side)
    "ou_result",               # over/under/push
    "status",                  # 'priced' or 'fair_line_only'
]


def parse_spread_home(line_str):
    """Extract home spread number from 'away_line | home_line' string."""
    if not line_str:
        return None
    parts = str(line_str).split("|")
    if len(parts) < 2:
        return None
    m = re.search(r"([+-]\d+\.?\d*)", parts[1])
    return float(m.group(1)) if m else None


def parse_total(line_str):
    """Extract total number from 'o47.5 (-102) | u47 (-107)' string."""
    if not line_str:
        return None
    m = re.search(r"[ou](\d+\.?\d*)", str(line_str), re.I)
    return float(m.group(1)) if m else None


def load_existing_log():
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH) as f:
        return list(csv.DictReader(f))


def week_key(season, week):
    return f"{season}_{week}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default="")
    parser.add_argument("--season", default="")
    parser.add_argument("--season-type", default="REG")
    args = parser.parse_args()

    season = int(args.season) if args.season else get_current_season()
    overlay_csv = ROOT / "data" / "historical" / f"warps_{season}_market_overlay.csv"

    week = args.week
    if not week:
        cw_path = ROOT / "data" / "current_week.json"
        if cw_path.exists():
            cw = json.loads(cw_path.read_text())
            week = str(cw.get("week", ""))
    if not week:
        print("ERROR: --week required or data/current_week.json must exist", file=sys.stderr)
        sys.exit(1)

    # Load master JSON for scores and engine recommendations
    master_path = ROOT / "data" / "historical" / f"week{week}_master.json"
    if not master_path.exists():
        print(f"ERROR: {master_path} not found — run grading first", file=sys.stderr)
        sys.exit(1)
    master_games = {g["matchup_key"]: g for g in json.loads(master_path.read_text())}

    # Load overlay CSV for WARPS edge data
    if not overlay_csv.exists():
        print(f"ERROR: {overlay_csv} not found", file=sys.stderr)
        sys.exit(1)

    overlay_rows = {}
    with open(overlay_csv) as f:
        for row in csv.DictReader(f):
            if str(row.get("season", "")) == str(season) and str(row.get("week", "")) == str(week):
                overlay_rows[row["matchup_key"]] = row

    if not overlay_rows:
        print(f"No overlay rows for season={season} week={week}", file=sys.stderr)
        sys.exit(0)

    # Load existing log and remove any rows for this week (re-run idempotency)
    existing = [r for r in load_existing_log()
                if not (r["season"] == str(season) and r["week"] == str(week))]

    new_rows = []
    for mk, ov in sorted(overlay_rows.items()):
        g = master_games.get(mk, {})
        a_score = g.get("away_score")
        h_score = g.get("home_score")
        # Skip unplayed games (placeholder 0-0)
        if a_score == 0 and h_score == 0:
            a_score = h_score = None

        fair_spread = float(ov.get("fair_home_spread") or 0)
        mkt_spread = ov.get("market_home_spread")
        mkt_spread_f = float(mkt_spread) if mkt_spread else None

        spread_edge = ov.get("home_spread_edge")
        spread_edge_f = float(spread_edge) if spread_edge else None
        # positive home_spread_edge means value on HOME; we store as-is (sign encodes direction)

        ml_edge = ov.get("away_ml_edge")
        ml_ev = ov.get("ml_overlay_ev")

        overlay_side = ov.get("spread_overlay_side", "")
        overlay_team = ov.get("spread_overlay_team", "")
        status = ov.get("status", "")

        # Determine closing total from master sharp lines (update preferred)
        mkt_total = None
        for stage in ["update", "lock", "final", "initial"]:
            t = parse_total(g.get(f"{stage}_sharp_total_line"))
            if t:
                mkt_total = t
                break

        # Find engine play across stages
        engine_confirmed = False
        engine_market = engine_side = engine_stage = ""
        for stage in ["final", "lock", "update", "initial"]:
            if not g.get(f"has_{stage}"):
                continue
            pm = g.get(f"{stage}_pick_market", "")
            if pm and str(pm).lower() not in ("none", ""):
                engine_confirmed = True
                engine_market = pm
                engine_side = g.get(f"{stage}_pick_side", "") or ""
                engine_stage = stage
                break

        # Grade spread result — engine's confirmed pick side takes precedence over overlay side
        # so the result reflects what the weekly engine actually bet, not just the model preference
        spread_result = "no_data"
        grade_side = (engine_side if (engine_confirmed and engine_market == "spread" and engine_side)
                      else overlay_side)
        if a_score is not None and h_score is not None and mkt_spread_f is not None and grade_side:
            # market_home_spread convention: negative = home favored, positive = away favored
            away_covers = (float(a_score) - float(h_score) + (-mkt_spread_f)) > 0
            home_covers = (float(h_score) - float(a_score) + mkt_spread_f) > 0
            is_push = not away_covers and not home_covers
            if is_push:
                spread_result = "push"
            elif grade_side.upper() == "AWAY":
                spread_result = "cover" if away_covers else "miss"
            elif grade_side.upper() == "HOME":
                spread_result = "cover" if home_covers else "miss"
        elif a_score is not None and h_score is not None and not grade_side:
            spread_result = "no_edge"

        # Grade ML result for WARPS overlay ML side
        ml_result = "no_data"
        ml_side = ov.get("ml_overlay_side", "")
        if a_score is not None and h_score is not None and ml_side:
            away_won = float(a_score) > float(h_score)
            home_won = float(h_score) > float(a_score)
            if ml_side.upper() == "AWAY":
                ml_result = "win" if away_won else ("push" if not home_won else "loss")
            elif ml_side.upper() == "HOME":
                ml_result = "win" if home_won else ("push" if not away_won else "loss")

        # Grade O/U
        ou_result = "no_data"
        if a_score is not None and h_score is not None and mkt_total:
            actual = float(a_score) + float(h_score)
            ou_result = "over" if actual > mkt_total else ("under" if actual < mkt_total else "push")

        new_rows.append({
            "season": season,
            "week": week,
            "matchup_key": mk,
            "away_tla": ov.get("away_tla", ""),
            "home_tla": ov.get("home_tla", ""),
            "game_date": ov.get("game_date", ""),
            "warps_fair_spread": fair_spread,
            "market_spread": mkt_spread_f if mkt_spread_f is not None else "",
            "spread_edge_pts": spread_edge_f if spread_edge_f is not None else "",
            "spread_overlay_side": overlay_side,
            "spread_overlay_team": overlay_team,
            "ml_edge_prob": ml_edge or "",
            "ml_overlay_ev": ml_ev or "",
            "market_total": mkt_total or "",
            "engine_confirmed": engine_confirmed,
            "engine_market": engine_market,
            "engine_side": engine_side,
            "engine_stage": engine_stage,
            "away_score": a_score if a_score is not None else "",
            "home_score": h_score if h_score is not None else "",
            "spread_result": spread_result,
            "ml_result": ml_result,
            "ou_result": ou_result,
            "status": status,
        })

    # Write updated log
    all_rows = existing + new_rows
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    priced = sum(1 for r in new_rows if r["status"] == "priced")
    graded = sum(1 for r in new_rows if r["spread_result"] in ("cover", "miss", "push"))
    print(f"Logged {len(new_rows)} games (season={season} week={week}): "
          f"{priced} priced, {graded} graded spread results")
    print(f"Wrote {LOG_PATH} ({len(all_rows)} total rows)")


if __name__ == "__main__":
    main()
