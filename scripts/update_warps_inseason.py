#!/usr/bin/env python3
"""
Update WARPS team ratings with in-season Pythagorean expectation.

Reads actual PF/PA from week{N}_master.json files, blends with preseason
WARPS win total priors via Bayesian shrinkage, then rewrites the market
overlay CSV and JSON with updated fair values and edges.

Formula
-------
  pyth_rate    = PF^2.37 / (PF^2.37 + PA^2.37)
  blended_17   = (prior_17 * SHRINKAGE + pyth_rate * 17 * games_played) /
                 (SHRINKAGE + games_played)
  fair_hwp     = logistic((blended_home - blended_away + HFA) * 0.15)
  fair_spread  = -(blended_home - blended_away + HFA) * 1.245

SHRINKAGE default = 8 (preseason prior worth ~8 games of evidence).
Spread factor 1.245 derived empirically from original priors (see comments).

Usage
-----
  python3 scripts/update_warps_inseason.py
  python3 scripts/update_warps_inseason.py --season 2026 --through-week 4
  python3 scripts/update_warps_inseason.py --shrinkage 10 --dry-run
"""

import argparse
import csv
import json
import math
from pathlib import Path

# ── Model constants (match WARPS v2.3) ──────────────────────────────────────
PYTH_EXP = 2.37
HOME_FIELD_WINS = 1.6    # HFA in projected-win units
LOGIT_SCALE = 0.15       # logistic scale factor
# Spread factor = LOGIT_SCALE * (NFL pts per logit unit ≈ 8.3)
# Verified against original priors: (h-a+hfa) * 1.245 = -fair_home_spread
SPREAD_FACTOR = 1.245
SEASON_GAMES = 17
DEFAULT_SHRINKAGE = 8    # preseason prior worth this many games of evidence

REPO_ROOT = Path(__file__).parent.parent
DATA_HIST = REPO_ROOT / "data" / "historical"
SITE_DATA = REPO_ROOT / "site" / "src" / "data"


# ── Math helpers ─────────────────────────────────────────────────────────────

def logistic(x):
    return 1.0 / (1.0 + math.exp(-x))


def pythagorean(pf, pa, exp=PYTH_EXP):
    """Pythagorean win rate from cumulative PF/PA."""
    if pf + pa == 0:
        return 0.5
    pf_e, pa_e = pf ** exp, pa ** exp
    denom = pf_e + pa_e
    return pf_e / denom if denom > 0 else 0.5


def fair_hwp(home_wins, away_wins):
    return logistic((home_wins - away_wins + HOME_FIELD_WINS) * LOGIT_SCALE)


def fair_spread(home_wins, away_wins):
    return -(home_wins - away_wins + HOME_FIELD_WINS) * SPREAD_FACTOR


def ml_str(prob):
    """Convert probability to American moneyline string ('+150' / '-150')."""
    if prob >= 1.0:
        return "-99999"
    if prob <= 0.0:
        return "+99999"
    if prob > 0.5:
        return str(round(-prob / (1.0 - prob) * 100))
    else:
        return "+" + str(round((1.0 - prob) / prob * 100))


def nvig_prob(ml):
    """No-vig implied probability from American moneyline (float)."""
    ml = float(ml)
    if ml < 0:
        return abs(ml) / (abs(ml) + 100)
    else:
        return 100 / (ml + 100)


def normalize_tla(tla):
    return "WAS" if str(tla) == "WSH" else str(tla)


# ── Data loading ─────────────────────────────────────────────────────────────

def latest_graded_week(season):
    """Return the highest week number with at least 8 completed games in master JSON."""
    best = 0
    for wk in range(1, 19):
        path = DATA_HIST / f"week{wk}_master.json"
        if not path.exists():
            break
        try:
            games = json.load(open(path))
        except (json.JSONDecodeError, IOError):
            break
        completed = sum(
            1 for g in games
            if g.get("season") == season
            and g.get("away_score") is not None
            and g.get("home_score") is not None
            and not (g.get("away_score") == 0 and g.get("home_score") == 0)
        )
        if completed >= 8:
            best = wk
    return best


def load_actuals(season, through_week):
    """Aggregate PF/PA/games per team from master JSONs."""
    stats = {}  # {tla: {pf, pa, games}}
    for wk in range(1, through_week + 1):
        path = DATA_HIST / f"week{wk}_master.json"
        if not path.exists():
            continue
        with open(path) as f:
            games = json.load(f)
        for g in games:
            if g.get("season") != season:
                continue
            away_sc = g.get("away_score")
            home_sc = g.get("home_score")
            if away_sc is None or home_sc is None:
                continue
            if away_sc == 0 and home_sc == 0:
                continue  # not yet played
            away = normalize_tla(g["away_tla"])
            home = normalize_tla(g["home_tla"])
            for tla, pf, pa in [(away, away_sc, home_sc), (home, home_sc, away_sc)]:
                s = stats.setdefault(tla, {"pf": 0, "pa": 0, "games": 0})
                s["pf"] += pf
                s["pa"] += pa
                s["games"] += 1
    return stats


