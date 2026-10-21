"""Send the weekly betting card email from matrix_engine_feed.json."""
import json
import os
import re
import smtplib
import sys
from glob import glob
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analyzers"))
from nfl_common import canonical_team
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SITE_URL = "https://lijuvarughese.com/matrix.html"
RECIPIENT = "lvarughese@gmail.com"

# ── Load env ─────────────────────────────────────────────────────────────────
week = os.getenv("WEEK", "?")
timestamp = os.getenv("TIME_STAMP", "")
analysis_type = os.getenv("ANALYSIS_TYPE", "ANALYSIS")
subject_prefix = os.getenv("SUBJECT_PREFIX", "UPDATE")
intro_text = os.getenv("INTRO_TEXT", "")
flip_alert = os.getenv("FLIP_ALERT", "")
gmail_user = os.getenv("GMAIL_USER", "")
gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")

# ── Load JSON feed ────────────────────────────────────────────────────────────
feed = {}
for path in ["data/historical/matrix_engine_feed.json", "site/public/matrix_engine_feed.json"]:
    try:
        with open(path) as f:
            feed = json.load(f)
        break
    except (FileNotFoundError, json.JSONDecodeError):
        continue

ctx = feed.get("current_context", {})
wbc = feed.get("weekly_betting_card", {})
cards = wbc.get("cards", [])
edge_board = feed.get("edge_board", [])
edge_lookup = {g["matchup_key"]: g for g in edge_board}

# ── Load WARPS overlay for pick'em section ────────────────────────────────────
overlay_rows = []
for path in ["site/src/data/warpsMarketOverlay.json", "data/historical/warps_2026_market_overlay.csv"]:
    try:
        if path.endswith(".json"):
            with open(path) as f:
                overlay_rows = json.load(f)
        break
    except (FileNotFoundError, json.JSONDecodeError):
        continue
cur_week_str = str(ctx.get("week", week))
overlay_week = [r for r in overlay_rows if str(r.get("week")) == cur_week_str]
# Build overlay lookup by matchup_key (WAS normalization)
def _norm_mk(mk):
    return mk.replace("WSH", "WAS")
overlay_by_mk = {_norm_mk(r["matchup_key"]): r for r in overlay_week}

# Leave out games that have kicked off: they can't be bet, and a late run would otherwise email them.
kickoffs = {}
try:
    with open(f"data/historical/week{cur_week_str}_master.json") as f:
        for g in json.load(f):
            if g.get("kickoff_utc"):
                kickoffs[_norm_mk(g["matchup_key"])] = datetime.fromisoformat(g["kickoff_utc"].replace("Z", "+00:00"))
except (FileNotFoundError, json.JSONDecodeError, ValueError):
    pass
_now = datetime.now(timezone.utc)
started = [c for c in cards if kickoffs.get(_norm_mk(c.get("matchup_key", "")), _now) < _now]
cards = [c for c in cards if c not in started]

plays   = [c for c in cards if c.get("action") == "play"]
watches = [c for c in cards if c.get("action") in ("watch", "lean")]
passes  = [c for c in cards if c.get("action") == "pass"]

# Email only when there's something to act on; every other run just refreshes the site.
# Always:
#   Thu noon-5pm ET: contest lines are set (posted before 4pm).
#   Fri 4pm-midnight ET: after the final injury report (Out/Doubtful), a full day to bet and set lineups.
#   Sun before 1pm ET when a game kicks off within 2.5h: after inactives for the 9:30 / 1pm games.
# Only with a play on a game kicking off within 3h (after its inactives):
#   Thu evening (TNF), Sun afternoon/evening (4pm window, SNF), Mon (MNF).
# A manual run of Workflow 5 always sends.
def _kicks_soon(mk_list, hours):
    return any(_now < k < _now + timedelta(hours=hours) for k in (kickoffs.get(_norm_mk(m)) for m in mk_list) if k)

