"""Send the weekly betting card email from matrix_engine_feed.json."""
import json
import os
import re
import smtplib
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

plays   = [c for c in cards if c.get("action") == "play"]
watches = [c for c in cards if c.get("action") in ("watch", "lean")]
passes  = [c for c in cards if c.get("action") == "pass"]

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

# ── Build sections ────────────────────────────────────────────────────────────
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
    {plays_html}
    {watch_section}
    {pass_section}
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
msg["Subject"] = f"NFL Wk {week} {subject_prefix}: {subject_detail}"
msg["From"] = gmail_user
msg["To"] = RECIPIENT
msg.attach(MIMEText(body, "html", "utf-8"))

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(gmail_user, gmail_pass)
server.send_message(msg)
server.quit()

print(f"Email sent: Week {week} -- {play_count} plays, {len(watches)} watch, {pass_count} passes")