def load_preseason_priors(season):
    """Extract preseason win totals from game priors CSV (take week-1 rows only)."""
    path = REPO_ROOT / f"warps_{season}_game_priors.csv"
    if not path.exists():
        path = DATA_HIST / f"warps_{season}_game_priors.csv"
    if not path.exists():
        return {}
    priors = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            if str(row.get("week", "0")) != "1":
                continue
            away = normalize_tla(row["away_tla"])
            home = normalize_tla(row["home_tla"])
            if away not in priors:
                priors[away] = float(row["away_warps_wins"])
            if home not in priors:
                priors[home] = float(row["home_warps_wins"])
    return priors


# ── Blend ─────────────────────────────────────────────────────────────────────

def blend(prior_17, pyth_rate, games_played, shrinkage):
    """Return blended 17-game win total."""
    pyth_17 = pyth_rate * SEASON_GAMES
    return (prior_17 * shrinkage + pyth_17 * games_played) / (shrinkage + games_played)


# ── Edge recomputation ────────────────────────────────────────────────────────

def recompute_edges(row, hwp, awp, fhs, fas):
    """Recompute spread and ML edges given updated fair values."""
    row = dict(row)

    mhs = row.get("market_home_spread", "")
    home_ml = row.get("market_home_moneyline", "")
    away_ml = row.get("market_away_moneyline", "")

    # Spread edges
    if mhs not in ("", None):
        mhs_f = float(mhs)
        hse = round(mhs_f - fhs, 2)
        ase = round(fas - float(row.get("market_away_spread") or -mhs_f), 2)
        row["home_spread_edge"] = str(hse)
        row["away_spread_edge"] = str(ase)
        abs_edge = abs(hse)
        row["spread_overlay_edge_points"] = str(round(abs_edge, 2))
        if hse > 0:
            row["spread_overlay_side"] = "HOME"
            row["spread_overlay_team"] = normalize_tla(row.get("home_tla", ""))
        elif hse < 0:
            row["spread_overlay_side"] = "AWAY"
            row["spread_overlay_team"] = normalize_tla(row.get("away_tla", ""))
        else:
            row["spread_overlay_side"] = ""
            row["spread_overlay_team"] = ""

    # ML edges — no-vig probs are market-derived (unchanged), we only update model edge
    if home_ml not in ("", None) and away_ml not in ("", None):
        h_nv = nvig_prob(home_ml)
        a_nv = nvig_prob(away_ml)
        # Recalculate hold against updated no-vig (market data unchanged, just re-derive)
        raw_h = abs(float(home_ml))
        raw_a = abs(float(away_ml)) if float(away_ml) > 0 else float(away_ml)
        # Standard no-vig normalization
        h_impl = abs(float(home_ml)) / (abs(float(home_ml)) + 100) if float(home_ml) < 0 else 100 / (float(away_ml) + 100)
        a_impl = abs(float(away_ml)) / (abs(float(away_ml)) + 100) if float(away_ml) < 0 else 100 / (float(away_ml) + 100)

        # Use the already-stored no-vig probs (market-derived, not re-derived here)
        h_nv_stored = row.get("home_ml_no_vig_prob", "")
        a_nv_stored = row.get("away_ml_no_vig_prob", "")
        if h_nv_stored not in ("", None):
            h_nv = float(h_nv_stored)
        if a_nv_stored not in ("", None):
            a_nv = float(a_nv_stored)

        hme = round(hwp - h_nv, 4)
        ame = round(awp - a_nv, 4)
        row["home_ml_edge"] = str(hme)
        row["away_ml_edge"] = str(ame)

        if hme > ame:
            row["ml_overlay_side"] = "HOME"
            row["ml_overlay_team"] = normalize_tla(row.get("home_tla", ""))
            row["ml_overlay_edge_prob"] = str(round(hme, 4))
            # EV: bet $1, wins (1/|ml|*100) if fav or ml/100 if dog
            h_ml_f = float(home_ml)
            payout = (100 / abs(h_ml_f)) if h_ml_f < 0 else (h_ml_f / 100)
            row["ml_overlay_ev"] = str(round(hwp * payout - (1 - hwp), 4))
        else:
            row["ml_overlay_side"] = "AWAY"
            row["ml_overlay_team"] = normalize_tla(row.get("away_tla", ""))
            row["ml_overlay_edge_prob"] = str(round(ame, 4))
            a_ml_f = float(away_ml)
            payout = (100 / abs(a_ml_f)) if a_ml_f < 0 else (a_ml_f / 100)
            row["ml_overlay_ev"] = str(round(awp * payout - (1 - awp), 4))

    return row


# ── Main ─────────────────────────────────────────────────────────────────────