def _decision_point():
    et = _now.astimezone(ZoneInfo("America/New_York"))
    day, hour = et.weekday(), et.hour
    if day == 3 and 12 <= hour < 17:
        return True
    if day == 4 and hour >= 16:
        return True
    if day == 6 and hour < 13:
        if not kickoffs:  # no master kickoff times: fall back to the 1pm slate
            return hour >= 10
        return any(_now < k < _now + timedelta(hours=2.5) for k in kickoffs.values())
    if day in (0, 3, 6):
        return _kicks_soon([c.get("matchup_key", "") for c in plays], 3)
    return False

if os.getenv("FORCE_SEND") != "true" and not _decision_point():
    print("Not a decision point: site refreshed, no email sent.")
    raise SystemExit(0)

ctx_season     = ctx.get("season", "")
ctx_week_label = ctx.get("week_label", f"Week {week}")
ctx_stage      = (ctx.get("stage") or "").replace("_", " ")
ctx_line = f"{ctx_season} {ctx_week_label}" + (f" - {ctx_stage}" if ctx_stage else "")

# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_score(v):
    return f"{float(v):.1f}" if v is not None else "--"

def fmt_pct(v):
    return f"{float(v):.0f}%" if v is not None else "--"

def signed(v):
    if v is None:
        return "--"
    v = float(v)
    return f"+{v:.1f}" if v > 0 else f"{v:.1f}"

def strip_emoji(text):
    return re.sub(
        r"^[\U0001F300-\U0001FFFF\U00002600-\U000027FF\U00002300-\U000023FF]+\s*",
        "",
        str(text or ""),
    )

def action_style(action):
    if action == "play":
        return ("PLAY", "#16a34a", "#f0fdf4", "#bbf7d0")
    if action in ("watch", "lean"):
        return ("WATCH", "#b45309", "#fffbeb", "#fde68a")
    return ("PASS", "#6b7280", "#f9fafb", "#e5e7eb")

def referee_html(card):
    ref = card.get("referee")
    if not ref:
        return ""
    stats = card.get("referee_stats") or {}
    ou    = stats.get("ou_pct")
    ats   = stats.get("ats_pct")
    n     = stats.get("sample_size", "?")
    fav   = stats.get("favorite", "")
    ats_rec = stats.get("ats_record", "")
    ou_rec  = stats.get("ou_record", "")
    ou_col  = "#15803d" if (ou or 50) >= 55 else ("#1d4ed8" if (ou or 50) <= 45 else "#6b7280")
    ats_col = "#15803d" if (ats or 50) >= 55 else ("#dc2626" if (ats or 50) <= 45 else "#6b7280")
    stats_part = (
        f"&nbsp;&nbsp;ATS <strong style='color:{ats_col};'>{fmt_pct(ats)}</strong>"
        f" ({ats_rec}) {fav}"
        f"&nbsp;&#183;&nbsp;OU <strong style='color:{ou_col};'>{fmt_pct(ou)}</strong>"
        f" ({ou_rec})&nbsp;&#183;&nbsp;n={n}"
    ) if stats else ""
    return (
        "<tr><td style='padding:8px 0 0;'>"
        f"<div style='font-size:12px;color:#6b7280;background:#f8fafc;padding:6px 10px;border-radius:4px;'>"
        f"&#x1F993; <strong style='color:#374151;'>{ref}</strong>{stats_part}"
        "</div></td></tr>"
    )

def warps_html(card):
    edge  = edge_lookup.get(card.get("matchup_key", ""), {})
    warps = edge.get("warps_market_overlay") or {}
    if not warps.get("available"):
        return ""
    fair      = warps.get("fair_home_spread")
    prob      = warps.get("home_win_prob")
    alignment = (warps.get("spread_pick_alignment") or "").replace("_", " ")
    home      = card.get("home_tla", "HOME")
    wp        = (prob or 0) * 100
    return (
        "<tr><td style='padding:6px 0 0;'>"
        "<div style='font-size:12px;color:#1e40af;background:#eff6ff;padding:6px 10px;border-radius:4px;'>"
        f"&#x26A1; WARPS: <strong>{alignment}</strong>"
        f"&nbsp;&#183;&nbsp; {home} fair <strong>{signed(fair)}</strong>"
        f"&nbsp;&#183;&nbsp; Win prob <strong>{fmt_pct(wp)}</strong> {home}"
        "</div></td></tr>"
    )

