#!/usr/bin/env python3
"""Detect significant line moves vs. stored model pick lines.

Compares the latest Action Network CSV against the lines stored at analysis
time (initial_sharp_spread_line / initial_sharp_total_line in the master CSV).

Writes:
  data/week{WEEK}/line_move_summary.json   — full detail per game
  stdout                                    — human-readable summary

Exits:
  0 — no significant moves
  2 — significant moves found (use in CI: || true to not fail the step)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import pandas as pd
except ImportError:
    print("pandas not installed")
    sys.exit(0)

from analyzers.nfl_common import normalize_matchup_key

TEAM_NAME_TO_TLA = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def parse_line(line_str, side="away"):
    """Extract numeric line for away or home side from 'AWAY_LINE (odds) | HOME_LINE (odds)'."""
    if not line_str or str(line_str).strip().lower() in ("nan", "none", ""):
        return None
    parts = str(line_str).split("|")
    part = parts[0] if side == "away" else (parts[1] if len(parts) > 1 else parts[0])
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", part.strip())
    return float(m.group(1)) if m else None


def load_master_lines(week: str) -> dict:
    """Return {matchup_key: {spread_line, total_line, pick_market, pick_side}} from master CSV."""
    slug = str(week).upper()
    if slug.startswith("PRE") and not slug.startswith("PREPRE"):
        path = ROOT / "data" / "historical" / f"weekPRE{slug[3:]}_master.csv"
        if not path.exists():
            path = ROOT / "data" / "historical" / f"week{slug}_master.csv"
    else:
        path = ROOT / "data" / "historical" / f"week{slug}_master.csv"

    if not path.exists():
        return {}

    df = pd.read_csv(path)
    result = {}
    for _, row in df.iterrows():
        mk = str(row.get("matchup_key", "")).strip()
        if not mk:
            continue
        # Find the stage that has a pick
        pick_market = pick_side = None
        stored_spread = stored_total = None
        for stage in ("final", "lock", "update", "initial"):
            pm = str(row.get(f"{stage}_pick_market", "") or "").strip().lower()
            if pm in ("spread", "total", "moneyline"):
                pick_market = pm
                pick_side = str(row.get(f"{stage}_pick_side", "") or "").strip().upper()
                stored_spread = row.get(f"{stage}_sharp_spread_line") or ""
                stored_total = row.get(f"{stage}_sharp_total_line") or ""
                break
        # Fall back to initial lines even if no pick
        if not stored_spread:
            stored_spread = row.get("initial_sharp_spread_line") or ""
        if not stored_total:
            stored_total = row.get("initial_sharp_total_line") or ""

        result[mk] = {
            "spread_line_raw": str(stored_spread).strip(),
            "total_line_raw": str(stored_total).strip(),
            "away_spread": parse_line(stored_spread, "away"),
            "home_spread": parse_line(stored_spread, "home"),
            "pick_market": pick_market,
            "pick_side": pick_side,
        }
    return result


def load_current_lines(markets_csv: str) -> dict:
    """Return {matchup_key: {away_spread, home_spread, total}} from Action Network CSV."""
    path = Path(markets_csv)
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    spread_rows = df[df["Market"].str.strip().str.lower() == "spread"]
    total_rows = df[df["Market"].str.strip().str.lower() == "total"]

    spreads = {}
    for _, row in spread_rows.iterrows():
        matchup_raw = str(row.get("Matchup", "")).strip()
        parts = matchup_raw.split("@")
        if len(parts) != 2:
            continue
        away_name, home_name = parts[0].strip(), parts[1].strip()
        away_tla = TEAM_NAME_TO_TLA.get(away_name, away_name[:3].upper())
        home_tla = TEAM_NAME_TO_TLA.get(home_name, home_name[:3].upper())
        mk = normalize_matchup_key(f"{away_tla}@{home_tla}")
        line_raw = str(row.get("Line", "")).strip()
        spreads[mk] = {
            "away_spread": parse_line(line_raw, "away"),
            "home_spread": parse_line(line_raw, "home"),
            "line_raw": line_raw,
        }

    totals = {}
    for _, row in total_rows.iterrows():
        matchup_raw = str(row.get("Matchup", "")).strip()
        parts = matchup_raw.split("@")
        if len(parts) != 2:
            continue
        away_tla = TEAM_NAME_TO_TLA.get(parts[0].strip(), parts[0].strip()[:3].upper())
        home_tla = TEAM_NAME_TO_TLA.get(parts[1].strip(), parts[1].strip()[:3].upper())
        mk = normalize_matchup_key(f"{away_tla}@{home_tla}")
        line_raw = str(row.get("Line", "")).strip()
        m = re.search(r"\d+(?:\.\d+)?", line_raw)
        totals[mk] = float(m.group()) if m else None

    result = {}
    for mk, s in spreads.items():
        result[mk] = {**s, "total": totals.get(mk)}
    return result


def detect_moves(stored: dict, current: dict, threshold: float, season_type: str = "REG") -> list:
    moves = []
    for mk, cur in current.items():
        if mk not in stored:
            continue
        st = stored[mk]

        old_away = st.get("away_spread")
        new_away = cur.get("away_spread")

        if old_away is None or new_away is None:
            continue

        move = new_away - old_away  # positive = line moved toward home (away got worse)
        abs_move = abs(move)

        if abs_move < threshold:
            continue

        old_fav = "AWAY" if old_away < 0 else ("HOME" if old_away > 0 else "PK")
        new_fav = "AWAY" if new_away < 0 else ("HOME" if new_away > 0 else "PK")
        is_flip = old_fav != new_fav

        pick_market = st.get("pick_market")
        pick_side = st.get("pick_side")
        has_model_pick = bool(pick_market)

        # Determine if move helps or hurts the model pick
        pick_impact = None
        if has_model_pick and pick_market == "spread":
            if pick_side == "AWAY":
                # Away pick — positive move_val means line got worse (less +, more -)
                pick_impact = "better" if move < 0 else "worse"
            elif pick_side == "HOME":
                pick_impact = "better" if move > 0 else "worse"

        parts = mk.split("@")
        away_tla = parts[0] if len(parts) == 2 else mk
        home_tla = parts[1] if len(parts) == 2 else mk

        moves.append({
            "matchup_key": mk,
            "away_tla": away_tla,
            "home_tla": home_tla,
            "old_away_spread": old_away,
            "new_away_spread": new_away,
            "move_points": round(move, 1),
            "abs_move": round(abs_move, 1),
            "is_flip": is_flip,
            "old_favorite": old_fav,
            "new_favorite": new_fav,
            "has_model_pick": has_model_pick,
            "pick_market": pick_market,
            "pick_side": pick_side,
            "pick_impact": pick_impact,
            "severity": "critical" if abs_move >= 4.0 else ("major" if abs_move >= 2.5 else "notable"),
        })

    moves.sort(key=lambda x: (-x["abs_move"], not x["has_model_pick"]))
    return moves


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("week", help="NFL week label (PRE1, PRE2, 1-18, WC...)")
    parser.add_argument("--markets", help="Path to Action Network markets CSV")
    parser.add_argument("--threshold", type=float, default=2.0,
                        help="Minimum line move (points) to flag (default 2.0)")
    parser.add_argument("--season-type", default="REG", choices=["PRE", "REG", "POST"])
    parser.add_argument("--output", help="Path to write move summary JSON")
    args = parser.parse_args()

    week = args.week
    threshold = args.threshold
    if args.season_type == "PRE":
        threshold = min(threshold, 1.5)

    # Find latest markets CSV if not specified
    if args.markets:
        markets_csv = args.markets
    else:
        candidates = sorted(Path(ROOT / "data").glob("action_all_markets_*.csv"), reverse=True)
        if not candidates:
            print("No Action Network markets CSV found")
            sys.exit(0)
        markets_csv = str(candidates[0])

    stored = load_master_lines(week)
    if not stored:
        print(f"No stored lines found for week {week} — skipping move detection")
        sys.exit(0)

    current = load_current_lines(markets_csv)
    if not current:
        print(f"No current lines found in {markets_csv}")
        sys.exit(0)

    moves = detect_moves(stored, current, threshold, args.season_type)

    summary = {
        "week": week,
        "season_type": args.season_type,
        "threshold": threshold,
        "markets_file": str(markets_csv),
        "total_moves": len(moves),
        "pick_affected": sum(1 for m in moves if m["has_model_pick"]),
        "flips": sum(1 for m in moves if m["is_flip"]),
        "moves": moves,
    }

    # Write summary JSON
    out_path = args.output or str(ROOT / "data" / f"week{week}" / "line_move_summary.json")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(summary, indent=2))

    # Print human-readable report
    if not moves:
        print(f"✅ No significant line moves detected (threshold: {threshold} pts)")
    else:
        print(f"🚨 {len(moves)} significant line move(s) detected (threshold: {threshold} pts)")
        for m in moves:
            tag = "⚠️ PICK AFFECTED" if m["has_model_pick"] else ""
            flip_tag = " [FLIP]" if m["is_flip"] else ""
            impact = f" — pick {m['pick_impact'].upper()}" if m["pick_impact"] else ""
            print(
                f"  {m['severity'].upper():8s} | {m['matchup_key']:10s} | "
                f"{m['old_away_spread']:+.1f} → {m['new_away_spread']:+.1f} "
                f"({m['move_points']:+.1f} pts){flip_tag}{impact}  {tag}"
            )

    # Set GitHub Actions outputs if running in CI
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"line_moves_total={len(moves)}\n")
            f.write(f"line_moves_pick_affected={summary['pick_affected']}\n")
            f.write(f"line_moves_flips={summary['flips']}\n")
            # Compact summary for email injection
            compact = "; ".join(
                f"{m['matchup_key']} {m['old_away_spread']:+.1f}→{m['new_away_spread']:+.1f}"
                + (" [PICK]" if m["has_model_pick"] else "")
                for m in moves[:5]
            )
            f.write(f"line_moves_summary={compact}\n")

    sys.exit(2 if moves else 0)


if __name__ == "__main__":
    main()
