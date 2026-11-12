#!/usr/bin/env python3
"""Move last season's (or a dry run's) week files out of the live folders.

data/week{N}/ and data/historical/week{N}_master.* are reused every season, so files a
new season hasn't overwritten yet get mixed into its pages (Week 10 2026 showed an Aug
dry run's 14 games next to the real 14). This moves them to data/archive/before_{season}/.

  Week folders     a stage whose metadata.json timestamp is before the cutoff is stale.
                   All stages stale -> the whole folder moves; some stale -> only those
                   stage files move and metadata.json keeps the rest.
                   A folder without metadata.json for a week the live season hasn't
                   reached (current_week.json) is last season's: the whole folder moves.
  Masters          data/historical/week*_master.{csv,json} whose rows are all from an
                   earlier season move, and so does the master of any folder that moved
                   whole (2025's weekWC master is labelled season 2026).
  Preseason (weekPRE*) folders and masters are never touched.

Cutoff: --cutoff YYYY-MM-DD, else two days before the season's first game (nflverse),
else Aug 1 of the season.

Usage: archive_season.py --season 2026 [--cutoff 2026-09-07] [--apply]
Without --apply it only prints what it would move.
"""

import argparse
import csv
import io
import json
import shutil
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HIST = DATA / "historical"
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"


def default_cutoff(season):
    try:
        text = urllib.request.urlopen(GAMES_URL, timeout=60).read().decode()
        days = [r["gameday"] for r in csv.DictReader(io.StringIO(text))
                if r["season"] == str(season) and r["game_type"] == "REG" and r["gameday"]]
        if days:
            return date.fromisoformat(min(days)) - timedelta(days=2)
    except Exception:
        pass
    return date(season, 8, 1)


def is_preseason(name):
    return name.lower().startswith("weekpre")


def stage_files(folder, stage):
    return [p for p in folder.iterdir() if p.is_file() and (p.name.startswith(stage + ".") or p.name.startswith(stage + "_"))]


def plan_folder(folder, cutoff):
    meta_path = folder / "metadata.json"
    if not meta_path.exists():
        return None, [], None
    meta = json.loads(meta_path.read_text())
    stages = meta.get("stages", [])
    stale, keep = [], []
    for e in stages:
        try:
            ts = datetime.fromisoformat(str(e["timestamp"])[:19]).date()
        except (KeyError, ValueError):
            keep.append(e)
            continue
        (stale if ts < cutoff else keep).append(e)
    if not stale:
        return "keep", [], meta
    if not keep:
        return "all", [p for p in folder.iterdir() if p.is_file()], meta
    files = [f for e in stale for f in stage_files(folder, e["stage"])]
    return "partial", files, {**meta, "stages": keep}


def master_seasons(path):
    try:
        if path.suffix == ".json":
            rows = json.loads(path.read_text())
        else:
            rows = list(csv.DictReader(open(path)))
        return {int(float(r["season"])) for r in rows if r.get("season") not in (None, "")}
    except Exception:
        return set()


def current_week():
    try:
        return str(json.loads((DATA / "current_week.json").read_text()).get("week"))
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True, help="the live season to keep")
    ap.add_argument("--cutoff", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    cutoff = date.fromisoformat(args.cutoff) if args.cutoff else default_cutoff(args.season)
    dest_root = DATA / "archive" / f"before_{args.season}"
    print(f"Season {args.season}: archiving stages from before {cutoff} into {dest_root.relative_to(ROOT)}"
          f"{'' if args.apply else '  (dry run)'}")

    moves, whole = [], set()
    cw = current_week()
    for folder in sorted(p for p in DATA.glob("week*") if p.is_dir() and not is_preseason(p.name)):
        kind, files, meta = plan_folder(folder, cutoff)
        if kind is None:
            wk = folder.name[4:]
            if wk.isdigit() and cw and cw.isdigit() and int(wk) > int(cw):
                kind, files = "all", [p for p in folder.iterdir() if p.is_file()]
            else:
                print(f"  {folder.name}: no metadata.json, left alone")
                continue
        if kind == "keep":
            continue
        if kind == "all":
            whole.add(folder.name)
        print(f"  {folder.name}: {'whole folder' if kind == 'all' else f'{len(files)} stale stage files'}")
        for f in files:
            moves.append((f, dest_root / folder.name / f.name))
        if kind == "partial" and args.apply:
            moves.append(("rewrite", folder / "metadata.json", meta))

    for path in sorted(HIST.glob("week*_master.*")):
        if is_preseason(path.name) or path.suffix not in (".csv", ".json"):
            continue
        seasons = master_seasons(path)
        folder_name = path.name.split("_master")[0]
        if (seasons and max(seasons) < args.season) or folder_name in whole:
            print(f"  {path.name}: season {sorted(seasons)}{' (folder archived)' if folder_name in whole else ''}")
            moves.append((path, dest_root / "historical" / path.name))

    n = sum(1 for m in moves if m[0] != "rewrite")
    if not args.apply:
        print(f"{n} files would move. Re-run with --apply.")
        return
    for m in moves:
        if m[0] == "rewrite":
            m[1].write_text(json.dumps(m[2], indent=2) + "\n")
            continue
        src, dst = m
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    for folder in DATA.glob("week*"):
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    print(f"Moved {n} files.")


if __name__ == "__main__":
    main()
