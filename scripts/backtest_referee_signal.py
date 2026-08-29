#!/usr/bin/env python3
"""
Backtest four referee-signal configurations against the WARPS game edge dataset.

Walk-forward: for each game in season N, referee stats are computed from
all prior seasons only (no lookahead bias).

Versions tested:
  V0  Baseline      — no referee filter; take every WARPS pick above edge threshold
  V1  Fade-conflict — skip picks where referee strongly conflicts with our side
  V2  Align gate    — only play when referee aligned (>50% for our side) or unknown
  V3  Strict        — edge > 2.0 wins AND referee aligned

Output:
  data/backtests/referee_signal/comparison_summary.csv  (one row per version)
  data/backtests/referee_signal/{version}_picks.csv     (pick-level detail)
"""

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT       = Path(__file__).resolve().parents[1]
EDGES_CSV  = ROOT / "data" / "backtests" / "warps_game_edges" / "warps_game_edges.csv"
REF_DB_CSV = ROOT / "data" / "historical" / "referee_outcome_db.csv"
OUT_DIR    = ROOT / "data" / "backtests" / "referee_signal"


def normalize_ref_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", str(name).lower())


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_edges(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["spread_result"].notna() & df["spread_edge_points"].notna()].copy()
    df["pick_wins"] = df["spread_result"] == "win"
    # Favorite side from market spread (market_home_spread < 0 means home favored)
    df["favorite_side"] = df["market_home_spread"].apply(lambda x: "HOME" if x < 0 else "AWAY")
    return df