def reasons_html(card):
    route   = (card.get("route_reason") or "").strip()
    reasons = [r for r in (card.get("main_reasons") or []) if r and r != route][:2]
    if not route and not reasons:
        return ""
    items = "".join(
        f"<li style='margin:0 0 3px;'>{strip_emoji(r)}</li>"
        for r in ([route] if route else []) + reasons
    )
    return (
        "<tr><td style='padding:8px 0 0;'>"
        "<ul style='margin:0;padding:0 0 0 16px;font-size:13px;color:#4b5563;'>"
        f"{items}</ul></td></tr>"
    )

def risk_html(card):
    flags = (card.get("risk_flags") or [])[:3]
    if not flags:
        return ""
    spans = "".join(
        f"<span style='display:inline-block;background:#fef2f2;color:#b91c1c;"
        f"font-size:11px;padding:2px 6px;border-radius:3px;margin:2px 2px 0 0;'>"
        f"&#x26A0; {flag}</span>"
        for flag in flags
    )
    return f"<tr><td style='padding:6px 0 0;'>{spans}</td></tr>"

def render_card(card):
    label, color, bg, badge_bg = action_style(card.get("action"))
    matchup = f"{card.get('away_tla','?')} @ {card.get('home_tla','?')}"
    wk      = card.get("week", "?")
    wk_str  = f"W{wk}" if str(wk).isdigit() else str(wk)
    pick    = (card.get("pick_label") or "").strip()
    if not pick:
        m    = card.get("market", "")
        s    = card.get("side", "")
        pick = f"{m.upper()} {s}".strip() if m else label
    score          = fmt_score(card.get("selector_score"))
    conf           = (card.get("confidence") or "").replace("_", " ").title()
    classification = strip_emoji(card.get("classification") or "")
    conf_td = (
        f"<td style='padding:0 0 0 8px;font-size:12px;color:#6b7280;vertical-align:middle;'>{conf}</td>"
        if conf and conf.lower() != label.lower() else ""
    )
    class_row = (
        f"<tr><td colspan='2' style='padding:4px 0 0;font-size:12px;color:#6b7280;'>{classification}</td></tr>"
        if classification else ""
    )
    return (
        f"<table style='width:100%;border-collapse:collapse;margin:12px 0;"
        f"border-left:4px solid {color};background:{bg};border-radius:0 6px 6px 0;'>"
        "<tr><td style='padding:14px 16px;'>"
        "<table style='width:100%;border-collapse:collapse;'>"
        "<tr>"
        f"<td style='vertical-align:top;'>"
        f"<div style='font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;'>{wk_str}</div>"
        f"<strong style='font-size:17px;color:#111827;'>{matchup}</strong></td>"
        f"<td style='vertical-align:top;text-align:right;white-space:nowrap;padding-left:12px;'>"
        f"<strong style='font-size:22px;color:{color};line-height:1;'>{score}</strong>"
        "<div style='font-size:10px;color:#9ca3af;text-transform:uppercase;'>score</div></td>"
        "</tr>"
        "<tr><td colspan='2' style='padding:6px 0 0;'>"
        "<table style='border-collapse:collapse;'><tr>"
        f"<td style='background:{badge_bg};border-radius:3px;padding:3px 8px;'>"
        f"<strong style='font-size:12px;color:{color};text-transform:uppercase;'>{label}</strong></td>"
        f"<td style='padding:0 0 0 8px;font-size:13px;color:#1f2937;vertical-align:middle;'>"
        f"<strong>{pick}</strong></td>"
        f"{conf_td}"
        "</tr></table></td></tr>"
        f"{class_row}"
        f"{reasons_html(card)}"
        f"{referee_html(card)}"
        f"{warps_html(card)}"
        f"{risk_html(card)}"
        "</table>"
        "</td></tr></table>"
    )

