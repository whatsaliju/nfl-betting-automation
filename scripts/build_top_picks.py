#!/usr/bin/env python3
"""Contest picks: rank this week's spread sides and totals by expected points.

Built for a points contest (win 1, push 0.5, loss 0; picks are graded at lines
posted Thursday before 4pm ET and can be made until kickoff; 100 picks a season,
at most 10 a week). Since a loss costs nothing, every slot should be filled with
the best expected value available.

Expected points for every side and total come from 2015-2025 results against the
closing line: how often a dog / favorite / over / under wins or pushes when taken
at a line `d` points better than the market's current number. The contest line
is our last line snapshot before Thursday 4pm ET; the market line is the latest
snapshot. Signals with a graded history then add their edge on top:

  - engine spread / total play: 2025 replay + this season's live ledger
  - WARPS spread lean (edge >= 1 pt, Weeks 1-5 only): preseason WARPS vs close
  - Over on a team that started under (Week 6+): from teamTrends.json

Signal rates are shrunk toward 50% with a Beta(25, 25) prior so short or
tuned-on records can't look stronger than they are. Writes site/src/data/topPicks.json.
"""

import argparse
import csv
import io
import json
import math
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "historical"
SITE_DATA = ROOT / "site" / "src" / "data"
OUT = SITE_DATA / "topPicks.json"
SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
TLA = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
ET = ZoneInfo("America/New_York")
PRIOR = 25            # Beta(25, 25): worth 50 games at 50%
TOP_N = 10
EARLY_WEEKS = 5
SEASON_BUDGET = 100
LAST_WEEK = 18


def shrunk(wins, losses):
    a, b = wins + PRIOR, losses + PRIOR
    mean = a / (a + b)
    # Normal approximation to the Beta's 90% interval; accurate since a, b >= 25.
    sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    return {"expected": mean, "low": mean - 1.645 * sd, "high": mean + 1.645 * sd, "history": f"{wins}-{losses}"}


def load_schedule():
    with urllib.request.urlopen(SCHEDULES_URL, timeout=60) as resp:
        return [r for r in csv.DictReader(io.StringIO(resp.read().decode())) if r["game_type"] == "REG"]


class LineValue:
    """Expected points for a dog/fav/over/under taken `d` points better than the close (2015-2025)."""

    def __init__(self, schedule):
        self.dist = {k: Counter() for k in ("dog", "fav", "over", "under")}
        for r in schedule:
            if not (2015 <= int(r["season"]) <= 2025) or not r["home_score"] or not r["spread_line"] or not r["total_line"]:
                continue
            hs, aws = int(r["home_score"]), int(r["away_score"])
            s = float(r["spread_line"])            # expected home margin
            u = hs - aws - s                       # home cover margin at the close
            if s != 0:
                self.dist["fav" if s > 0 else "dog"][u] += 1
                self.dist["dog" if s > 0 else "fav"][-u] += 1
            v = hs + aws - float(r["total_line"])
            self.dist["over"][v] += 1
            self.dist["under"][-v] += 1

    def ev(self, kind, d):
        c = self.dist[kind]
        n = sum(c.values())
        win = sum(k for u, k in c.items() if u + d > 0)
        push = sum(k for u, k in c.items() if u + d == 0)
        return (win + 0.5 * push) / n


def warps_early_history():
    w = l = 0
    path = ROOT / "data" / "backtests" / "warps_game_edges" / "warps_game_edges.csv"
    for r in csv.DictReader(open(path)):
        if r["game_type"] != "REG" or int(r["week"]) > EARLY_WEEKS or not r["market_home_spread"] or not r["home_score"]:
            continue
        mk, fair = float(r["market_home_spread"]), float(r["fair_home_spread"])
        edge = mk - fair
        if abs(edge) < 1:
            continue
        margin = float(r["home_score"]) - float(r["away_score"])
        m = (margin + mk) if edge > 0 else (-margin - mk)
        if m:
            w += m > 0
            l += m < 0
    return w, l


