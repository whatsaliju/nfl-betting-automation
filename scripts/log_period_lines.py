#!/usr/bin/env python3
"""Log quarter and half lines for the week's unplayed games, and flag the period angles.

Why: a 2017-2026 walk-forward on nflverse play-by-play (2,550 games, lines built from
the full-game close) found four quarter/half angles that held in both 2017-21 and
2022-26:
  primetime (SNF/MNF/TNF)   1st-half Under, Q1 Under
  spread <= 3               Q3 Under (and 1st-half Under)
  spread >= 7               1st-half Over, Q2 Over, Q4 Under
  wind >= 15 mph            1st-half Under
Books set period lines off the full-game number, so these need the real period lines to
be graded. This script records them each Workflow 3 run.

Sources, cheapest first:
  1. Action Network's public scoreboard feed (free). Its shape isn't documented, so the
     parser accepts the two layouts it has used; if nothing parses, a small sample of
     the response is saved to data/period_lines_debug.json for fixing.
  2. Odds API event odds, only when (1) gave nothing: 1st-half and Q1 totals for games
     kicking off within 30 hours, at most once per ET day, only with quota >= 150
     (2 credits per game).

Writes:
  data/period_lines_{season}.csv   one row per game x period per run (append)
  data/period_angles_latest.json   this week's angle plays, with the latest real line

Never fails the workflow: every network problem is logged and skipped.
Usage: log_period_lines.py WEEK [--season 2026]
"""

import argparse
import csv
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
sys.path.insert(0, str(ROOT / "scripts"))
from nfl_common import canonical_team  # noqa: E402

ET = ZoneInfo("America/New_York")
DATA = ROOT / "data"
DEBUG = DATA / "period_lines_debug.json"
STATE = DATA / "period_lines_state.json"
ANGLES = DATA / "period_angles_latest.json"
AN_URL = "https://api.actionnetwork.com/web/v2/scoreboard/nfl"
AN_PERIODS = {"firsthalf": "1H", "secondhalf": "2H", "firstquarter": "Q1", "secondquarter": "Q2",
              "thirdquarter": "Q3", "fourthquarter": "Q4"}
AN_V1_TYPES = {"firsthalf": "1H", "secondhalf": "2H", "firstquarter": "Q1", "secondquarter": "Q2",
               "thirdquarter": "Q3", "fourthquarter": "Q4", "1h": "1H", "2h": "2H", "1q": "Q1",
               "2q": "Q2", "3q": "Q3", "4q": "Q4"}
ODDS_EVENTS = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events"
ODDS_MARKETS = {"totals_h1": "1H", "totals_q1": "Q1"}
ODDS_QUOTA_FLOOR = 150
FIELDS = ["captured_at", "season", "week", "matchup_key", "kickoff", "period", "total",
          "over_price", "under_price", "home_spread", "books", "source"]
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/124.0 Safari/537.36", "Accept": "application/json",
           "Referer": "https://www.actionnetwork.com/nfl/odds"}

# Angle definitions (period, side) and the football reason, shown with each play.
ANGLE_RULES = [
    ("primetime", lambda g: g["primetime"], [("1H", "Under"), ("Q1", "Under")],
     "Primetime: slow scripted starts. Q1 went under in all 10 seasons tested."),
    ("close", lambda g: g["abs_spread"] is not None and g["abs_spread"] <= 3, [("Q3", "Under")],
     "Spread 3 or less: both teams stay conservative until the 4th. Q3 under in 10 of 10 seasons."),
    ("big_fav", lambda g: g["abs_spread"] is not None and g["abs_spread"] >= 7,
     [("1H", "Over"), ("Q2", "Over"), ("Q4", "Under")],
     "Spread 7+: the favorite scores early, then runs the clock."),
    ("wind", lambda g: (g.get("wind") or 0) >= 15, [("1H", "Under")],
     "Wind 15+ mph: every period runs under, about 1.3 points in the 1st half."),
]


def now_utc():
    return datetime.now(timezone.utc)


def get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode()), resp.headers


def schedule(season, week):
    """{matchup_key: game} for the week's unplayed games, from nflverse via check_lines."""
    try:
        from check_lines import nflverse_week_lines
        lines = nflverse_week_lines(season, week) or {}
    except Exception as exc:
        print(f"schedule unavailable ({exc})")
        return {}
    out = {}
    for mk, (home_spread, total, kick) in lines.items():
        ko = datetime.fromisoformat(kick).replace(tzinfo=ET)
        out[mk] = {"matchup_key": mk, "kickoff": ko, "home_spread": home_spread, "total": total,
                   "abs_spread": abs(home_spread) if home_spread is not None else None,
                   "primetime": ko.hour >= 19 or ko.weekday() in (0, 3)}
    return out


def wind_by_game(week_games):
    """Latest Action Network weather scrape (away, home, ..., wind like '12 NNE'): {matchup_key: mph}."""
    files = sorted(DATA.glob("action_weather_*.csv"), key=lambda p: p.stat().st_mtime)
    out = {}
    if not files:
        return out
    try:
        for r in csv.DictReader(open(files[-1])):
            mk = f"{canonical_team(r.get('away'))}@{canonical_team(r.get('home'))}"
            mph = str(r.get("wind") or "").split()
            if mk in week_games and mph and mph[0].replace(".", "").isdigit():
                out[mk] = float(mph[0])
    except Exception:
        return {}
    return out