# ── Build pick'em section ─────────────────────────────────────────────────────
def build_pickem_section():
    if not overlay_week:
        return ""
    DAY_ORDER = {"Thu": 0, "Fri": 1, "Sat": 2, "Sun": 3, "Mon": 4}
    games_by_day: dict = {}
    for mk, r in overlay_by_mk.items():
        hwp = r.get("home_win_prob")
        if hwp is None:
            continue
        try:
            hwp = float(hwp)
        except (ValueError, TypeError):
            continue
        away = r.get("away_tla", "")
        home = r.get("home_tla", "")
        if hwp >= 0.5:
            pick, pick_pct = home, round(hwp * 100)
            dog = away
        else:
            pick, pick_pct = away, round((1 - hwp) * 100)
            dog = home
        day = r.get("game_day") or "Sun"
        games_by_day.setdefault(day, []).append({
            "mk": mk, "away": away, "home": home,
            "pick": pick, "pct": pick_pct, "dog": dog,
            "date": r.get("game_date", ""),
        })

    rows_html = ""
    for day in sorted(games_by_day, key=lambda d: DAY_ORDER.get(d, 9)):
        day_games = sorted(games_by_day[day], key=lambda g: g["mk"])
        rows_html += (
            f"<tr><td colspan='3' style='padding:10px 0 4px;font-size:11px;"
            f"text-transform:uppercase;letter-spacing:1px;color:#6b7280;"
            f"border-bottom:1px solid #e5e7eb;'>{day}</td></tr>"
        )
        for g in day_games:
            fav_color = "#15803d"
            dog_color = "#6b7280"
            rows_html += (
                f"<tr>"
                f"<td style='padding:5px 0;font-size:13px;color:{dog_color};width:38%;'>"
                f"{g['away']} @ {g['home']}</td>"
                f"<td style='padding:5px 8px;font-size:13px;font-weight:700;"
                f"color:{fav_color};width:30%;'>▶ {g['pick']}</td>"
                f"<td style='padding:5px 0;font-size:12px;color:#9ca3af;"
                f"width:32%;'>{g['pct']}% win prob</td>"
                f"</tr>"
            )
    if not rows_html:
        return ""
    total = len(overlay_by_mk)
    return (
        f"<h2 style='font-size:16px;color:#111827;border-bottom:2px solid #e5e7eb;"
        f"padding-bottom:8px;margin:28px 0 4px;'>"
        f"Pick'em &nbsp;<span style='font-size:13px;font-weight:400;color:#6b7280;'>"
        f"WARPS straight-up · {total} games</span></h2>"
        f"<table style='width:100%;border-collapse:collapse;font-size:13px;"
        f"margin:0 0 8px;'>"
        f"{rows_html}"
        f"</table>"
        f"<p style='font-size:11px;color:#9ca3af;margin:4px 0 0;'>"
        f"SU pick = team with higher WARPS win probability. "
        f"Pool record through last week: <strong style='color:#15803d;'>41–23 (64%)</strong></p>"
    )

pickem_section = build_pickem_section()

# ── Build sections ────────────────────────────────────────────────────────────
started_note = (
    f"<p style='color:#6b7280;font-size:13px;margin:6px 0 10px;'>{len(started)} game{'s' if len(started) != 1 else ''} "
    f"already kicked off and {'are' if len(started) != 1 else 'is'} left out.</p>"
) if started else ""
plays_html = "".join(render_card(c) for c in plays) if plays else (
    "<p style='color:#9ca3af;font-size:14px;margin:8px 0;'>No plays this week.</p>"
)

watch_section = ""
if watches:
    cards_html = "".join(render_card(c) for c in watches)
    watch_section = (
        f"<h2 style='font-size:16px;color:#111827;border-bottom:2px solid #e5e7eb;"
        f"padding-bottom:8px;margin:28px 0 4px;'>"
        f"Watchlist &nbsp;<span style='color:#b45309;font-weight:400;'>{len(watches)}</span></h2>"
        f"{cards_html}"
    )