def engine_history(season):
    rec = {"spread": [0, 0], "total": [0, 0]}
    replay = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "pick_results.csv"
    ledger = HIST / f"live_pick_ledger_{season}.csv"
    for path in (replay, ledger):
        if not path.exists():
            continue
        for r in csv.DictReader(open(path)):
            m = r.get("market")
            if m in rec and r.get("result") in ("win", "loss"):
                rec[m][0 if r["result"] == "win" else 1] += 1
    return rec


def num(text):
    try:
        return float(str(text).split("(")[0].strip().lstrip("ou"))
    except ValueError:
        return None


def parse_lines(snap):
    """(home spread, total) from a snapshot row. The home half of the spread is used:
    the scraped halves can disagree and the away half has carried bad values."""
    parts = [p.strip() for p in str(snap.get("spread_line") or "").split("|")]
    home = num(parts[1]) if len(parts) == 2 else None
    if home is None and len(parts) == 2 and num(parts[0]) is not None:
        home = -num(parts[0])
    tparts = [p.strip() for p in str(snap.get("total_line") or "").split("|")]
    total = num(tparts[0]) if tparts and tparts[0] else None
    return home, total


def contest_cutoff(week_games):
    """Thursday 4pm ET of the week: lines are posted before then."""
    first = min(datetime.fromisoformat(g["gameday"]).date() for g in week_games)
    thursday = first - timedelta(days=(first.weekday() - 3) % 7)
    return datetime(thursday.year, thursday.month, thursday.day, 16, 0, tzinfo=ET)


