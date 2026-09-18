#!/usr/bin/env python3
"""Patch the WARPS market overlay with fresh sharp lines from the week master JSON.

After each engine stage (initial/update/lock), the master JSON has sharper,
more current spread/ML/total lines than the Odds API snapshot the overlay was
built from. This script:

  1. Reads {stage}_sharp_* lines from the master JSON for a given week
  2. Updates market_home_spread, market_away_spread, market_home_moneyline,
     market_away_moneyline in the overlay CSV
  3. Adds market_total (missing from the overlay schema entirely)
  4. Recomputes spread/ML edges and overlay sides with the fresh lines
  5. WARPS does not generate a fair total (R²=0.002 vs wins) — total edge
     columns are intentionally omitted

Usage:
    python3 scripts/patch_overlay_from_master.py --week 2 --season 2026
    python3 scripts/patch_overlay_from_master.py  # auto-detect from current_week.json
    python3 scripts/patch_overlay_from_master.py --stage update  # default
"""

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
from nfl_common import get_current_season

OVERLAY_CSV = ROOT / "data" / "historical" / "warps_2026_market_overlay.csv"

# Stage preference order for extracting market lines
STAGE_ORDER = ["lock", "update", "initial"]


# ── line parsing ─────────────────────────────────────────────────────────────

def parse_spread_pair(line_str):
    """'away_line | home_line' → (away_float, home_float) or (None, None)."""
    if not line_str:
        return None, None
    parts = str(line_str).split("|")
    def extract(s):
        m = re.search(r"([+-]\d+\.?\d*)", s)
        return float(m.group(1)) if m else None
    away = extract(parts[0]) if len(parts) >= 1 else None
    home = extract(parts[1]) if len(parts) >= 2 else None
    return away, home


def parse_ml_pair(line_str):
    """'away_ml | home_ml' → (away_float, home_float) or (None, None)."""
    if not line_str:
        return None, None
    parts = str(line_str).split("|")
    def extract(s):
        m = re.search(r"([+-]\d+\.?\d*)", s)
        return float(m.group(1)) if m else None
    away = extract(parts[0]) if len(parts) >= 1 else None
    home = extract(parts[1]) if len(parts) >= 2 else None
    return away, home


def parse_total(line_str):
    """'o47.5 (-102) | u47 (-107)' → 47.5 (uses over line)."""
    if not line_str:
        return None
    m = re.search(r"[ou](\d+\.?\d*)", str(line_str), re.I)
    return float(m.group(1)) if m else None


# ── edge computation (mirrors build_2026_warps_market_overlay.py) ────────────

def american_to_prob(ml):
    if ml is None:
        return None
    if ml > 0:
        return 100.0 / (ml + 100.0)
    return abs(ml) / (abs(ml) + 100.0)


def devig_pair(home_ml, away_ml):
    hp = american_to_prob(home_ml)
    ap = american_to_prob(away_ml)
    if hp is None or ap is None:
        return None, None, None
    total = hp + ap
    return hp / total, ap / total, total - 1.0


def moneyline_ev(win_prob, ml):
    if win_prob is None or ml is None:
        return None
    payout = ml / 100.0 if ml > 0 else 100.0 / abs(ml)
    return round(win_prob * payout - (1 - win_prob), 4)


def recompute_edges(row, new_home_spread, new_away_spread, new_home_ml, new_away_ml):
    """Return updated edge columns given fresh market lines."""
    fair_home = _float(row.get("fair_home_spread"))
    fair_away = _float(row.get("fair_away_spread"))
    home_win_prob = _float(row.get("home_win_prob"))
    away_win_prob = _float(row.get("away_win_prob"))

    # Spread edge
    home_spread_edge = (new_home_spread - fair_home) if new_home_spread is not None and fair_home is not None else None
    away_spread_edge = (new_away_spread - fair_away) if new_away_spread is not None and fair_away is not None else None

    spread_side = spread_team = ""
    spread_edge = None
    if home_spread_edge is not None and away_spread_edge is not None:
        if home_spread_edge >= away_spread_edge:
            spread_side, spread_team = "HOME", row.get("home_tla", "")
            spread_edge = home_spread_edge
        else:
            spread_side, spread_team = "AWAY", row.get("away_tla", "")
            spread_edge = away_spread_edge

    # ML edge
    home_mkt_prob, away_mkt_prob, ml_hold = devig_pair(new_home_ml, new_away_ml)
    home_ml_edge = (home_win_prob - home_mkt_prob) if home_win_prob is not None and home_mkt_prob is not None else None
    away_ml_edge = (away_win_prob - away_mkt_prob) if away_win_prob is not None and away_mkt_prob is not None else None

    ml_side = ml_team = ""
    ml_edge = ml_ev = None
    if home_ml_edge is not None and away_ml_edge is not None:
        if home_ml_edge >= away_ml_edge:
            ml_side, ml_team = "HOME", row.get("home_tla", "")
            ml_edge, ml_ev = home_ml_edge, moneyline_ev(home_win_prob, new_home_ml)
        else:
            ml_side, ml_team = "AWAY", row.get("away_tla", "")
            ml_edge, ml_ev = away_ml_edge, moneyline_ev(away_win_prob, new_away_ml)

    return {
        "home_spread_edge":       _fmt(home_spread_edge, 3),
        "away_spread_edge":       _fmt(away_spread_edge, 3),
        "spread_overlay_side":    spread_side,
        "spread_overlay_team":    spread_team,
        "spread_overlay_edge_points": _fmt(spread_edge, 3),
        "home_ml_no_vig_prob":    _fmt(home_mkt_prob, 4),
        "away_ml_no_vig_prob":    _fmt(away_mkt_prob, 4),
        "moneyline_hold":         _fmt(ml_hold, 4),
        "home_ml_edge":           _fmt(home_ml_edge, 4),
        "away_ml_edge":           _fmt(away_ml_edge, 4),
        "ml_overlay_side":        ml_side,
        "ml_overlay_team":        ml_team,
        "ml_overlay_edge_prob":   _fmt(ml_edge, 4),
        "ml_overlay_ev":          _fmt(ml_ev, 4),
    }


