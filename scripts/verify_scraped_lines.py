#!/usr/bin/env python3
"""Correct bad numbers in the Action Network scrape before anything else reads it.

Source of truth, in order:
  1. The Odds API: the median line across every US book it returns (DraftKings,
     FanDuel, BetMGM, Caesars, ...). One call per run (h2h, spreads, totals).
  2. nflverse games.csv consensus spread_line / total_line (free, no moneyline).
  If neither is reachable the scrape is left as is and nothing is corrected.

For each game that hasn't kicked off (Game Time shows AM/PM):
  Spread     the halves must mirror (within a point) and the home number must be
             within SPREAD_TOL of the reference; otherwise the line is rewritten
             to the reference number, keeping the scraped prices.
  Total      over and under must match (within a point) and sit within TOTAL_TOL
             of the reference; otherwise rewritten to the reference total.
  Moneyline  the two prices must make a sane market (implied probabilities sum to
             0.97-1.15) and the favorite must match the spread's favorite;
             otherwise replaced with the reference moneyline (Odds API only).

The CSV is rewritten in place, so the engine, master JSON, feed, contest picks,
site and email all see the corrected number. Every change is appended to
data/line_corrections_{season}.csv and the latest run's changes go to
data/line_verify_latest.json (check_lines.py shows them on the Edge Board and in
the email as "corrected").

Usage: verify_scraped_lines.py WEEK [--csv path] [--odds-json path]
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
from nfl_common import canonical_team, home_spread_from_line  # noqa: E402

SPREAD_TOL = 2.5
TOTAL_TOL = 3.0
HALF_TOL = 1.0
ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
LATEST = ROOT / "data" / "line_verify_latest.json"

NUM = re.compile(r"([+-]?\d+(?:\.\d+)?)")
PRICE = re.compile(r"\(([+-]?\d+)\)")


def round_half(x):
    return round(x * 2) / 2


def fmt_spread(x):
    return "PK" if x == 0 else f"{x:+g}"


def implied(american):
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)


def odds_api_reference(api_key=None, path=None):
    """{(away, home): {'spread', 'total', 'ml': (away, home), 'books'}} from The Odds API."""
    if path:
        games = json.loads(Path(path).read_text())
    elif api_key:
        query = urllib.parse.urlencode({"apiKey": api_key, "regions": "us",
                                        "markets": "h2h,spreads,totals", "oddsFormat": "american"})
        try:
            with urllib.request.urlopen(f"{ODDS_URL}?{query}", timeout=30) as resp:
                games = json.loads(resp.read().decode())
        except Exception as exc:
            print(f"Odds API unavailable ({type(exc).__name__}); falling back to nflverse", file=sys.stderr)
            return None
    else:
        return None
    now = datetime.now(timezone.utc)
    out = {}
    for g in games:
        try:
            kick = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if not path and (kick < now or kick > now + timedelta(days=8)):
            continue  # live or a later week
        home_name, away_name = g["home_team"], g["away_team"]
        spreads, totals, ml_a, ml_h = [], [], [], []
        for b in g.get("bookmakers", []):
            for m in b.get("markets", []):
                oc = {o.get("name"): o for o in m.get("outcomes", [])}
                if m["key"] == "spreads" and home_name in oc and "point" in oc[home_name]:
                    spreads.append(float(oc[home_name]["point"]))
                elif m["key"] == "totals" and "Over" in oc and "point" in oc["Over"]:
                    totals.append(float(oc["Over"]["point"]))
                elif m["key"] == "h2h" and home_name in oc and away_name in oc:
                    ml_a.append(oc[away_name]["price"])
                    ml_h.append(oc[home_name]["price"])
        key = (canonical_team(away_name), canonical_team(home_name))
        out[key] = {
            "spread": round_half(statistics.median(spreads)) if spreads else None,
            "total": round_half(statistics.median(totals)) if totals else None,
            "ml": (round(statistics.median(ml_a)), round(statistics.median(ml_h))) if ml_a else None,
            "books": len(g.get("bookmakers", [])),
        }
    return out


def nflverse_reference(season, week):
    try:
        from check_lines import nflverse_week_lines
    except Exception:
        return None
    lines = nflverse_week_lines(season, week) if season and week else None
    if lines is None:
        return None
    out = {}
    for mk, (spread, total, _) in lines.items():
        away, home = mk.split("@")
        out[(away, home)] = {"spread": spread, "total": total, "ml": None, "books": None}
    return out


def parts(line):
    return [p.strip() for p in str(line or "").split("|")]


def numbers(line, strip_ou=False):
    vals = []
    for p in parts(line):
        p = p.lstrip("ou") if strip_ou else p
        p = PRICE.sub("", p)
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
    return out + [""] * (2 - len(out))


def moneylines(line):
    vals = []
    for p in parts(line):
        m = NUM.search(p)
        vals.append(int(float(m.group(1))) if m else None)
    return vals


def check_game(rows, ref):
    """Return [(market, raw, corrected, reason)] and rewrite rows' Line in place."""
    by_market = {r["Market"]: r for r in rows}
    changes = []
    sp_row, tot_row, ml_row = by_market.get("Spread"), by_market.get("Total"), by_market.get("Moneyline")

    if sp_row and ref.get("spread") is not None:
        raw = sp_row["Line"]
        vals = numbers(raw)
        ours = home_spread_from_line(raw, ml_row["Line"] if ml_row else None)
        reason = None
        if len(vals) != 2 or None in vals:
            reason = "unreadable"
        elif abs(vals[0] + vals[1]) > HALF_TOL:
            reason = "halves disagree"
        elif ours is None or abs(ours - ref["spread"]) > SPREAD_TOL:
            reason = f"{abs(ours - ref['spread']):g} pts off consensus" if ours is not None else "unreadable"
        if reason:
            pa, ph = prices(raw)
            new = f"{fmt_spread(-ref['spread'])}{pa} | {fmt_spread(ref['spread'])}{ph}"
            sp_row["Line"] = new
            changes.append(("Spread", raw, new, reason))

    if tot_row and ref.get("total") is not None:
        raw = tot_row["Line"]
        vals = numbers(raw, strip_ou=True)
        reason = None
        if len(vals) != 2 or None in vals:
            reason = "unreadable"
        elif abs(vals[0] - vals[1]) > HALF_TOL:
            reason = "over/under disagree"
        elif abs(vals[0] - ref["total"]) > TOTAL_TOL:
            reason = f"{abs(vals[0] - ref['total']):g} pts off consensus"
        if reason:
            po, pu = prices(raw)
            new = f"o{ref['total']:g}{po} | u{ref['total']:g}{pu}"
            tot_row["Line"] = new
            changes.append(("Total", raw, new, reason))

    if ml_row and ref.get("ml"):
        raw = ml_row["Line"]
        vals = moneylines(raw)
        reason = None
        if len(vals) != 2 or None in vals or 0 in vals:
            reason = "unreadable"
        else:
            s = implied(vals[0]) + implied(vals[1])
            spread = ref.get("spread")
            if not 0.97 <= s <= 1.15:
                reason = f"prices don't form a market (implied {s:.2f})"
            elif spread is not None and abs(spread) >= 2.5 and (vals[1] < vals[0]) != (spread < 0):
                reason = "favorite disagrees with spread"
        if reason:
            a, h = ref["ml"]
            new = f"{a:+d} | {h:+d}"
            ml_row["Line"] = new
            changes.append(("Moneyline", raw, new, reason))
    return changes