def load_ref_db(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["ref_key"] = df["referee"].apply(normalize_ref_name)
    return df


# ─── Walk-forward referee stats ───────────────────────────────────────────────

def build_walkforward_ref_stats(ref_db: pd.DataFrame, seasons: list, min_sample: int) -> dict:
    """
    Returns {season: {ref_key: {ats_pct, n}}} using only prior-season data.
    """
    stats_by_season = {}
    for season in seasons:
        prior = ref_db[ref_db["season"] < season]
        season_stats = {}
        for ref_key, rows in prior.groupby("ref_key"):
            wins   = (rows["favorite_ats"] == "win").sum()
            losses = (rows["favorite_ats"] == "loss").sum()
            total  = wins + losses
            if total < min_sample:
                continue
            season_stats[ref_key] = {"ats_pct": wins / total, "n": int(total)}
        stats_by_season[season] = season_stats
    return stats_by_season


# ─── Signal computation ───────────────────────────────────────────────────────

def ats_for_our_side(ref_stats: dict, pick_side: str, favorite_side: str) -> tuple:
    """
    Return (ats_prob_for_pick_side, sample_size).
    ref_stats contains ats_pct = P(favorite covers).
    If we pick the favorite, we want high ats_pct.
    If we pick the underdog, we want low ats_pct (1 - ats_pct is our alignment).
    """
    ats_pct = ref_stats.get("ats_pct")
    n = ref_stats.get("n", 0)
    if ats_pct is None:
        return None, 0
    if pick_side == favorite_side:
        return ats_pct, n
    return 1.0 - ats_pct, n


def classify_alignment(prob: float | None, n: int, min_sample: int) -> str:
    if prob is None or n < min_sample:
        return "unknown"
    if prob >= 0.55:
        return "strong_aligned"
    if prob >= 0.50:
        return "aligned"
    if prob >= 0.45:
        return "neutral"
    if prob >= 0.40:
        return "weak_conflict"
    return "conflict"


# ─── Per-row enrichment ───────────────────────────────────────────────────────

def enrich_edges(edges: pd.DataFrame, ref_db: pd.DataFrame, min_sample: int) -> pd.DataFrame:
    edges = edges.copy()

    # Build (season, away_team, home_team) → ref_key lookup
    ref_lookup = {}
    for _, r in ref_db.iterrows():
        key = (int(r["season"]), str(r["away_team"]).upper(), str(r["home_team"]).upper())
        ref_lookup[key] = r["ref_key"]

    edges["ref_key"] = edges.apply(
        lambda r: ref_lookup.get(
            (int(r["season"]), str(r["away_team"]).upper(), str(r["home_team"]).upper()),
        ), axis=1,
    )
    edges["ref_found"] = edges["ref_key"].notna()

    seasons = sorted(edges["season"].unique())
    wf_stats = build_walkforward_ref_stats(ref_db, seasons, min_sample)

    def compute_alignment(row):
        season_stats = wf_stats.get(int(row["season"]), {})
        ref_key = row["ref_key"]
        if pd.isna(ref_key) or ref_key not in season_stats:
            return pd.Series({"ref_ats_for_our_side": None, "ref_n": 0, "ref_alignment": "unknown"})
        prob, n = ats_for_our_side(
            season_stats[ref_key],
            str(row["spread_pick_side"]),
            str(row["favorite_side"]),
        )
        alignment = classify_alignment(prob, n, min_sample)
        return pd.Series({"ref_ats_for_our_side": prob, "ref_n": n, "ref_alignment": alignment})

    print("Computing per-game referee alignment (this takes ~10s)…")
    ref_cols = edges.apply(compute_alignment, axis=1)
    return pd.concat([edges, ref_cols], axis=1)


# ─── Version filters ──────────────────────────────────────────────────────────

def make_filters(edge_threshold: float):
    def v0(row):
        return abs(row["spread_edge_points"]) >= edge_threshold

    def v1(row):
        return v0(row) and row["ref_alignment"] not in {"conflict"}

    def v2(row):
        return v0(row) and row["ref_alignment"] in {"aligned", "strong_aligned", "unknown"}

    def v3(row):
        return (abs(row["spread_edge_points"]) >= 2.0 and
                row["ref_alignment"] in {"aligned", "strong_aligned"})

    return [
        ("V0_baseline",      v0, f"No referee filter (WARPS edge ≥ {edge_threshold})"),
        ("V1_fade_conflict",  v1, "Skip when referee strongly conflicts"),
        ("V2_align_gate",     v2, "Only play when referee aligned or unknown"),
        ("V3_strict",         v3, "Edge > 2.0 wins + referee aligned"),
    ]


# ─── Backtest ─────────────────────────────────────────────────────────────────

def run_backtest(
    edges: pd.DataFrame,
    ref_db: pd.DataFrame,
    out_dir: Path,
    min_sample: int = 10,
    edge_threshold: float = 1.5,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)

    enriched = enrich_edges(edges, ref_db, min_sample)

    versions = make_filters(edge_threshold)
    summary_rows = []

    DETAIL_COLS = [
        "season", "week", "matchup_key", "away_team", "home_team",
        "spread_pick_side", "spread_pick_team", "spread_edge_points",
        "favorite_side", "ref_key", "ref_n", "ref_ats_for_our_side",
        "ref_alignment", "spread_result", "pick_wins", "spread_roi",
    ]

    for version_name, filt_fn, description in versions:
        mask = enriched.apply(filt_fn, axis=1)
        picks = enriched[mask].copy()

        total   = len(picks)
        wins    = int(picks["pick_wins"].sum())
        win_pct = wins / total if total else 0
        roi     = (wins * 1.0 - (total - wins) * 1.1) / total if total else 0

        aligned  = picks[picks["ref_alignment"].isin(["aligned", "strong_aligned"])]
        conflict = picks[picks["ref_alignment"].isin(["conflict", "weak_conflict"])]
        unknown  = picks[picks["ref_alignment"] == "unknown"]

        summary_rows.append({
            "version":              version_name,
            "description":          description,
            "picks":                total,
            "wins":                 wins,
            "win_pct":              round(win_pct, 4),
            "roi_pct":              round(roi * 100, 2),
            "ref_found_pct":        round(picks["ref_found"].mean() * 100 if total else 0, 1),
            "aligned_picks":        len(aligned),
            "aligned_win_pct":      round(aligned["pick_wins"].mean() if len(aligned) else 0, 4),
            "conflict_picks":       len(conflict),
            "conflict_win_pct":     round(conflict["pick_wins"].mean() if len(conflict) else 0, 4),
            "unknown_picks":        len(unknown),
            "unknown_win_pct":      round(unknown["pick_wins"].mean() if len(unknown) else 0, 4),
        })

        out_cols = [c for c in DETAIL_COLS if c in picks.columns]
        picks[out_cols].to_csv(out_dir / f"{version_name}_picks.csv", index=False)
        print(f"{version_name}: {total} picks, {win_pct:.1%} win rate, ROI {roi*100:+.1f}%")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out_dir / "comparison_summary.csv", index=False)

    print(f"\n{'─'*70}")
    print("COMPARISON SUMMARY")
    print(f"{'─'*70}")
    display = summary[["version", "picks", "win_pct", "roi_pct", "aligned_win_pct", "conflict_win_pct"]]
    display = display.rename(columns={
        "win_pct": "win%", "roi_pct": "roi%",
        "aligned_win_pct": "aligned_win%", "conflict_win_pct": "conflict_win%",
    })
    print(display.to_string(index=False))
    print(f"\nSaved to {out_dir}")
    return summary


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--edges",          type=Path,  default=EDGES_CSV)
    parser.add_argument("--ref-db",         type=Path,  default=REF_DB_CSV)
    parser.add_argument("--output",         type=Path,  default=OUT_DIR)
    parser.add_argument("--min-ref-sample", type=int,   default=10)
    parser.add_argument("--edge-threshold", type=float, default=1.5)
    args = parser.parse_args()

    if not args.ref_db.exists():
        print(f"Referee outcome DB not found at {args.ref_db}.")
        print("Run: python3 scripts/build_referee_outcome_db.py")
        raise SystemExit(1)

    edges  = load_edges(args.edges)
    ref_db = load_ref_db(args.ref_db)

    print(f"Loaded {len(edges):,} graded WARPS games ({int(edges['season'].min())}–{int(edges['season'].max())})")
    print(f"Loaded {len(ref_db):,} referee outcome rows ({int(ref_db['season'].min())}–{int(ref_db['season'].max())})")

    run_backtest(
        edges, ref_db, args.output,
        min_sample=args.min_ref_sample,
        edge_threshold=args.edge_threshold,
    )


if __name__ == "__main__":
    main()
