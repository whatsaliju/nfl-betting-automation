#!/usr/bin/env python3
"""Grade the Model view's live picks from its own history, and test early vs late bets.

Every run of Workflow 4.5 commits site/src/data/modelView.json, so git history holds
what the Model view said at every point in the week. For each finished game this script
takes two snapshots of the game's lean:

  late   the last snapshot before kickoff (what you would have bet on game day)
  early  the first snapshot of that week (Tuesday/Wednesday, the opening lines)

and grades each at the line it carried then. Totals and sides, at 53%+ and 55%+.
"late" is the live record; "early vs late" answers whether betting the early number
would have done better than waiting (timing / closing-line value).

Needs full git history (Wf 6 Grade checks out with fetch-depth 0) and the nflverse
schedule for scores. Writes site/src/data/modelViewRecord.json.

Usage: grade_model_view.py [--games games.csv] [--season 2026]
"""

import argparse
import csv
import io
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "src" / "data" / "modelViewRecord.json"
MV_PATH = "site/src/data/modelView.json"
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
TLA = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
TIERS = (0.53, 0.55)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout


def load_results(path, season):
    text = Path(path).read_text() if path else urllib.request.urlopen(GAMES_URL, timeout=60).read().decode()
    kick, score = {}, {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["season"] != str(season) or r["game_type"] != "REG":
            continue
        mk = f"{TLA.get(r['away_team'], r['away_team'])}@{TLA.get(r['home_team'], r['home_team'])}"
        w = int(r["week"])
        kick[(w, mk)] = datetime.fromisoformat(f"{r['gameday']}T{r['gametime'] or '13:00'}:00-05:00")
        if r["home_score"]:
            score[(w, mk)] = (int(r["away_score"]), int(r["home_score"]))
    return kick, score


def snapshots():
    """[(commit_time, modelView dict)] oldest first."""
    out = []
    for line in git("log", "--format=%H|%cI", "--", MV_PATH).splitlines():
        sha, ts = line.split("|")
        try:
            out.append((datetime.fromisoformat(ts), json.loads(git("show", f"{sha}:{MV_PATH}"))))
        except json.JSONDecodeError:
            continue
    return sorted(out, key=lambda x: x[0])


def grade_total(pick, a, h):
    side, line = pick.split()
    line, total = float(line), a + h
    if total == line:
        return None
    return (total > line) == (side == "Over")


def grade_side(pick, away, a, h):
    team, line = pick.rsplit(" ", 1)
    margin = (a - h) if team == away else (h - a)
    m = margin + float(line)
    return None if m == 0 else m > 0


def tally(rows):
    w = sum(1 for r in rows if r)
    n = len(rows)
    return {"w": w, "l": n - w, "pct": round(w / n, 4) if n else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games")
    ap.add_argument("--season", type=int, default=2026)
    args = ap.parse_args()
    kick, score = load_results(args.games, args.season)
    snaps = snapshots()
    if not snaps:
        print("No modelView.json history (shallow checkout?); nothing graded")
        return

    res = {}  # (market, tier, timing) -> [bool]
    weekly = {}
    for (w, mk), t in sorted(kick.items()):
        if (w, mk) not in score:
            continue
        week_snaps = [(ts, mv) for ts, mv in snaps if str(mv.get("week")) == str(w) and ts < t]
        week_snaps = [(ts, next((g for g in mv.get("games", []) if g["matchup"] == mk), None)) for ts, mv in week_snaps]
        week_snaps = [(ts, g) for ts, g in week_snaps if g]
        if not week_snaps:
            continue
        a, h = score[(w, mk)]
        for timing, (ts, g) in (("early", week_snaps[0]), ("late", week_snaps[-1])):
            for market, pick, conf, fn in (
                ("totals", g["total_pick"], g["total_conf"], lambda p: grade_total(p, a, h)),
                ("sides", g["side_pick"], g["side_conf"], lambda p: grade_side(p, g["away"], a, h)),
            ):
                outcome = fn(pick)
                if outcome is None:
                    continue
                for tier in TIERS:
                    if conf >= tier:
                        res.setdefault((market, tier, timing), []).append(outcome)
                        if timing == "late":
                            weekly.setdefault((w, market, tier), []).append(outcome)

    summary = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "season": args.season, "note": "Graded from modelView.json snapshots: 'late' = last before kickoff, "
               "'early' = first of the week, each at the line it showed then.", "markets": {}, "by_week": {}}
    for market in ("totals", "sides"):
        summary["markets"][market] = {
            f"{int(tier * 100)}": {timing: tally(res.get((market, tier, timing), [])) for timing in ("late", "early")}
            for tier in TIERS}
    for (w, market, tier), rows in sorted(weekly.items()):
        summary["by_week"].setdefault(str(w), {})[f"{market}_{int(tier * 100)}"] = tally(rows)
    OUT.write_text(json.dumps(summary, indent=2) + "\n")
    for market, tiers in summary["markets"].items():
        for tier, t in tiers.items():
            print(f"{market} {tier}%+: late {t['late']}  early {t['early']}")


if __name__ == "__main__":
    main()
