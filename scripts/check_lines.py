#!/usr/bin/env python3
"""Cross-check our published spreads and totals against a second source before they ship.

Our lines come from Action Network scrapes, which sometimes carry an alternate line in
one half of the 'away | home' string (NE@MIA '+16.5 | +6.5' when the game was NE -7).
nflverse publishes a consensus spread_line / total_line for every game, refreshed through
the week, so it makes a cheap independent check.

For each current-week game that hasn't kicked off, compare the engine feed's spread and
total with nflverse; a gap of more than SPREAD_TOL / TOTAL_TOL points is flagged.
Also carries the corrections verify_scraped_lines.py made to the scrape this week
(data/line_verify_latest.json) and a few data checks: a stale scrape (> STALE_HOURS old),
scheduled games missing from the feed or listed twice, and totals outside 30-65.
Writes site/src/data/lineCheck.json (Edge Board banner, email box). If nflverse can't
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
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
from nfl_common import home_spread_from_line, normalize_matchup_key  # noqa: E402

SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
FEED = ROOT / "data" / "historical" / "matrix_engine_feed.json"
OUT = ROOT / "site" / "src" / "data" / "lineCheck.json"
SPREAD_TOL = 2.5
TOTAL_TOL = 3.0
STALE_HOURS = 8
TOTAL_RANGE = (30.0, 65.0)
VERIFY = ROOT / "data" / "line_verify_latest.json"

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


def add_corrections(result, week):
    """Corrections made to this week's scrape, latest per game and market."""
    try:
        v = json.loads(VERIFY.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return
    if str(v.get("week")) != str(week):
        return
    result["corrected"] = [{**c, "source": v.get("source")} for c in v.get("corrected", [])]
    result["verified_at"] = v.get("generated_at")


def add_data_checks(result, feed, week, ref):
    warn = result["warnings"]
    games = [g for g in feed.get("edge_board", []) if str(g.get("week")) == str(week)]
    keys = [normalize_matchup_key(g.get("matchup_key", "")) for g in games]
    for mk in sorted({k for k in keys if keys.count(k) > 1}):
        warn.append(f"{mk} appears {keys.count(mk)} times in the feed")
    if ref:
        for mk in sorted(set(ref) - set(keys)):
            warn.append(f"{mk} is on the schedule but has no lines in the feed")
    for g, mk in zip(games, keys):
        tot = first_total(((g.get("markets") or {}).get("total") or {}).get("line"))
        if tot is not None and not TOTAL_RANGE[0] <= tot <= TOTAL_RANGE[1]:
            warn.append(f"{mk} total {tot:g} is outside {TOTAL_RANGE[0]:g}-{TOTAL_RANGE[1]:g}")
    scrapes = sorted((ROOT / "data").glob("action_all_markets_*.csv"), key=lambda f: f.name)
    if scrapes:
        with open(scrapes[-1], newline="") as fh:
            stamps = [r.get("Fetched", "") for r in csv.DictReader(fh) if r.get("Fetched")]
        try:
            fetched = datetime.strptime(max(stamps), "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York"))
            hours = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
            if hours > STALE_HOURS:
                warn.append(f"latest scrape is {hours:.0f}h old ({max(stamps)} ET)")
        except ValueError:
            pass


def main():
    feed = json.loads(FEED.read_text())
    ctx = feed.get("current_context", {})
    season, week = ctx.get("season"), ctx.get("week")
    result = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "season": season, "week": week, "source": "nflverse", "checked": 0, "flagged": [],
              "corrected": [], "warnings": []}
    try:
        week_num = int(float(week))
    except (TypeError, ValueError):
        week_num = None
    ref = nflverse_week_lines(season, week_num) if season and week_num else None
    add_corrections(result, week)
    add_data_checks(result, feed, week, ref)
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
    print(f"Line check week {week}: {result['checked']} games vs {result['source']}, {len(result['flagged'])} flagged, "
          f"{len(result['corrected'])} corrected at scrape, {len(result['warnings'])} warnings")
    for c in result["corrected"]:
        print(f"  corrected {c['matchup_key']} {c['market']}: '{c['scraped']}' -> '{c['corrected']}'")
    for w in result["warnings"]:
        print(f"  warning: {w}")
    for f in result["flagged"]:
        for i in f["issues"]:
            print(f"  {f['matchup_key']} {i['field']}: ours {i['ours']} vs consensus {i['consensus']} (raw '{i['raw']}')")


if __name__ == "__main__":
    main()