def latest_csv():
    files = sorted(glob.glob(str(ROOT / "data" / "action_all_markets_*.csv")), key=os.path.basename)
    return Path(files[-1]) if files else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("week")
    ap.add_argument("--csv", type=Path, default=None)
    ap.add_argument("--odds-json", default=None, help="saved Odds API response (testing)")
    args = ap.parse_args()

    path = args.csv or latest_csv()
    if not path or not path.exists():
        print("No Action Network scrape to verify")
        return
    cw = json.loads((ROOT / "data" / "current_week.json").read_text()) if (ROOT / "data" / "current_week.json").exists() else {}
    season = cw.get("season")
    try:
        week = int(float(args.week))
    except ValueError:
        week = None

    ref, source = odds_api_reference(os.environ.get("ODDS_API_KEY"), args.odds_json), "The Odds API (median of US books)"
    if not ref:
        ref, source = nflverse_reference(season, week), "nflverse consensus"
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)

    result = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "season": season, "week": args.week, "scrape": path.name, "source": source if ref else "unavailable",
              "checked": 0, "missing_reference": [], "corrected": []}
    if not ref:
        LATEST.write_text(json.dumps(result, indent=2) + "\n")
        print("No reference source reachable; scrape left as is")
        return

    games = {}
    for r in rows:
        if "@" not in r.get("Matchup", "") or not re.search(r"\b(AM|PM)\b", r.get("Game Time", "")):
            continue
        away, home = (canonical_team(t.strip()) for t in r["Matchup"].split("@"))
        games.setdefault((away, home), []).append(r)

    log_rows = []
    for (away, home), grows in games.items():
        mk = f"{away}@{home}"
        g_ref = ref.get((away, home))
        if not g_ref:
            result["missing_reference"].append(mk)
            continue
        result["checked"] += 1
        for market, raw, new, reason in check_game(grows, g_ref):
            item = {"matchup_key": mk, "market": market, "scraped": raw, "corrected": new, "reason": reason,
                    "reference": {"spread": g_ref["spread"], "total": g_ref["total"], "ml": g_ref["ml"]}}
            result["corrected"].append(item)
            log_rows.append({"logged_at": result["generated_at"], "season": season, "week": args.week,
                             "scrape": path.name, "matchup_key": mk, "market": market, "scraped": raw,
                             "corrected": new, "reason": reason, "source": source})

    if log_rows:
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        log = ROOT / "data" / f"line_corrections_{season}.csv"
        new_file = not log.exists()
        with open(log, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(log_rows[0]))
            if new_file:
                w.writeheader()
            w.writerows(log_rows)
    LATEST.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified {result['checked']} games in {path.name} against {source}: {len(log_rows)} corrected")
    for c in result["corrected"]:
        print(f"  {c['matchup_key']} {c['market']}: '{c['scraped']}' -> '{c['corrected']}' ({c['reason']})")
    if result["missing_reference"]:
        print(f"  no reference for: {', '.join(result['missing_reference'])}")


if __name__ == "__main__":
    main()
