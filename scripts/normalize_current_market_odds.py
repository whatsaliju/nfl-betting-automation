#!/usr/bin/env python3
"""Normalize current NFL spread/ML odds into the WARPS overlay input shape.

Supported inputs:
- The Odds API JSON response for markets=spreads,h2h
- Action Network-style CSV with Matchup, Market, and Line columns
- Already-normalized CSV keyed by matchup_key

Output columns:
matchup_key, away_team, home_team, away_spread_line, home_spread_line,
away_moneyline, home_moneyline, source, source_book
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "historical" / "current_market_odds.csv"

TEAM_NAME_TO_TLA = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
    "LA Rams": "LAR",
    "Washington Football Team": "WAS",
}

NICKNAME_TO_TLA = {
    "Cardinals": "ARI",
    "Falcons": "ATL",
    "Ravens": "BAL",
    "Bills": "BUF",
    "Panthers": "CAR",
    "Bears": "CHI",
    "Bengals": "CIN",
    "Browns": "CLE",
    "Cowboys": "DAL",
    "Broncos": "DEN",
    "Lions": "DET",
    "Packers": "GB",
    "Texans": "HOU",
    "Colts": "IND",
    "Jaguars": "JAX",
    "Chiefs": "KC",
    "Raiders": "LV",
    "Chargers": "LAC",
    "Rams": "LAR",
    "Dolphins": "MIA",
    "Vikings": "MIN",
    "Patriots": "NE",
    "Saints": "NO",
    "Giants": "NYG",
    "Jets": "NYJ",
    "Eagles": "PHI",
    "Steelers": "PIT",
    "49ers": "SF",
    "Seahawks": "SEA",
    "Buccaneers": "TB",
    "Bucs": "TB",
    "Titans": "TEN",
    "Commanders": "WAS",
}


def canonical_team(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if upper in set(TEAM_NAME_TO_TLA.values()):
        return upper
    if text in TEAM_NAME_TO_TLA:
        return TEAM_NAME_TO_TLA[text]
    if text in NICKNAME_TO_TLA:
        return NICKNAME_TO_TLA[text]
    parts = text.split()
    if parts and parts[-1] in NICKNAME_TO_TLA:
        return NICKNAME_TO_TLA[parts[-1]]
    return upper


def parse_float(value) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        return float(str(value).replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def parse_line_parts(line: str | None) -> list[str]:
    return [part.strip() for part in str(line or "").split("|") if part.strip()]


def first_signed_number(text: str | None) -> float | None:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)", str(text or ""))
    return float(match.group(1)) if match else None


def first_american_odds(text: str | None) -> float | None:
    matches = re.findall(r"([+-]\d{2,4})", str(text or ""))
    if not matches:
        return None
    return float(matches[-1])


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "matchup_key",
        "away_team",
        "home_team",
        "away_spread_line",
        "home_spread_line",
        "away_moneyline",
        "home_moneyline",
        "source",
        "source_book",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_ready_csv(rows: list[dict], source: str) -> list[dict]:
    output = []
    for row in rows:
        matchup_key = row.get("matchup_key") or ""
        away = canonical_team(row.get("away_team") or row.get("away_tla"))
        home = canonical_team(row.get("home_team") or row.get("home_tla"))
        if not matchup_key and away and home:
            matchup_key = f"{away}@{home}"
        if not matchup_key:
            continue
        output.append({
            "matchup_key": matchup_key,
            "away_team": away or matchup_key.split("@")[0],
            "home_team": home or matchup_key.split("@")[-1],
            "away_spread_line": parse_float(row.get("away_spread_line")),
            "home_spread_line": parse_float(row.get("home_spread_line")),
            "away_moneyline": parse_float(row.get("away_moneyline")),
            "home_moneyline": parse_float(row.get("home_moneyline")),
            "source": source,
            "source_book": row.get("source_book") or row.get("bookmaker") or "",
        })
    return output


def normalize_action_csv(rows: list[dict], source: str) -> list[dict]:
    games: dict[str, dict] = {}
    for row in rows:
        matchup = row.get("Matchup") or row.get("matchup") or ""
        if "@" not in matchup:
            continue
        away_raw, home_raw = [part.strip() for part in matchup.split("@", 1)]
        away = canonical_team(away_raw)
        home = canonical_team(home_raw)
        key = f"{away}@{home}"
        item = games.setdefault(key, {
            "matchup_key": key,
            "away_team": away,
            "home_team": home,
            "away_spread_line": None,
            "home_spread_line": None,
            "away_moneyline": None,
            "home_moneyline": None,
            "source": source,
            "source_book": row.get("Book") or row.get("Sportsbook") or row.get("book") or "Action Network",
        })

        market = str(row.get("Market") or row.get("market") or "").lower()
        line = row.get("Line") or row.get("line") or ""
        parts = parse_line_parts(line)
        if "spread" in market:
            away_spread = first_signed_number(parts[0] if parts else line)
            if away_spread is not None:
                item["away_spread_line"] = away_spread
                item["home_spread_line"] = -away_spread
        elif "moneyline" in market or market in {"ml", "h2h"}:
            if len(parts) >= 2:
                item["away_moneyline"] = first_american_odds(parts[0])
                item["home_moneyline"] = first_american_odds(parts[1])
            else:
                odds = re.findall(r"([+-]\d{2,4})", line)
                if len(odds) >= 2:
                    item["away_moneyline"] = float(odds[0])
                    item["home_moneyline"] = float(odds[1])
    return list(games.values())


def select_bookmaker(game: dict, preferred_book: str | None) -> dict | None:
    bookmakers = game.get("bookmakers") or []
    if not bookmakers:
        return None
    if preferred_book:
        preferred = preferred_book.lower()
        for book in bookmakers:
            if preferred in str(book.get("key", "")).lower() or preferred in str(book.get("title", "")).lower():
                return book
    return bookmakers[0]


def normalize_odds_api_json(path: Path, preferred_book: str | None) -> list[dict]:
    games = json.loads(path.read_text())
    output = []
    for game in games:
        away = canonical_team(game.get("away_team"))
        home = canonical_team(game.get("home_team"))
        if not away or not home:
            continue
        book = select_bookmaker(game, preferred_book)
        item = {
            "matchup_key": f"{away}@{home}",
            "away_team": away,
            "home_team": home,
            "away_spread_line": None,
            "home_spread_line": None,
            "away_moneyline": None,
            "home_moneyline": None,
            "source": str(path),
            "source_book": book.get("title") or book.get("key") if book else "",
        }
        for market in (book or {}).get("markets", []):
            outcomes = market.get("outcomes") or []
            if market.get("key") == "spreads":
                for outcome in outcomes:
                    team = canonical_team(outcome.get("name"))
                    if team == away:
                        item["away_spread_line"] = parse_float(outcome.get("point"))
                    elif team == home:
                        item["home_spread_line"] = parse_float(outcome.get("point"))
            elif market.get("key") == "h2h":
                for outcome in outcomes:
                    team = canonical_team(outcome.get("name"))
                    if team == away:
                        item["away_moneyline"] = parse_float(outcome.get("price"))
                    elif team == home:
                        item["home_moneyline"] = parse_float(outcome.get("price"))
        if item["away_spread_line"] is not None and item["home_spread_line"] is None:
            item["home_spread_line"] = -item["away_spread_line"]
        if item["home_spread_line"] is not None and item["away_spread_line"] is None:
            item["away_spread_line"] = -item["home_spread_line"]
        output.append(item)
    return output


def normalize_input(path: Path, input_format: str, preferred_book: str | None) -> list[dict]:
    if input_format == "odds-api-json":
        return normalize_odds_api_json(path, preferred_book)
    rows = read_csv(path)
    if input_format == "normalized-csv":
        return normalize_ready_csv(rows, str(path))
    if input_format == "action-csv":
        return normalize_action_csv(rows, str(path))
    if rows and "matchup_key" in rows[0]:
        return normalize_ready_csv(rows, str(path))
    if rows and "Matchup" in rows[0] and "Market" in rows[0]:
        return normalize_action_csv(rows, str(path))
    raise ValueError("Could not infer input format; pass --input-format explicitly")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize current NFL market odds")
    parser.add_argument("input", type=Path)
    parser.add_argument("--input-format", choices=["auto", "odds-api-json", "action-csv", "normalized-csv"], default="auto")
    parser.add_argument("--preferred-book", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = normalize_input(args.input, args.input_format, args.preferred_book)
    write_csv(args.output, rows)
    print(json.dumps({
        "input": str(args.input),
        "output": str(args.output),
        "rows": len(rows),
        "priced_spreads": sum(1 for row in rows if row["away_spread_line"] is not None),
        "priced_moneylines": sum(1 for row in rows if row["away_moneyline"] is not None),
    }, indent=2))


if __name__ == "__main__":
    main()