pass_section = ""
if passes:
    names = " &nbsp;&#183;&nbsp; ".join(
        f"{c.get('away_tla','?')}@{c.get('home_tla','?')}" for c in passes
    )
    pass_section = (
        "<div style='margin-top:24px;padding:12px 16px;background:#f9fafb;"
        "border-radius:6px;border:1px solid #e5e7eb;'>"
        f"<div style='font-size:12px;color:#6b7280;text-transform:uppercase;"
        f"letter-spacing:1px;margin-bottom:4px;'>Passes ({len(passes)})</div>"
        f"<div style='font-size:13px;color:#9ca3af;'>{names}</div>"
        "</div>"
    )

# ── Injury & lineup changes ──────────────────────────────────────────────────
# Injury report: latest Action Network file vs the previous day's. Starting QBs:
# latest RotoWire lineup file for the week vs the week's first one. Limited to
# teams with games that haven't kicked off.
STATUS_RANK = {"out": 0, "doubtful": 1, "questionable": 2}
SKILL = {"QB", "RB", "WR", "TE"}

def _last_name(name):
    return (name or "").replace(".", " ").split()[-1].lower() if (name or "").strip() else ""

def _read_csv(path):
    import csv
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except (FileNotFoundError, OSError):
        return []

def injury_changes(week, teams):
    reports = sorted(glob("data/action_injuries_*.csv"))
    changes = []
    since = None
    if len(reports) >= 2:
        since = datetime.strptime(reports[-2].split("_")[2], "%Y-%m-%d").strftime("%b %-d")
        def by_player(rows):
            return {(canonical_team(r.get("team")), r.get("player", "")): r for r in rows if r.get("player")}
        old, new = by_player(_read_csv(reports[-2])), by_player(_read_csv(reports[-1]))
        for key, r in new.items():
            if key[0] not in teams:
                continue
            status = (r.get("status") or "").strip()
            before = (old.get(key, {}).get("status") or "").strip()
            if status.lower() != before.lower():
                changes.append({"team": key[0], "player": key[1], "pos": r.get("pos", ""),
                                "now": status, "was": before or "not listed", "injury": r.get("injury", "")})
        for key, r in old.items():
            if key[0] in teams and key not in new and r.get("pos") in SKILL:
                changes.append({"team": key[0], "player": key[1], "pos": r.get("pos", ""),
                                "now": "Cleared", "was": r.get("status", ""), "injury": r.get("injury", "")})
    changes.sort(key=lambda c: (c["pos"] != "QB", c["pos"] not in SKILL, STATUS_RANK.get(c["now"].lower(), 3), c["team"]))

    qb_changes = []
    lineups = sorted(glob(f"data/rotowire_lineups_week{week}_*.csv"))
    if len(lineups) >= 2:
        def qbs(rows):
            out = {}
            for r in rows:
                for side in ("away", "home"):
                    out[canonical_team(r.get(side))] = r.get(f"{side}_qb", "")
            return out
        first, last = qbs(_read_csv(lineups[0])), qbs(_read_csv(lineups[-1]))
        for team, qb in sorted(last.items()):
            was = first.get(team, "")
            if team in teams and qb and was and _last_name(qb) != _last_name(was):
                qb_changes.append({"team": team, "now": qb, "was": was})
    return qb_changes, changes, since

