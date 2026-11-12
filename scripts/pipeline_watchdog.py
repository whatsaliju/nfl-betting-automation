#!/usr/bin/env python3
"""Pipeline watchdog: email Liju when the weekly pipeline breaks or stalls.

Run by .github/workflows/13_pipeline_watchdog.yml in two modes:

  --failed-run NAME URL   a watched workflow just failed (workflow_run trigger): alert now.
  (no args)               scheduled health check, alerting on anything below:

  1. Failed runs        any watched workflow whose run failed, timed out or never started
                        in the last LOOKBACK_HOURS (cancelled runs are ignored).
  2. Week not advanced  every game of the week in data/current_week.json is final
                        (nflverse) and the last one ended more than STALL_HOURS ago.
                        Week 9 2026 sat for three days when Wf 6 failed on setup.
  3. Feed out of sync   matrix_engine_feed.json's week differs from current_week.json.
  4. Stale lines        in season, the newest Action Network scrape is over 3 days old.
  5. No referees        from Wednesday 4pm ET on, the current week has no referee file.

Prints the findings either way; sends one email only when something is wrong.
Needs GITHUB_TOKEN + GITHUB_REPOSITORY (run history) and GMAIL_USER +
GMAIL_APP_PASSWORD (email). Without the Gmail secrets it only prints.
"""

import argparse
import csv
import io
import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RECIPIENT = "lvarughese@gmail.com"
ET = ZoneInfo("America/New_York")
LOOKBACK_HOURS = 26
STALL_HOURS = 30
WATCHED = {
    "1. Referee Data Collection", "2. Initial Market Data", "3. Market Update (with Line-Flip Detection)",
    "4.5 Pro Analysis & Email (Enhanced Organized)", "5. Send Conversational Analysis Email",
    "6. Enhanced Performance Tracker", "6. Grade Week Results", "8 NFL Edge Hub Site Build",
    "10 Deploy NFL Edge Hub to Bluehost", "11 Refresh WARPS Market Overlay",
}
BAD = {"failure", "timed_out", "startup_failure"}
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"


def gh(path):
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/{path}",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def failed_runs(now):
    since = (now - timedelta(hours=LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        data = gh(f"actions/runs?per_page=100&created=%3E%3D{since}")
    except Exception as exc:
        return [f"Couldn't read workflow run history ({type(exc).__name__})."]
    if data is None:
        return []
    out = []
    for r in data.get("workflow_runs", []):
        if r.get("name") in WATCHED and r.get("conclusion") in BAD and r.get("event") != "push":
            when = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(ET)
            out.append(f"{r['name']} {r['conclusion']} ({r['event']}, {when:%a %b %d %I:%M %p} ET): {r['html_url']}")
    return out


def week_checks(now):
    issues = []
    try:
        cw = json.loads((ROOT / "data" / "current_week.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return ["data/current_week.json is missing or unreadable."]
    season, week = str(cw.get("season")), str(cw.get("week"))
    local_now = now.astimezone(ET)
    if local_now.month in (7, 8) and season.isdigit() and int(season) < local_now.year:
        issues.append(f"current_week.json is still season {season}. Run '14 New Season Rollover' with season "
                      f"{local_now.year} (reset_week on) so last season's week files are archived before Week 1.")

    feed = ROOT / "data" / "historical" / "matrix_engine_feed.json"
    try:
        fw = str(json.loads(feed.read_text()).get("current_context", {}).get("week"))
        if fw != week:
            issues.append(f"Site feed shows Week {fw} but current_week.json is Week {week}.")
    except (FileNotFoundError, json.JSONDecodeError):
        issues.append("matrix_engine_feed.json is missing or unreadable.")

    if now.astimezone(ET).month in (8, 9, 10, 11, 12, 1, 2):
        scrapes = sorted((ROOT / "data").glob("action_all_markets_*.csv"), key=lambda f: f.name)
        if scrapes:
            day = scrapes[-1].name.replace("action_all_markets_", "")[:10]
            try:
                age = now.astimezone(ET).date() - datetime.strptime(day, "%Y-%m-%d").date()
                if age.days > 3:
                    issues.append(f"Newest Action Network scrape is {age.days} days old ({scrapes[-1].name}).")
            except ValueError:
                pass

    local = now.astimezone(ET)
    weekday = local.weekday()  # Mon 0 .. Sun 6
    past_wed_4pm = weekday in (3, 4, 5, 6) or (weekday == 2 and local.hour >= 16)
    if week.isdigit() and past_wed_4pm:
        ref = ROOT / "data" / f"week{week}" / f"week{week}_referees.csv"
        if not ref.exists():
            issues.append(f"No referee file for Week {week} ({ref.relative_to(ROOT)}); Wf 1 may have looked for the wrong week.")

    try:
        text = urllib.request.urlopen(GAMES_URL, timeout=60).read().decode()
    except Exception:
        return issues
    games = [g for g in csv.DictReader(io.StringIO(text))
             if g["season"] == season and g["week"] == week and g["game_type"] == "REG"]
    tla = lambda x: {"LA": "LAR", "WSH": "WAS"}.get(x, x)
    scheduled = {f"{tla(g['away_team'])}@{tla(g['home_team'])}" for g in games}
    try:
        board = json.loads(feed.read_text()).get("edge_board", [])
        on_site = {str(r.get("matchup_key")).replace("WSH", "WAS") for r in board if str(r.get("week")) == week}
        extra = sorted(on_site - scheduled) if scheduled else []
        if extra:
            issues.append(f"Site shows {len(extra)} Week {week} games that aren't on the schedule "
                          f"(stale files from another season or a test run?): {', '.join(extra)}")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if games and all(g["home_score"] for g in games):
        last = max(datetime.fromisoformat(f"{g['gameday']}T{g.get('gametime') or '13:00'}").replace(tzinfo=ET)
                   for g in games)
        hours = (now - last).total_seconds() / 3600 - 3.5   # roughly when the last game ended
        if hours > STALL_HOURS:
            issues.append(f"Every Week {week} game is final ({hours:.0f}h ago) but the site is still on Week {week}. "
                          f"Grading (Wf 6) probably didn't run; it advances the week.")
    return issues


def send(subject, lines):
    body = "\n".join(f"- {l}" for l in lines)
    print(subject + "\n" + body)
    user, pw = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        print("(no Gmail credentials; not emailed)")
        return
    msg = MIMEText(body + "\n\nRepo actions: https://github.com/whatsaliju/nfl-betting-automation/actions\n")
    msg["Subject"], msg["From"], msg["To"] = subject, user, RECIPIENT
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    print("alert emailed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--failed-run", nargs=2, metavar=("NAME", "URL"))
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    if args.failed_run:
        name, url = args.failed_run
        send(f"NFL pipeline alert: {name} failed", [f"{name} failed: {url}",
             "Later steps in the chain won't run until this is fixed or re-run."])
        return
    issues = failed_runs(now) + week_checks(now)
    if issues:
        send(f"NFL pipeline alert: {len(issues)} problem{'s' if len(issues) != 1 else ''}", issues)
    else:
        print("Pipeline healthy: no failed runs, week pointer, feed, scrapes and referees look right.")


if __name__ == "__main__":
    sys.exit(main())
