#!/usr/bin/env python3
"""Correct bad numbers in the Action Network scrape before anything else reads it.

Layered so the paid Odds API is the last resort, not the first call:

  1. The scrape itself. A bad spread is almost always one real half plus an
     alternate line in the other ("+7.5 | +17.5" when the game is DAL -7.5), so the
     right number is usually already there.
  2. Free references: nflverse's consensus spread/total (refreshed through the week)
     and the Odds API response Wf 11 saves every morning (data/current_odds_api.json,
     every US book). They pick which half is real and confirm a line is sane.
  3. Our own Odds API cache (data/odds_api_cache.json), reused for CACHE_HOURS.
  4. A live Odds API call, only when a game can't be settled above, only for the
     markets that need it (1 credit each), and never when the remaining quota is
     below QUOTA_FLOOR or a call was made in the last MIN_CALL_GAP_MIN minutes.
  5. If no paid number is available, the free reference value.

Checks on each game that hasn't kicked off (Game Time shows AM/PM):
  Spread     halves must mirror (within a point) and sit within SPREAD_TOL of the reference.
  Total      over and under must match (within a point) and sit within TOTAL_TOL.
  Moneyline  prices must form a market (implied sum 0.97-1.15) and pick the spread's
             favorite; there's no free moneyline, so a bad one needs layer 2-4.

The CSV is rewritten in place, so the engine, master JSON, feed, contest picks, site and
email all see the corrected number. Changes are appended to data/line_corrections_{season}.csv;
the latest run goes to data/line_verify_latest.json (shown by check_lines.py).

Usage: verify_scraped_lines.py WEEK [--csv path] [--odds-json path] [--no-live]
"""

import argparse
import csv
import glob
import json
import os
import re
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers"))
sys.path.insert(0, str(ROOT / "scripts"))
from nfl_common import canonical_team  # noqa: E402

SPREAD_TOL = 2.5
TOTAL_TOL = 3.0
HALF_TOL = 1.0
FRESH_HOURS = 6          # a reference this young can supply the replacement number
DAILY_MAX_HOURS = 30     # Wf 11's morning file is still good for picking a half
CACHE_HOURS = 3          # reuse our own paid call this long
MIN_CALL_GAP_MIN = 30
QUOTA_FLOOR = 60         # leave room for Wf 11's daily call
ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
DAILY = ROOT / "data" / "current_odds_api.json"
CACHE = ROOT / "data" / "odds_api_cache.json"
LATEST = ROOT / "data" / "line_verify_latest.json"
MARKET_KEYS = {"Spread": "spreads", "Total": "totals", "Moneyline": "h2h"}

NUM = re.compile(r"([+-]?\d+(?:\.\d+)?)")
PRICE = re.compile(r"\(([+-]?\d+)\)")


def now_utc():
    return datetime.now(timezone.utc)


def round_half(x):
    return round(x * 2) / 2


def fmt_spread(x):
    return "PK" if x == 0 else f"{x:+g}"


def implied(american):
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)