# ── Action Network ───────────────────────────────────────────────────────────

def an_matchup(game):
    teams = {t.get("id"): t for t in game.get("teams", []) if isinstance(t, dict)}
    away = teams.get(game.get("away_team_id"), {})
    home = teams.get(game.get("home_team_id"), {})
    a = canonical_team(away.get("abbr") or away.get("full_name") or "")
    h = canonical_team(home.get("abbr") or home.get("full_name") or "")
    return f"{a}@{h}" if a and h else None


def an_rows_v2(game):
    """markets = {book_id: {period: {"total": [{side, value, odds}], "spread": [...]}}}"""
    per = {}
    for book, periods in (game.get("markets") or {}).items():
        if not isinstance(periods, dict):
            continue
        for key, mk in periods.items():
            period = AN_PERIODS.get(key)
            if not period or not isinstance(mk, dict):
                continue
            slot = per.setdefault(period, {"total": [], "over": [], "under": [], "spread": [], "books": set()})
            for o in mk.get("total") or []:
                side = str(o.get("side", "")).lower()
                if o.get("value") is not None and side in ("over", "under"):
                    slot["total"].append(float(o["value"]))
                    slot[side].append(o.get("odds"))
                    slot["books"].add(str(book))
            for o in mk.get("spread") or []:
                if str(o.get("side", "")).lower() == "home" and o.get("value") is not None:
                    slot["spread"].append(float(o["value"]))
    return per


def an_rows_v1(game):
    """odds = [{book_id, type, total, over, under, spread_home}]"""
    per = {}
    for o in game.get("odds") or []:
        period = AN_V1_TYPES.get(str(o.get("type", "")).lower())
        if not period:
            continue
        slot = per.setdefault(period, {"total": [], "over": [], "under": [], "spread": [], "books": set()})
        if o.get("total") is not None:
            slot["total"].append(float(o["total"]))
            slot["over"].append(o.get("over"))
            slot["under"].append(o.get("under"))
            slot["books"].add(str(o.get("book_id")))
        if o.get("spread_home") is not None:
            slot["spread"].append(float(o["spread_home"]))
    return per


def action_network(week_games, log):
    rows, sample = [], None
    days = sorted({g["kickoff"].date() for g in week_games.values()})
    for d in days:
        query = urllib.parse.urlencode({"bookIds": "15,30,68,69,71,75,79,123", "date": d.strftime("%Y%m%d"),
                                        "periods": ",".join(["event", *AN_PERIODS])})
        try:
            data, _ = get_json(f"{AN_URL}?{query}", HEADERS)
        except Exception as exc:
            log.append(f"Action Network {d}: {type(exc).__name__} {exc}")
            continue
        games = data.get("games") or []
        if sample is None and games:
            g0 = games[0]
            sample = {"top_keys": sorted(data)[:20], "game_keys": sorted(g0)[:60],
                      "markets_sample": json.dumps(g0.get("markets"))[:3000] if g0.get("markets") else None,
                      "odds_sample": json.dumps((g0.get("odds") or [])[:6])[:3000]}
        for g in games:
            mk = an_matchup(g)
            if mk not in week_games:
                continue
            per = an_rows_v2(g) or an_rows_v1(g)
            for period, s in per.items():
                if not s["total"]:
                    continue
                rows.append({"matchup_key": mk, "period": period, "total": statistics.median(s["total"]),
                             "over_price": median_price(s["over"]), "under_price": median_price(s["under"]),
                             "home_spread": statistics.median(s["spread"]) if s["spread"] else "",
                             "books": len(s["books"]), "source": "action_network"})
    if not rows and sample:
        DEBUG.write_text(json.dumps(sample, indent=2) + "\n")
        log.append(f"Action Network answered but no period lines parsed; sample saved to {DEBUG.name}")
    return rows


def median_price(vals):
    vals = [float(v) for v in vals if v not in (None, "")]
    return round(statistics.median(vals)) if vals else ""


# ── Odds API fallback ────────────────────────────────────────────────────────