def run(season, through_week, shrinkage, dry_run):
    actuals = load_actuals(season, through_week)
    priors = load_preseason_priors(season)

    if not priors:
        print(f"ERROR: no preseason priors found for {season}")
        return

    # Build blended ratings
    ratings = {}  # {tla: blended_17}
    print(f"\nWARPS in-season update — {season} through Week {through_week}")
    print(f"Pythagorean exponent {PYTH_EXP}, shrinkage {shrinkage}\n")
    print(f"{'Team':<6} {'Prior':>6} {'Pyth%':>6} {'Pyth17':>7} {'Blnd17':>7} {'Δ':>6} {'GP':>3}")
    print("─" * 48)

    for tla in sorted(priors):
        prior = priors[tla]
        s = actuals.get(tla, {"pf": 0, "pa": 0, "games": 0})
        gp = s["games"]
        if gp == 0:
            blended = prior
            pr = prior / SEASON_GAMES
        else:
            pr = pythagorean(s["pf"], s["pa"])
            blended = blend(prior, pr, gp, shrinkage)
        ratings[tla] = blended
        delta = blended - prior
        print(f"{tla:<6} {prior:>6.2f} {pr*100:>5.1f}% {pr*17:>7.2f} {blended:>7.2f} {delta:>+6.2f} {gp:>3}")

    print()

    # Load overlay CSV
    overlay_path = DATA_HIST / f"warps_{season}_market_overlay.csv"
    json_path = SITE_DATA / "warpsMarketOverlay.json"

    if not overlay_path.exists():
        print(f"Overlay CSV not found: {overlay_path}")
        return

    with open(overlay_path) as f:
        original = list(csv.DictReader(f))
    if not original:
        print("Overlay CSV is empty")
        return
    fieldnames = list(original[0].keys())

    updated = []
    changed = 0
    for row in original:
        away = normalize_tla(row.get("away_tla", ""))
        home = normalize_tla(row.get("home_tla", ""))

        baway = ratings.get(away)
        bhome = ratings.get(home)
        if baway is None or bhome is None:
            updated.append(row)
            continue

        hwp = fair_hwp(bhome, baway)
        awp = 1.0 - hwp
        fhs = fair_spread(bhome, baway)
        fas = -fhs

        old_hwp = float(row.get("home_win_prob") or 0)
        if abs(hwp - old_hwp) > 0.0005:
            changed += 1

        new_row = dict(row)
        new_row["away_warps_wins"] = f"{baway:.2f}"
        new_row["home_warps_wins"] = f"{bhome:.2f}"
        new_row["fair_home_spread"] = f"{fhs:.1f}"
        new_row["fair_away_spread"] = f"{fas:.1f}"
        new_row["home_win_prob"] = f"{hwp:.4f}"
        new_row["away_win_prob"] = f"{awp:.4f}"
        new_row["home_fair_moneyline"] = ml_str(hwp)
        new_row["away_fair_moneyline"] = ml_str(awp)

        new_row = recompute_edges(new_row, hwp, awp, fhs, fas)
        updated.append(new_row)

    print(f"Games updated (>0.05% win-prob shift): {changed} / {len(original)}")

    if dry_run:
        print("\n[DRY RUN] No files written.\n")
        # Print a few updated week-5 rows as a sanity check
        wk5 = [r for r in updated if r.get("week") == "5"][:4]
        for r in wk5:
            print(f"  {r['matchup_key']}: hwp={r['home_win_prob']} fhs={r['fair_home_spread']} edge={r.get('spread_overlay_edge_points','')}")
        return

    # Write CSV
    with open(overlay_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(updated)
    print(f"Written: {overlay_path}")

    # Write JSON — preserve numeric types for numeric columns
    NUM_COLS = {
        "away_warps_wins", "home_warps_wins", "fair_home_spread", "fair_away_spread",
        "home_win_prob", "away_win_prob", "market_home_spread", "market_away_spread",
        "market_home_moneyline", "market_away_moneyline", "market_total",
        "home_spread_edge", "away_spread_edge", "spread_overlay_edge_points",
        "home_ml_no_vig_prob", "away_ml_no_vig_prob", "moneyline_hold",
        "home_ml_edge", "away_ml_edge", "ml_overlay_edge_prob", "ml_overlay_ev",
        "week", "season",
    }

    def coerce(k, v):
        if v in ("", None):
            return None
        if k in NUM_COLS:
            try:
                return float(v)
            except (ValueError, TypeError):
                pass
        return v

    json_rows = [{k: coerce(k, v) for k, v in row.items()} for row in updated]
    with open(json_path, "w") as f:
        json.dump(json_rows, f, indent=2)
    print(f"Written: {json_path}")
    print()


def main():
    p = argparse.ArgumentParser(
        description="Update WARPS ratings with in-season Pythagorean expectation"
    )
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--through-week", type=int, default=None,
                   help="Latest completed/graded week (default: auto-detect)")
    p.add_argument("--shrinkage", type=float, default=DEFAULT_SHRINKAGE,
                   help=f"Prior weight in games-equivalent (default: {DEFAULT_SHRINKAGE})")
    p.add_argument("--dry-run", action="store_true",
                   help="Print summary without writing files")
    args = p.parse_args()
    through_week = args.through_week
    if through_week is None:
        through_week = latest_graded_week(args.season)
        if through_week == 0:
            print("No graded weeks found — nothing to update.")
            return
        print(f"Auto-detected latest graded week: {through_week}")
    run(args.season, through_week, args.shrinkage, args.dry_run)


if __name__ == "__main__":
    main()