def build(season, week):
    schedule = load_schedule()
    lv = LineValue(schedule)
    week_games = [g for g in schedule if g["season"] == str(season) and g["week"] == str(week)]
    cutoff = contest_cutoff(week_games)
    kickoffs = {}
    for g in week_games:
        mk = f"{TLA.get(g['away_team'], g['away_team'])}@{TLA.get(g['home_team'], g['home_team'])}"
        if g["gameday"] and g["gametime"]:
            kickoffs[mk] = datetime.fromisoformat(f"{g['gameday']}T{g['gametime']}").replace(tzinfo=ET)

    snaps = {}
    snap_path = HIST / f"engine_line_snapshots_{season}.csv"
    if snap_path.exists():
        for r in csv.DictReader(open(snap_path)):
            if r["week"] == str(week):
                snaps.setdefault(r["matchup_key"], []).append(r)

    overlay = {r["matchup_key"]: r for r in json.load(open(SITE_DATA / "warpsMarketOverlay.json"))
               if int(float(r["week"])) == week}
    trends = json.load(open(SITE_DATA / "teamTrends.json"))
    under_start = set(trends["under_start"]["teams"]) if trends.get("season") == season else set()
    us_hist = trends["under_start"]["history"]["under_start_later_over"]
    eng = engine_history(season)
    signal_stats = {
        "engine_spread": ("Betting engine spread play", shrunk(*eng["spread"])),
        "engine_total": ("Betting engine total play", shrunk(*eng["total"])),
        "warps_early": ("WARPS spread lean, Weeks 1–5", shrunk(*warps_early_history())),
        "under_start_over": ("Over on a team that started under", shrunk(us_hist["w"], us_hist["l"])),
    }

    engine_play = {}
    for e in json.load(open(HIST / "matrix_engine_feed.json")).get("edge_board", []):
        best = e.get("best_edge") or {}
        if e.get("season") == season and str(e.get("week")) == str(week) and best.get("status") == "play":
            engine_play[e["matchup_key"]] = (best.get("market"), (best.get("side") or "").upper())

    now = datetime.now(timezone.utc)
    games = sorted(set(snaps) | set(overlay) | set(kickoffs))
    candidates = []
    for mk in games:
        ko = kickoffs.get(mk)
        if ko and ko <= now:
            continue                                   # locked
        away, home = mk.split("@")
        rows = sorted(snaps.get(mk, []), key=lambda r: r["captured_at"])
        before = [r for r in rows if datetime.fromisoformat(r["captured_at"]) <= cutoff]
        contest_row = before[-1] if before else (rows[0] if rows else None)
        latest_row = rows[-1] if rows else None
        ov = overlay.get(mk, {})
        c_home, c_total = parse_lines(contest_row) if contest_row else (None, None)
        m_home, m_total = parse_lines(latest_row) if latest_row else (None, None)
        if c_home is None and ov.get("market_home_spread") not in (None, ""):
            c_home = m_home = float(ov["market_home_spread"])
        if c_total is None and ov.get("market_total") not in (None, ""):
            c_total = m_total = float(ov["market_total"])
        if m_home is None:
            m_home = c_home
        if m_total is None:
            m_total = c_total
        if now < cutoff:
            line_source = "provisional"               # contest lines not posted yet
        else:
            line_source = "thursday" if before else ("first_snapshot" if rows else "market")
        play = engine_play.get(mk)

        markets = []
        if c_home is not None:
            for side, team, line, mline in (("HOME", home, c_home, m_home), ("AWAY", away, -c_home, -m_home)):
                d = line - mline
                kind = "dog" if line > 0 else "fav" if line < 0 else ("dog" if d >= 0 else "fav")
                sigs = []
                if play == ("spread", side):
                    sigs.append("engine_spread")
                if week <= EARLY_WEEKS and (ov.get("spread_overlay_side") or "").upper() == side \
                        and ov.get("spread_overlay_edge_points") not in (None, "") and float(ov["spread_overlay_edge_points"]) >= 1:
                    sigs.append("warps_early")
                markets.append(("spread", side, f"{team} {line:+g}", line, mline, d, kind, sigs))
        if c_total is not None:
            for side, d in (("OVER", m_total - c_total), ("UNDER", c_total - m_total)):
                sigs = []
                if play == ("total", side):
                    sigs.append("engine_total")
                if side == "OVER" and week > EARLY_WEEKS and {away, home} & under_start:
                    sigs.append("under_start_over")
                markets.append(("total", side, f"{side.title()} {c_total:g}", c_total, m_total, d, side.lower(), sigs))

        for market in ("spread", "total"):
            opts = []
            for mkt, side, text, line, mline, d, kind, sigs in markets:
                if mkt != market:
                    continue
                base = lv.ev(kind, d)
                line_gain = base - lv.ev(kind, 0)
                best_sig, expected, low, high = None, base, None, None
                for s in sigs:
                    st = signal_stats[s][1]
                    if st["expected"] + line_gain > expected:
                        best_sig, expected = s, st["expected"] + line_gain
                        low, high = st["low"] + line_gain, st["high"] + line_gain
                opts.append({
                    "matchup": mk,
                    "market": market,
                    "pick": text,
                    "contest_line": line,
                    "market_line": mline,
                    "line_value": round(d, 1),
                    "line_source": line_source,
                    "basis": signal_stats[best_sig][0] if best_sig else {"dog": "Underdog", "fav": "Favorite", "over": "Over", "under": "Under"}[kind] + " at this line",
                    "history": signal_stats[best_sig][1]["history"] if best_sig else None,
                    "also": [signal_stats[s][0] for s in sigs if s != best_sig],
                    "expected": round(expected, 4),
                    "low": round(low, 4) if low is not None else None,
                    "high": round(high, 4) if high is not None else None,
                })
            if opts:
                candidates.append(max(opts, key=lambda o: o["expected"]))

    candidates.sort(key=lambda p: p["expected"], reverse=True)
    return {
        "season": season,
        "week": week,
        "generated_at": now.isoformat(timespec="seconds"),
        "contest_cutoff": cutoff.isoformat(),
        "budget": SEASON_BUDGET,
        "weeks_left": LAST_WEEK - week + 1,
        "max_per_week": TOP_N,
        "baseline": {k: round(lv.ev(k, 0), 4) for k in ("dog", "fav", "over", "under")},
        "picks": candidates[:TOP_N],
        "signals": [{"name": n, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}} for n, s in signal_stats.values()],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    a = ap.parse_args()
    cw = json.load(open(ROOT / "data" / "current_week.json"))
    season = a.season or int(cw["season"])
    week = a.week or int(cw["week"])
    data = build(season, week)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Contest picks week {week} (lines before {data['contest_cutoff']}):")
    for p in data["picks"]:
        print(f"  {p['expected']:.1%}  {p['matchup']:8} {p['pick']:12} value {p['line_value']:+.1f} ({p['line_source']})  {p['basis']}")


if __name__ == "__main__":
    main()
