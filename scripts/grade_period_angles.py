#!/usr/bin/env python3
"""Grade the quarter/half angles at the real period lines logged by log_period_lines.py.

For every finished game with a logged period line, tags the game from the nflverse
schedule (closing spread, kickoff time, wind) with the same rules as the logger, takes
the last line logged before kickoff, and grades it with quarter scores from nflverse
play-by-play. Q4 lines exclude overtime; 2nd-half lines include it (the usual book rule).

Writes data/backtests/period_angles_{season}.json: record per angle x period and per week.
Usage: grade_period_angles.py [--season 2026] [--pbp play_by_play_2026.csv.gz] [--games games.csv]
"""

import argparse
import csv
import gzip
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
from nfl_common import canonical_team  # noqa: E402

ET = ZoneInfo("America/New_York")
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
BETS = {
    "primetime": [("1H", "Under"), ("Q1", "Under")],
    "close": [("Q3", "Under")],
    "big_fav": [("1H", "Over"), ("Q2", "Over"), ("Q4", "Under")],
    "wind": [("1H", "Under")],
}


def fetch(path_or_url, binary=False):
    if path_or_url and Path(path_or_url).exists():
        return Path(path_or_url).read_bytes() if binary else Path(path_or_url).read_text()
    with urllib.request.urlopen(path_or_url, timeout=120) as resp:
        data = resp.read()
    return data if binary else data.decode()


def period_points(pbp_bytes):
    """{game_id: {"Q1".."Q4", "1H", "2H"}} from cumulative scores at the end of each quarter."""
    last = {}
    for r in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(pbp_bytes)))):
        if r.get("season_type") != "REG" or not r.get("qtr"):
            continue
        q = min(int(r["qtr"]), 5)
        last[(r["game_id"], q)] = int(float(r["total_away_score"] or 0)) + int(float(r["total_home_score"] or 0))
    out = {}
    for gid in {g for g, _ in last}:
        cum = [last.get((gid, q)) for q in range(1, 6)]
        for i in range(1, 4):
            if cum[i] is None:
                cum[i] = cum[i - 1]
        q = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, 4)]
        ot = (cum[4] - cum[3]) if cum[4] is not None else 0
        out[gid] = {"Q1": q[0], "Q2": q[1], "Q3": q[2], "Q4": q[3], "1H": q[0] + q[1], "2H": q[2] + q[3] + ot}
    return out


def tally(rows):
    w = sum(1 for r in rows if r == "W")
    l = sum(1 for r in rows if r == "L")
    p = sum(1 for r in rows if r == "P")
    return {"w": w, "l": l, "p": p, "pct": round(w / (w + l), 4) if w + l else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--pbp")
    ap.add_argument("--games")
    args = ap.parse_args()
    lines_path = ROOT / "data" / f"period_lines_{args.season}.csv"
    if not lines_path.exists():
        print(f"No {lines_path.name} yet; nothing to grade")
        return

    logged = {}
    for r in csv.DictReader(open(lines_path)):
        logged.setdefault((r["matchup_key"], r["period"]), []).append(r)

    games = {}
    for r in csv.DictReader(io.StringIO(fetch(args.games or GAMES_URL))):
        if r["season"] != str(args.season) or r["game_type"] != "REG" or not r["home_score"]:
            continue
        mk = f"{canonical_team(r['away_team'])}@{canonical_team(r['home_team'])}"
        ko = datetime.fromisoformat(f"{r['gameday']}T{r['gametime'] or '13:00'}").replace(tzinfo=ET)
        spread = abs(float(r["spread_line"])) if r["spread_line"] else None
        outdoor = r["roof"] in ("outdoors", "open")
        games[r["game_id"]] = {"mk": mk, "week": int(r["week"]), "kickoff": ko, "angles": [
            a for a, ok in (("primetime", ko.hour >= 19 or ko.weekday() in (0, 3)),
                            ("close", spread is not None and spread <= 3),
                            ("big_fav", spread is not None and spread >= 7),
                            ("wind", outdoor and float(r["wind"] or 0) >= 15)) if ok]}
    pts = period_points(fetch(args.pbp or PBP_URL.format(season=args.season), binary=True))

    res, weekly, detail = {}, {}, []
    for gid, g in games.items():
        if gid not in pts:
            continue
        for angle in g["angles"]:
            for period, side in BETS[angle]:
                before = [r for r in logged.get((g["mk"], period), [])
                          if datetime.fromisoformat(r["captured_at"]) < g["kickoff"].astimezone(timezone.utc)]
                if not before:
                    continue
                line = float(before[-1]["total"])
                actual = pts[gid][period]
                outcome = "P" if actual == line else ("W" if (actual > line) == (side == "Over") else "L")
                key = f"{angle}:{period}_{side}"
                res.setdefault(key, []).append(outcome)
                weekly.setdefault(str(g["week"]), []).append(outcome)
                detail.append({"week": g["week"], "matchup_key": g["mk"], "angle": angle, "bet": f"{period} {side}",
                               "line": line, "price": before[-1]["under_price" if side == "Under" else "over_price"],
                               "actual": actual, "result": outcome})

    out = {"season": args.season, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "note": "Angles graded at the last logged real period line before kickoff. Break-even 52.4% at -110.",
           "all": tally([o for v in res.values() for o in v]),
           "by_angle": {k: tally(v) for k, v in sorted(res.items())},
           "by_week": {w: tally(v) for w, v in sorted(weekly.items(), key=lambda x: int(x[0]))},
           "bets": sorted(detail, key=lambda d: (d["week"], d["matchup_key"]))}
    dest = ROOT / "data" / "backtests" / f"period_angles_{args.season}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Period angles {args.season}: {out['all']}")
    for k, v in out["by_angle"].items():
        print(f"  {k:28s} {v['w']}-{v['l']}-{v['p']}")


if __name__ == "__main__":
    main()