def build_injury_section():
    teams = {c.get("away_tla") for c in cards} | {c.get("home_tla") for c in cards}
    teams = {canonical_team(t) for t in teams if t}
    qb_changes, changes, since = injury_changes(cur_week_str, teams)
    if not qb_changes and not changes:
        return ""
    rows = [
        f"<tr><td style='padding:4px 8px 4px 0;font-weight:600;'>{q['team']} QB</td>"
        f"<td style='padding:4px 0;'><b>{q['now']}</b> starting <span style='color:#6b7280;'>(was {q['was']})</span></td></tr>"
        for q in qb_changes
    ]
    shown = changes[:12]
    for c in shown:
        color = "#b91c1c" if c["now"].lower() in ("out", "doubtful") else "#15803d" if c["now"] == "Cleared" else "#b45309"
        rows.append(
            f"<tr><td style='padding:4px 8px 4px 0;font-weight:600;white-space:nowrap;'>{c['team']} {c['pos']}</td>"
            f"<td style='padding:4px 0;'>{c['player']}: <b style='color:{color};'>{c['now']}</b>"
            f" <span style='color:#6b7280;'>(was {c['was']}{', ' + c['injury'] if c['injury'] else ''})</span></td></tr>"
        )
    more = f"<div style='font-size:12px;color:#6b7280;margin-top:6px;'>+{len(changes) - len(shown)} more on the dashboard</div>" if len(changes) > len(shown) else ""
    since_txt = f" since {since}" if since else ""
    return (
        f"<h2 style='font-size:16px;color:#111827;border-bottom:2px solid #e5e7eb;"
        f"padding-bottom:8px;margin:28px 0 8px;'>Injury &amp; lineup changes{since_txt}</h2>"
        f"<table style='width:100%;border-collapse:collapse;font-size:13px;color:#111827;'>{''.join(rows)}</table>"
        f"{more}"
        "<div style='font-size:12px;color:#6b7280;margin-top:6px;'>The line usually moves on this news before we see it; "
        "check the current number before betting.</div>"
    )

injury_section = build_injury_section()

# ── Model view (learning model, second opinion) ──────────────────────────────
def build_model_view_section():
    try:
        with open("site/src/data/modelView.json") as f:
            mv = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    if str(mv.get("week")) != cur_week_str:
        return ""
    live_teams = {c.get("away_tla") for c in cards} | {c.get("home_tla") for c in cards}
    thr = mv.get("lean_threshold", 0.53)
    leans = []
    for g in mv.get("games", []):
        if g.get("away") not in live_teams and g.get("home") not in live_teams:
            continue  # already kicked off
        for pick, conf in ((g["side_pick"], g["side_conf"]), (g["total_pick"], g["total_conf"])):
            if conf >= thr:
                leans.append((conf, pick, g["matchup"]))
    if not leans:
        return ""
    leans.sort(reverse=True)
    rows = "".join(
        f"<tr><td style='padding:4px 8px 4px 0;font-weight:600;'>{pick}</td>"
        f"<td style='padding:4px 8px;color:#6b7280;'>{matchup}</td>"
        f"<td style='padding:4px 0;text-align:right;font-weight:600;'>{round(conf * 100)}%</td></tr>"
        for conf, pick, matchup in leans[:8]
    )
    return (
        "<h2 style='font-size:16px;color:#111827;border-bottom:2px solid #e5e7eb;"
        "padding-bottom:8px;margin:28px 0 8px;'>Model view</h2>"
        f"<table style='width:100%;border-collapse:collapse;font-size:13px;color:#111827;'>{rows}</table>"
        "<div style='font-size:12px;color:#6b7280;margin-top:6px;'>Learning model leans (2015&ndash;2025 history plus "
        "2026 sharp money and line moves). A second opinion beside the engine, not a play; weak edges near 52.4% break-even.</div>"
    )

model_view_section = build_model_view_section()

flip_section = ""
if flip_alert:
    flip_section = (
        "<div style='background:#fefce8;border:1px solid #fbbf24;border-radius:6px;"
        "padding:14px 16px;margin-bottom:20px;'>"
        "<strong style='color:#92400e;'>&#x26A0;&#xFE0F; Line Movement Alert</strong>"
        f"<p style='margin:6px 0 0;font-size:14px;color:#78350f;'>{flip_alert}</p>"
        "</div>"
    )

