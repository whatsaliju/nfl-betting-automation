#!/usr/bin/env python3
"""Append a timestamped snapshot of each game's engine pick and lines.

week{N}_master.json keeps only the most recent run per stage name, so the line a
pick was first made at is overwritten by later runs (including runs after
kickoff). This log keeps every run so the live pick ledger can find the line at
pick time and the last pre-kickoff line.

  Live (Workflow 4.5):  --season 2026 --week 5 --stage update
  Backfill from git:    --season 2026 --week 4 --from-git
"""

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "historical"
STAGES = ["initial", "pre_tnf", "update", "lock", "pre_mnf", "final"]
FIELDS = [
    "captured_at", "season", "week", "matchup_key", "stage", "model_version",
    "classification", "pick_market", "pick_side", "spread_line", "total_line",
    "moneyline_line", "pick_reasons",
]


def snapshot_path(season):
    return HIST / f"engine_line_snapshots_{season}.csv"


def stage_row(game, stage, captured_at, season, week):
    row = {
        "captured_at": captured_at,
        "season": season,
        "week": week,
        "matchup_key": game.get("matchup_key", ""),
        "stage": stage,
        "model_version": game.get(f"{stage}_model_version") or "",
        "classification": game.get(f"{stage}_classification") or "",
        "pick_market": game.get(f"{stage}_pick_market") or "",
        "pick_side": game.get(f"{stage}_pick_side") or "",
        "spread_line": game.get(f"{stage}_sharp_spread_line") or "",
        "total_line": game.get(f"{stage}_sharp_total_line") or "",
        "moneyline_line": game.get(f"{stage}_sharp_moneyline_line") or "",
        "pick_reasons": game.get(f"{stage}_pick_reasons") or "",
    }
    return {k: str(v) for k, v in row.items()}


def content_key(row):
    return tuple(row[f] for f in FIELDS if f not in ("captured_at",))


def load(season):
    path = snapshot_path(season)
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def write(season, rows):
    rows.sort(key=lambda r: (r["captured_at"], int(r["week"]) if str(r["week"]).isdigit() else 0, r["matchup_key"], r["stage"]))
    with open(snapshot_path(season), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def append_unchanged_filtered(existing, new_rows):
    """Skip rows identical to the latest stored snapshot for the same game+stage."""
    last = {}
    for r in existing:
        last[(r["week"], r["matchup_key"], r["stage"])] = content_key(r)
    added = [r for r in new_rows if last.get((r["week"], r["matchup_key"], r["stage"])) != content_key(r)]
    return existing + added, len(added)


def live(season, week, stage):
    path = HIST / f"week{week}_master.json"
    if not path.exists():
        print(f"No master for week {week}")
        return
    games = json.load(open(path))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_rows = [stage_row(g, stage, now, season, week) for g in games
                if str(g.get("season")) == str(season) and g.get(f"has_{stage}")]
    rows, added = append_unchanged_filtered(load(season), new_rows)
    write(season, rows)
    print(f"Snapshot week {week} stage {stage}: {added} new rows")


def from_git(season, week):
    rel = f"data/historical/week{week}_master.json"
    log = subprocess.run(["git", "log", "--reverse", "--format=%H %cI", "--", rel],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    prev = {}
    new_rows = []
    for line in filter(None, log):
        sha, when = line.split(" ", 1)
        try:
            games = json.loads(subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=ROOT,
                                              capture_output=True, text=True, check=True).stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        captured_at = datetime.fromisoformat(when).astimezone(timezone.utc).isoformat(timespec="seconds")
        for g in games:
            if str(g.get("season")) != str(season):
                continue
            for stage in STAGES:
                if not g.get(f"has_{stage}"):
                    continue
                row = stage_row(g, stage, captured_at, season, week)
                key = (g.get("matchup_key"), stage)
                # A stage whose content changed in this commit was rewritten by this run.
                if prev.get(key) != content_key(row):
                    new_rows.append(row)
                    prev[key] = content_key(row)
    existing = [r for r in load(season) if str(r["week"]) != str(week)]
    write(season, existing + new_rows)
    print(f"Backfilled week {week} from git: {len(new_rows)} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", required=True)
    ap.add_argument("--stage")
    ap.add_argument("--from-git", action="store_true")
    a = ap.parse_args()
    if a.from_git:
        from_git(a.season, a.week)
    elif a.stage:
        live(a.season, a.week, a.stage)
    else:
        sys.exit("--stage or --from-git required")


if __name__ == "__main__":
    main()