def parse_iso(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ── references ───────────────────────────────────────────────────────────────

def summarize_odds(games, only_upcoming=True):
    """{(away, home): {'spread', 'total', 'ml', 'books'}} medians across books."""
    out, now = {}, now_utc()
    for g in games:
        kick = parse_iso(g.get("commence_time"))
        if kick is None or (only_upcoming and (kick < now or kick > now + timedelta(days=8))):
            continue
        home_name, away_name = g["home_team"], g["away_team"]
        spreads, totals, ml_a, ml_h = [], [], [], []
        for b in g.get("bookmakers", []):
            for m in b.get("markets", []):
                oc = {o.get("name"): o for o in m.get("outcomes", [])}
                if m["key"] == "spreads" and "point" in oc.get(home_name, {}):
                    spreads.append(float(oc[home_name]["point"]))
                elif m["key"] == "totals" and "point" in oc.get("Over", {}):
                    totals.append(float(oc["Over"]["point"]))
                elif m["key"] == "h2h" and home_name in oc and away_name in oc:
                    ml_a.append(oc[away_name]["price"])
                    ml_h.append(oc[home_name]["price"])
        out[(canonical_team(away_name), canonical_team(home_name))] = {
            "spread": round_half(statistics.median(spreads)) if spreads else None,
            "total": round_half(statistics.median(totals)) if totals else None,
            "ml": (round(statistics.median(ml_a)), round(statistics.median(ml_h))) if ml_a else None,
            "books": len(g.get("bookmakers", [])),
        }
    return out


def daily_reference():
    """Wf 11's saved response; its age is the newest book update in it."""
    if not DAILY.exists():
        return None, None
    try:
        games = json.loads(DAILY.read_text())
    except json.JSONDecodeError:
        return None, None
    stamps = [parse_iso(m.get("last_update")) for g in games for b in g.get("bookmakers", [])
              for m in b.get("markets", [])]
    stamps = [s for s in stamps if s]
    if not stamps:
        return None, None
    age = (now_utc() - max(stamps)).total_seconds() / 3600
    return (summarize_odds(games) if age <= DAILY_MAX_HOURS else None), age


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def paid_reference(markets, api_key, allow_live, log):
    """Our cached call if fresh enough and it covers the markets, else one live call."""
    cache = load_cache()
    fetched = parse_iso(cache.get("fetched_at"))
    age_h = (now_utc() - fetched).total_seconds() / 3600 if fetched else None
    if age_h is not None and age_h <= CACHE_HOURS and set(markets) <= set(cache.get("markets", [])):
        log.append(f"used cached Odds API call ({age_h * 60:.0f} min old, 0 credits)")
        return summarize_odds(cache.get("games", []))
    if not allow_live or not api_key:
        log.append("live Odds API call skipped (" + ("no key" if not api_key else "disabled") + ")")
        return None
    if age_h is not None and age_h * 60 < MIN_CALL_GAP_MIN:
        log.append(f"live Odds API call skipped (last call {age_h * 60:.0f} min ago)")
        return None
    remaining = cache.get("requests_remaining")
    if remaining is not None and int(remaining) < QUOTA_FLOOR:
        log.append(f"live Odds API call skipped (quota {remaining} < floor {QUOTA_FLOOR})")
        return None
    query = urllib.parse.urlencode({"apiKey": api_key, "regions": "us", "markets": ",".join(sorted(markets)),
                                    "oddsFormat": "american"})
    try:
        with urllib.request.urlopen(f"{ODDS_URL}?{query}", timeout=30) as resp:
            games = json.loads(resp.read().decode())
            remaining = resp.headers.get("x-requests-remaining")
            used = resp.headers.get("x-requests-last")
    except Exception as exc:
        log.append(f"live Odds API call failed ({type(exc).__name__})")
        return None
    CACHE.write_text(json.dumps({"fetched_at": now_utc().isoformat(timespec="seconds"),
                                 "markets": sorted(markets), "requests_remaining": remaining,
                                 "games": games}) + "\n")
    log.append(f"live Odds API call for {','.join(sorted(markets))} ({used or len(markets)} credits, {remaining} left)")
    return summarize_odds(games)


def nflverse_reference(season, week):
    try:
        from check_lines import nflverse_week_lines
    except Exception:
        return None
    lines = nflverse_week_lines(season, week) if season and week else None
    if lines is None:
        return None
    return {tuple(mk.split("@")): {"spread": s, "total": t, "ml": None} for mk, (s, t, _) in lines.items()}


# ── scrape parsing ───────────────────────────────────────────────────────────

def parts(line):
    return [p.strip() for p in str(line or "").split("|")]


def numbers(line, strip_ou=False):
    vals = []
    for p in parts(line):
        p = PRICE.sub("", p.lstrip("ou") if strip_ou else p)
        if "PK" in p.upper() or "pick" in p.lower():
            vals.append(0.0)
            continue
        m = NUM.search(p)
        vals.append(float(m.group(1)) if m else None)
    return vals


def prices(line):
    out = []
    for p in parts(line):
        m = PRICE.search(p)
        out.append(f" ({m.group(1)})" if m else "")
    return (out + ["", ""])[:2]


def moneylines(line):
    vals = []
    for p in parts(line):
        m = NUM.search(p)
        vals.append(int(float(m.group(1))) if m else None)
    return vals


def near(value, refs, tol):
    """True when value is within tol of every reference that has a number."""
    vals = [r for r in refs if r is not None]
    return bool(vals) and all(abs(value - r) <= tol for r in vals)


# ── per-game decision ────────────────────────────────────────────────────────

def assess(rows, free_refs):
    """Settle what the free layers can. Returns (fixes, pending).

    fixes:   [(market, new_line, reason, source)]
    pending: {market: reason} that need a paid number (or a free fallback).
    """
    by = {r["Market"]: r for r in rows}
    fixes, pending = [], {}
    sp_refs = [r.get("spread") for r in free_refs]
    tot_refs = [r.get("total") for r in free_refs]

    if "Spread" in by:
        vals = numbers(by["Spread"]["Line"])
        if len(vals) != 2 or None in vals:
            pending["Spread"] = "unreadable"
        else:
            away, home = vals
            if abs(away + home) <= HALF_TOL:
                if any(r is not None for r in sp_refs) and not near(home, sp_refs, SPREAD_TOL):
                    pending["Spread"] = "off consensus"
            else:
                good = [c for c in (home, -away) if near(c, sp_refs, SPREAD_TOL)]
                if len(good) == 1:
                    fixes.append(("Spread", good[0], "halves disagree", "scrape half confirmed by free reference"))
                else:
                    pending["Spread"] = "halves disagree"

    if "Total" in by:
        vals = numbers(by["Total"]["Line"], strip_ou=True)
        if len(vals) != 2 or None in vals:
            pending["Total"] = "unreadable"
        else:
            over, under = vals
            if abs(over - under) <= HALF_TOL:
                if any(r is not None for r in tot_refs) and not near(over, tot_refs, TOTAL_TOL):
                    pending["Total"] = "off consensus"
            else:
                good = sorted({c for c in (over, under) if near(c, tot_refs, TOTAL_TOL)})
                if len(good) == 1:
                    fixes.append(("Total", good[0], "over/under disagree", "scrape half confirmed by free reference"))
                else:
                    pending["Total"] = "over/under disagree"

    if "Moneyline" in by:
        vals = moneylines(by["Moneyline"]["Line"])
        spread = next((r for r in sp_refs if r is not None), None)
        if len(vals) != 2 or None in vals or 0 in vals:
            pending["Moneyline"] = "unreadable"
        else:
            s = implied(vals[0]) + implied(vals[1])
            if not 0.97 <= s <= 1.15:
                pending["Moneyline"] = f"prices don't form a market (implied {s:.2f})"
            elif spread is not None and abs(spread) >= 2.5 and (vals[1] < vals[0]) != (spread < 0):
                pending["Moneyline"] = "favorite disagrees with spread"
    return fixes, pending


def write_fix(row, market, value):
    raw = row["Line"]
    a, b = prices(raw)
    if market == "Spread":
        row["Line"] = f"{fmt_spread(-value)}{a} | {fmt_spread(value)}{b}"
    elif market == "Total":
        row["Line"] = f"o{value:g}{a} | u{value:g}{b}"
    else:
        row["Line"] = f"{value[0]:+d} | {value[1]:+d}"
    return raw, row["Line"]


def latest_csv():
    files = sorted(glob.glob(str(ROOT / "data" / "action_all_markets_*.csv")), key=os.path.basename)
    return Path(files[-1]) if files else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("week")
    ap.add_argument("--csv", type=Path, default=None)
    ap.add_argument("--odds-json", default=None, help="use a saved Odds API response as the paid layer (testing)")
    ap.add_argument("--no-live", action="store_true", help="never make a live Odds API call")
    args = ap.parse_args()

    path = args.csv or latest_csv()
    if not path or not path.exists():
        print("No Action Network scrape to verify")
        return
    cw_path = ROOT / "data" / "current_week.json"
    season = json.loads(cw_path.read_text()).get("season") if cw_path.exists() else None
    try:
        week = int(float(args.week))
    except ValueError:
        week = None

    log = []
    nfl = nflverse_reference(season, week) or {}
    daily, daily_age = daily_reference()
    daily = daily or {}
    log.append(f"free references: nflverse {len(nfl)} games, Wf 11 daily file {len(daily)} games"
               + (f" ({daily_age:.0f}h old)" if daily_age is not None else ""))

    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    games = {}
    for r in rows:
        if "@" not in r.get("Matchup", "") or not re.search(r"\b(AM|PM)\b", r.get("Game Time", "")):
            continue
        away, home = (canonical_team(t.strip()) for t in r["Matchup"].split("@"))
        games.setdefault((away, home), []).append(r)

    result = {"generated_at": now_utc().isoformat(timespec="seconds"), "season": season, "week": args.week,
              "scrape": path.name, "checked": 0, "missing_reference": [], "corrected": [], "unresolved": []}
    decided, pending_all = {}, {}
    for key, grows in games.items():
        refs = [x for x in (nfl.get(key), daily.get(key)) if x]
        if not refs:
            result["missing_reference"].append("@".join(key))
        result["checked"] += 1
        fixes, pending = assess(grows, refs)
        decided[key] = fixes
        if pending:
            pending_all[key] = pending

    paid = None
    if pending_all:
        needed = {MARKET_KEYS[m] for p in pending_all.values() for m in p}
        if args.odds_json:
            paid = summarize_odds(json.loads(Path(args.odds_json).read_text()), only_upcoming=False)
            log.append("paid layer from --odds-json")
        else:
            fresh_daily = daily if daily_age is not None and daily_age <= FRESH_HOURS else None
            paid = fresh_daily or paid_reference(needed, os.environ.get("ODDS_API_KEY"), not args.no_live, log)
            if fresh_daily:
                log.append("used Wf 11 daily file as the paid layer (fresh, 0 credits)")
    else:
        log.append("every game settled by the scrape and free references; no Odds API call")

    for key, pending in pending_all.items():
        p, free = (paid or {}).get(key), nfl.get(key) or daily.get(key) or {}
        for market, reason in pending.items():
            field = {"Spread": "spread", "Total": "total", "Moneyline": "ml"}[market]
            if p and p.get(field) is not None:
                decided[key].append((market, p[field], reason, "The Odds API (median of US books)"))
            elif free.get(field) is not None:
                decided[key].append((market, free[field], reason, "free reference (no paid number available)"))
            else:
                result["unresolved"].append({"matchup_key": "@".join(key), "market": market, "reason": reason})

    log_rows = []
    for key, fixes in decided.items():
        by = {r["Market"]: r for r in games[key]}
        for market, value, reason, source in fixes:
            raw, new = write_fix(by[market], market, value)
            if raw == new:
                continue
            mk = "@".join(key)
            result["corrected"].append({"matchup_key": mk, "market": market, "scraped": raw, "corrected": new,
                                        "reason": reason, "source": source})
            log_rows.append({"logged_at": result["generated_at"], "season": season, "week": args.week,
                             "scrape": path.name, "matchup_key": mk, "market": market, "scraped": raw,
                             "corrected": new, "reason": reason, "source": source})
    result["layers"] = log

    if log_rows:
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        corr = ROOT / "data" / f"line_corrections_{season}.csv"
        new_file = not corr.exists()
        with open(corr, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(log_rows[0]))
            if new_file:
                w.writeheader()
            w.writerows(log_rows)
    LATEST.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified {result['checked']} games in {path.name}: {len(log_rows)} corrected, "
          f"{len(result['unresolved'])} unresolved")
    for line in log:
        print(f"  {line}")
    for c in result["corrected"]:
        print(f"  {c['matchup_key']} {c['market']}: '{c['scraped']}' -> '{c['corrected']}' ({c['reason']}; {c['source']})")
    for u in result["unresolved"]:
        print(f"  unresolved {u['matchup_key']} {u['market']}: {u['reason']}")


if __name__ == "__main__":
    main()