# ── Assemble body ─────────────────────────────────────────────────────────────
body = f"""<html>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table style="width:100%;border-collapse:collapse;background:#f1f5f9;" cellpadding="0" cellspacing="0">
<tr><td style="padding:24px 16px;">
<table style="max-width:620px;margin:0 auto;border-collapse:collapse;width:100%;" cellpadding="0" cellspacing="0">
<tr>
  <td style="background:#0f1629;border-radius:10px 10px 0 0;padding:28px 32px;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#475569;margin-bottom:6px;">NFL Edge Lab</div>
    <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;line-height:1.3;">Week {week} {analysis_type}</h1>
    <div style="color:#94a3b8;font-size:13px;margin-top:6px;">{ctx_line} &nbsp;&#183;&nbsp; {timestamp}</div>
  </td>
</tr>
<tr>
  <td style="background:#ffffff;padding:28px 32px;">
    <p style="font-size:15px;color:#4b5563;margin:0 0 20px;line-height:1.6;">{intro_text}</p>
    {flip_section}
    <table style="width:100%;border-collapse:collapse;margin:0 0 20px;">
      <tr>
        <td style="background:#f8fafc;border-radius:6px;padding:12px 16px;text-align:center;width:33%;">
          <strong style="font-size:24px;color:#16a34a;">{len(plays)}</strong>
          <div style="font-size:12px;color:#6b7280;margin-top:2px;">Plays</div>
        </td>
        <td style="width:8px;"></td>
        <td style="background:#f8fafc;border-radius:6px;padding:12px 16px;text-align:center;width:33%;">
          <strong style="font-size:24px;color:#b45309;">{len(watches)}</strong>
          <div style="font-size:12px;color:#6b7280;margin-top:2px;">Watch</div>
        </td>
        <td style="width:8px;"></td>
        <td style="background:#f8fafc;border-radius:6px;padding:12px 16px;text-align:center;width:33%;">
          <strong style="font-size:24px;color:#6b7280;">{len(passes)}</strong>
          <div style="font-size:12px;color:#6b7280;margin-top:2px;">Passes</div>
        </td>
      </tr>
    </table>
    <h2 style="font-size:16px;color:#111827;border-bottom:2px solid #e5e7eb;padding-bottom:8px;margin:0 0 4px;">
      Plays &nbsp;<span style="color:#16a34a;font-weight:400;">{len(plays)}</span>
    </h2>
    {started_note}
    {plays_html}
    {watch_section}
    {model_view_section}
    {injury_section}
    {pass_section}
    {pickem_section}
    <table style="width:100%;border-collapse:collapse;margin-top:28px;">
      <tr>
        <td style="background:#eff6ff;border-radius:8px;padding:20px 24px;text-align:center;">
          <p style="margin:0 0 12px;font-size:14px;color:#475569;">Full edge board, WARPS scores, and scout alerts on the dashboard:</p>
          <a href="{SITE_URL}" style="display:inline-block;background:#0056b3;color:#ffffff;text-decoration:none;padding:10px 28px;border-radius:6px;font-weight:600;font-size:14px;">View Dashboard</a>
        </td>
      </tr>
    </table>
  </td>
</tr>
<tr>
  <td style="background:#f8fafc;border-radius:0 0 10px 10px;padding:14px 32px;text-align:center;border-top:1px solid #e5e7eb;">
    <p style="margin:0;font-size:12px;color:#94a3b8;">NFL Edge Lab - Week {week} {analysis_type} - {timestamp}</p>
    <p style="margin:4px 0 0;font-size:12px;color:#cbd5e1;">Model output only - not financial advice</p>
  </td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""

# ── Send ──────────────────────────────────────────────────────────────────────
play_count = len(plays)
pass_count = len(passes)
top = plays[0].get("pick_label") or f"{plays[0].get('away_tla','?')}@{plays[0].get('home_tla','?')}" if plays else None
if top:
    subject_detail = f"{top} + {play_count} play{'s' if play_count != 1 else ''}, {pass_count} pass{'es' if pass_count != 1 else ''}"
else:
    subject_detail = f"No plays - {pass_count} pass{'es' if pass_count != 1 else ''}"

msg = MIMEMultipart()
week_display = ctx_week_label if ctx_week_label and ctx_week_label != f"Week {week}" else f"Wk {week}"
msg["Subject"] = f"NFL {week_display} {subject_prefix}: {subject_detail}"
msg["From"] = gmail_user
msg["To"] = RECIPIENT
msg.attach(MIMEText(body, "html", "utf-8"))

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(gmail_user, gmail_pass)
server.send_message(msg)
server.quit()

print(f"Email sent: Week {week} -- {play_count} plays, {len(watches)} watch, {pass_count} passes")
