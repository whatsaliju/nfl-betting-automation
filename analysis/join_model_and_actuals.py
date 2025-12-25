#!/usr/bin/env python3

import pandas as pd
import os
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------
HISTORICAL_DIR = "data/historical"
ACTUAL_BETS_FILE = os.path.join(HISTORICAL_DIR, "my_actual_bets.csv")
OUTPUT_DIR = "data/analysis"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# TEAM NAME → ABBREV
# (MUST MATCH YOUR CANONICAL MAP)
# -----------------------------
TEAM_MAP = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WSH",
}

# -----------------------------
# HELPERS
# -----------------------------
def normalize_matchup(game_str: str) -> str:
    """
    Converts 'Philadelphia Eagles @ Washington Commanders'
    → 'PHI@WSH'
    """
    try:
        away, home = game_str.split(" @ ")
        return f"{TEAM_MAP[away]}@{TEAM_MAP[home]}"
    except Exception:
        return None

# -----------------------------
# MAIN
# -----------------------------
def main():
    if not os.path.exists(ACTUAL_BETS_FILE):
        raise FileNotFoundError("❌ my_actual_bets.csv not found")

    actuals = pd.read_csv(ACTUAL_BETS_FILE)

    # Normalize matchup key
    actuals["matchup_key"] = actuals["game"].apply(normalize_matchup)

    # Load all available master tables
    master_files = sorted([
        f for f in os.listdir(HISTORICAL_DIR)
        if f.startswith("week") and f.endswith("_master.csv")
    ])

    if not master_files:
        raise FileNotFoundError("❌ No week*_master.csv files found")

    masters = []
    for f in master_files:
        df = pd.read_csv(os.path.join(HISTORICAL_DIR, f))
        masters.append(df)

    master = pd.concat(masters, ignore_index=True)

    # JOIN: actual bets → model snapshot (LOCK preferred)
    joined = actuals.merge(
        master,
        on=["week", "matchup_key"],
        how="left",
        suffixes=("_bet", "_model")
    )

    # Select high-signal columns only
    cols = [
        # Your bet
        "week",
        "game",
        "bet_type",
        "amount",
        "line",
        "odds",
        "result_bet",

        # Model (LOCK snapshot)
        "has_lock",
        "lock_classification",
        "lock_recommendation",
        "lock_confidence",

        # Model outcome
        "result",
        "final_margin",
        "final_total",
    ]

    # Some columns may not exist yet — filter safely
    cols = [c for c in cols if c in joined.columns]
    joined = joined[cols]

    out_path = os.path.join(
        OUTPUT_DIR,
        f"model_vs_actuals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    joined.to_csv(out_path, index=False)

    print("✅ Model vs Actuals join complete")
    print(f"📄 Output written to: {out_path}")
    print("\nPreview:")
    print(joined.head(10))


if __name__ == "__main__":
    main()
