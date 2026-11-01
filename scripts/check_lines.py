#!/usr/bin/env python3
"""Cross-check our published spreads and totals against a second source before they ship.

Our lines come from Action Network scrapes, which sometimes carry an alternate line in
one half of the 'away | home' string (NE@MIA '+16.5 | +6.5' when the game was NE -7).
nflverse publishes a consensus spread_line / total_line for every game, refreshed through
the week, so it makes a cheap independent check.

For each current-week game that hasn't kicked off, compare the engine feed's spread and
total with nflverse; a gap of more than SPREAD_TOL / TOTAL_TOL points is flagged.
Writes site/src/data/lineCheck.json (Edge Board banner, email warning). If nflverse can't
be reached the file says so and nothing is flagged.

Also importable: nflverse_week_lines(season, week) for other scripts (detect_line_moves).
"""

import csv
import io
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
from nfl_common import home_spread_from_line, normalize_matchup_key  # noqa: E402

SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
FEED = ROOT / "data" / "historical" / "matrix_engine_feed.json"
OUT = ROOT / "site" / "src" / "data" / "lineCheck.json"
SPREAD_TOL = 2.5
TOTAL_TOL = 3.0

_cache = {}


def nflverse_week_lines(season, week):
    """{matchup_key: (home_spread, total, kickoff_iso)} for unplayed games, or None if unreachable."""
    key = (int(season), int(week))
    if key in _cache:
        return _cache[key]
    try:
        with urllib.request.urlopen(SCHEDULES_URL, timeout=60) as resp:
            text = resp.read().decode()
    except Exception as exc:  # network failure: the check is skipped, never blocks a run
        print(f"nflverse unavailable ({exc}); line check skipped", file=sys.stderr)
        _cache[key] = None
        return None
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["season"] != str(season) or r["week"] != str(week) or r["home_score"]:
            continue
        mk = normalize_matchup_key(f"{r['away_team']}@{r['home_team']}")
        spread = -float(r["spread_line"]) if r["spread_line"] else None   # spread_line = home margin
        total = float(r["total_line"]) if r["total_line"] else None
        out[mk] = (spread, total, f"{r['gameday']}T{r.get('gametime') or '13:00'}")
    _cache[key] = out
    return out


def first_total(text):
    m = re.search(r"(\d+(?:\.\d+)?)", str(text or "").split("|")[0])
    return float(m.group(1)) if m else None


def main():
    feed = json.loads(FEED.read_text())
    ctx = feed.get("current_context", {})
    season, week = ctx.get("season"), ctx.get("week")
    result = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "season": season, "week": week, "source": "nflverse", "checked": 0, "flagged": []}
    try:
        week_num = int(float(week))
    except (TypeError, ValueError):
        week_num = None
    ref = nflverse_week_lines(season, week_num) if season and week_num else None
    if ref is None:
        result["source"] = "unavailable"
    else:
        for g in feed.get("edge_board", []):
            if str(g.get("week")) != str(week):
                continue
            mk = normalize_matchup_key(g.get("matchup_key", ""))
            if mk not in ref:
                continue  # already played, or not in nflverse yet
            mk_spread, mk_total, _ = ref[mk]
            markets = g.get("markets", {})
            ours_spread = home_spread_from_line((markets.get("spread") or {}).get("line"),
                                                (markets.get("moneyline") or {}).get("line"))
            ours_total = first_total((markets.get("total") or {}).get("line"))
            result["checked"] += 1
            issues = []
            if mk_spread is not None and (ours_spread is None or abs(ours_spread - mk_spread) > SPREAD_TOL):
                issues.append({"field": "spread", "ours": ours_spread, "consensus": mk_spread,
                               "raw": (markets.get("spread") or {}).get("line")})
            if mk_total is not None and (ours_total is None or abs(ours_total - mk_total) > TOTAL_TOL):
                issues.append({"field": "total", "ours": ours_total, "consensus": mk_total,
                               "raw": (markets.get("total") or {}).get("line")})
            if issues:
                result["flagged"].append({"matchup_key": mk, "issues": issues})
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Line check week {week}: {result['checked']} games vs {result['source']}, {len(result['flagged'])} flagged")
    for f in result["flagged"]:
        for i in f["issues"]:
            print(f"  {f['matchup_key']} {i['field']}: ours {i['ours']} vs consensus {i['consensus']} (raw '{i['raw']}')")


if __name__ == "__main__":
    main()