def odds_api(week_games, log):
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        log.append("Odds API fallback skipped (no key)")
        return []
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    today = now_utc().astimezone(ET).date().isoformat()
    if state.get("odds_api_day") == today:
        log.append("Odds API fallback skipped (already called today)")
        return []
    try:
        cache = json.loads((DATA / "odds_api_cache.json").read_text())
        remaining = int(cache.get("requests_remaining") or 0)
    except Exception:
        remaining = None
    if remaining is not None and remaining < ODDS_QUOTA_FLOOR:
        log.append(f"Odds API fallback skipped (quota {remaining} < {ODDS_QUOTA_FLOOR})")
        return []
    soon = {mk for mk, g in week_games.items() if now_utc() < g["kickoff"] <= now_utc() + timedelta(hours=30)}
    if not soon:
        log.append("Odds API fallback skipped (no game within 30h)")
        return []
    try:
        events, _ = get_json(f"{ODDS_EVENTS}?{urllib.parse.urlencode({'apiKey': key})}")   # free
    except Exception as exc:
        log.append(f"Odds API events failed ({type(exc).__name__})")
        return []
    rows, left = [], remaining
    for ev in events:
        mk = f"{canonical_team(ev.get('away_team'))}@{canonical_team(ev.get('home_team'))}"
        if mk not in soon:
            continue
        q = urllib.parse.urlencode({"apiKey": key, "regions": "us", "markets": ",".join(ODDS_MARKETS),
                                    "oddsFormat": "american"})
        try:
            data, hdr = get_json(f"{ODDS_EVENTS}/{ev['id']}/odds?{q}")
            left = hdr.get("x-requests-remaining", left)
        except Exception as exc:
            log.append(f"Odds API {mk} failed ({type(exc).__name__})")
            continue
        per = {}
        for bm in data.get("bookmakers", []):
            for m in bm.get("markets", []):
                period = ODDS_MARKETS.get(m.get("key"))
                if not period:
                    continue
                s = per.setdefault(period, {"total": [], "over": [], "under": [], "books": set()})
                for o in m.get("outcomes", []):
                    side = str(o.get("name", "")).lower()
                    if side in ("over", "under") and o.get("point") is not None:
                        if side == "over":
                            s["total"].append(float(o["point"]))
                        s[side].append(o.get("price"))
                        s["books"].add(bm.get("key"))
        for period, s in per.items():
            if s["total"]:
                rows.append({"matchup_key": mk, "period": period, "total": statistics.median(s["total"]),
                             "over_price": median_price(s["over"]), "under_price": median_price(s["under"]),
                             "home_spread": "", "books": len(s["books"]), "source": "odds_api"})
    state["odds_api_day"] = today
    STATE.write_text(json.dumps(state) + "\n")
    log.append(f"Odds API fallback: {len(rows)} period lines for {len(soon)} games ({left} credits left)")
    return rows


# ── output ───────────────────────────────────────────────────────────────────

def latest_lines(path, week):
    """{(matchup_key, period): row} latest logged line per game/period this week."""
    out = {}
    if path.exists():
        for r in csv.DictReader(open(path)):
            if r["week"] == str(week):
                out[(r["matchup_key"], r["period"])] = r
    return out


def build_angles(week_games, lines, season, week):
    plays = []
    for mk, g in sorted(week_games.items(), key=lambda x: x[1]["kickoff"]):
        if g["kickoff"] <= now_utc():
            continue
        for name, rule, bets, why in ANGLE_RULES:
            if not rule(g):
                continue
            for period, side in bets:
                ln = lines.get((mk, period))
                plays.append({"matchup_key": mk, "kickoff": g["kickoff"].isoformat(), "angle": name,
                              "period": period, "side": side,
                              "line": float(ln["total"]) if ln else None,
                              "price": (ln["under_price"] if side == "Under" else ln["over_price"]) if ln else None,
                              "line_source": ln["source"] if ln else None, "why": why})
    ANGLES.write_text(json.dumps({"season": season, "week": week,
                                  "generated_at": now_utc().isoformat(timespec="seconds"),
                                  "note": "Quarter/half angles from a 2017-2026 backtest at lines built from the "
                                          "full-game close; about 52-56%. Graded at real logged lines by "
                                          "grade_period_angles.py.",
                                  "plays": plays}, indent=2) + "\n")
    return plays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("week")
    ap.add_argument("--season", type=int, default=None)
    args = ap.parse_args()
    if not args.week.isdigit():
        print(f"Week {args.week}: period lines logged for regular-season weeks only")
        return
    week = int(args.week)
    season = args.season
    if season is None:
        try:
            season = int(json.loads((DATA / "current_week.json").read_text())["season"])
        except Exception:
            season = now_utc().year if now_utc().month >= 8 else now_utc().year - 1

    games = schedule(season, week)
    upcoming = {mk: g for mk, g in games.items() if g["kickoff"] > now_utc()}
    for mk, w in wind_by_game(upcoming).items():
        upcoming[mk]["wind"] = w
    log = []
    rows = action_network(upcoming, log) if upcoming else []
    if not rows and upcoming:
        rows = odds_api(upcoming, log)

    path = DATA / f"period_lines_{season}.csv"
    stamp = now_utc().isoformat(timespec="seconds")
    if rows:
        new = not path.exists()
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            for r in rows:
                w.writerow({**r, "captured_at": stamp, "season": season, "week": week,
                            "kickoff": upcoming[r["matchup_key"]]["kickoff"].isoformat()})
    plays = build_angles(upcoming, latest_lines(path, week), season, week)

    for line in log:
        print(line)
    print(f"Week {week}: {len(rows)} period lines logged for {len({r['matchup_key'] for r in rows})} games; "
          f"{len(plays)} angle plays")
    for p in plays:
        ln = f"{p['line']} ({p['price']})" if p["line"] is not None else "no line yet"
        print(f"  {p['matchup_key']:8s} {p['period']} {p['side']:5s} {ln:16s} [{p['angle']}]")


if __name__ == "__main__":
    main()