def _float(v):
    try:
        return float(v) if v not in (None, "", "nan") else None
    except (TypeError, ValueError):
        return None


def _fmt(v, digits):
    return round(v, digits) if v is not None else ""


# ── TLA normalization (mirrors overlay builder) ───────────────────────────────

_TLA_ALIASES = {"WSH": "WAS", "LAR": "LA", "OAK": "LV"}

def _norm(tla):
    return _TLA_ALIASES.get(tla, tla)

def _norm_key(key):
    if "@" not in key:
        return key
    away, home = key.split("@", 1)
    return f"{_norm(away)}@{_norm(home)}"


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default="")
    parser.add_argument("--season", default="")
    parser.add_argument("--stage", default="update",
                        help="Stage to pull sharp lines from (initial/update/lock/final)")
    args = parser.parse_args()

    season = int(args.season) if args.season else get_current_season()
    week = args.week
    if not week:
        cw = ROOT / "data" / "current_week.json"
        if cw.exists():
            week = str(json.loads(cw.read_text()).get("week", ""))
    if not week:
        print("ERROR: --week required", file=sys.stderr)
        sys.exit(1)

    master_path = ROOT / "data" / "historical" / f"week{week}_master.json"
    if not master_path.exists():
        print(f"ERROR: {master_path} not found", file=sys.stderr)
        sys.exit(1)

    # Build lookup: norm_matchup_key → stage sharp lines
    stage_order = STAGE_ORDER if args.stage == "update" else [args.stage] + STAGE_ORDER
    sharp_lines = {}
    for g in json.loads(master_path.read_text()):
        norm = _norm_key(g["matchup_key"])
        lines = {}
        for stage in stage_order:
            if not g.get(f"has_{stage}"):
                continue
            sprd = g.get(f"{stage}_sharp_spread_line", "")
            tot  = g.get(f"{stage}_sharp_total_line", "")
            ml   = g.get(f"{stage}_sharp_moneyline_line", "")
            if sprd:
                aw, hw = parse_spread_pair(sprd)
                if aw is not None:
                    lines.setdefault("away_spread", aw)
                    lines.setdefault("home_spread", hw)
            if tot:
                t = parse_total(tot)
                if t is not None:
                    lines.setdefault("total", t)
            if ml:
                aml, hml = parse_ml_pair(ml)
                if aml is not None:
                    lines.setdefault("away_ml", aml)
                    lines.setdefault("home_ml", hml)
        if lines:
            sharp_lines[norm] = lines

    # Read overlay
    if not OVERLAY_CSV.exists():
        print(f"ERROR: {OVERLAY_CSV} not found", file=sys.stderr)
        sys.exit(1)

    with open(OVERLAY_CSV) as f:
        reader = csv.DictReader(f)
        orig_fields = reader.fieldnames or []
        rows = list(reader)

    # Add market_total to field list if not present
    new_fields = list(orig_fields)
    if "market_total" not in new_fields:
        # Insert after market_away_moneyline
        try:
            idx = new_fields.index("market_away_moneyline") + 1
        except ValueError:
            idx = len(new_fields)
        new_fields.insert(idx, "market_total")

    updated = 0
    for row in rows:
        if str(row.get("season", "")) != str(season) or str(row.get("week", "")) != str(week):
            continue

        mk = _norm_key(row.get("matchup_key", ""))
        lines = sharp_lines.get(mk, {})
        if not lines:
            continue

        hs = lines.get("home_spread")
        as_ = lines.get("away_spread")
        hml = lines.get("home_ml")
        aml = lines.get("away_ml")
        tot = lines.get("total")

        changed = False

        if hs is not None:
            row["market_home_spread"] = _fmt(hs, 2)
            row["market_away_spread"] = _fmt(as_, 2)
            changed = True

        if hml is not None:
            row["market_home_moneyline"] = _fmt(hml, 0)
            row["market_away_moneyline"] = _fmt(aml, 0)
            changed = True

        if tot is not None:
            row["market_total"] = tot
            changed = True

        if changed and hs is not None and hml is not None:
            edges = recompute_edges(row, hs, as_, hml, aml)
            row.update(edges)
            row["status"] = "priced"
            row["source"] = f"WARPS v2.3 game prior + master sharp lines ({args.stage})"
            updated += 1

    # Write back
    with open(OVERLAY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Patched {updated} rows for season={season} week={week} (stage={args.stage})")
    print(f"Wrote {OVERLAY_CSV}")

    # Summary of key changes
    with open(OVERLAY_CSV) as f:
        patched = [r for r in csv.DictReader(f)
                   if str(r.get("season","")) == str(season) and str(r.get("week","")) == str(week)]
    missing_total = sum(1 for r in patched if not r.get("market_total"))
    print(f"  market_total populated: {len(patched)-missing_total}/{len(patched)} games")
    if missing_total:
        for r in patched:
            if not r.get("market_total"):
                print(f"    still missing: {r['matchup_key']}")


if __name__ == "__main__":
    main()
