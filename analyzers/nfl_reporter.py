import smtplib, os, json, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def validate_total_line(total_line_str):
    """Return (display_str, warning) for a total line.

    Checks that over and under numbers are within 1.0 of each other.
    A gap larger than that indicates a parsing error (e.g. 'o44.5 / u54.5').
    """
    if not total_line_str or total_line_str == 'N/A':
        return total_line_str, None
    nums = re.findall(r'[ou](\d+(?:\.\d+)?)', str(total_line_str), re.IGNORECASE)
    if len(nums) == 2:
        try:
            gap = abs(float(nums[0]) - float(nums[1]))
            if gap > 1.0:
                return (
                    f"⚠️ DATA ERROR ({total_line_str})",
                    f"Over/under gap {gap:.1f}pts — parsing mismatch, verify raw odds"
                )
        except ValueError:
            pass
    return total_line_str, None


def _load_card_lookup(week):
    """Load weekly_betting_card.json and return dict keyed by matchup_key."""
    try:
        with open("data/historical/weekly_betting_card.json") as f:
            card_data = json.load(f)
        return {c.get('matchup_key', ''): c for c in card_data.get('cards', []) if c.get('matchup_key')}
    except Exception:
        return {}


def _risk_chips_html(risk_flags):
    if not risk_flags:
        return ""
    chips = "".join(
        f'<span style="display:inline-block; margin:2px 3px 0 0; padding:2px 6px; '
        f'background:#fff3e0; border:1px solid #ffcc80; border-radius:10px; '
        f'font-size:10px; color:#e65100;">⚠ {f}</span>'
        for f in risk_flags
    )
    return f'<div style="margin-top:5px;">{chips}</div>'


def _play_card(game, card_lookup, color, bg, emoji):
    """Full card for LEAN / TARGETED / BLUE CHIP games."""
    matchup_key = game.get('matchup_key', '')
    card = card_lookup.get(matchup_key, {})

    class_text = game.get('classification', '').upper()
    confidence = game.get('confidence', 0)
    recommendation = game.get('recommendation', '')
    game_time = game.get('game_time', '') or 'TBD'

    spread_line = game.get('sharp_analysis', {}).get('spread', {}).get('line', 'N/A')
    raw_total_line = game.get('sharp_analysis', {}).get('total', {}).get('line', 'N/A')
    total_line, total_warning = validate_total_line(raw_total_line)

    sharp_spread = game.get('sharp_analysis', {}).get('spread', {}).get('differential', 0)
    sharp_total = game.get('sharp_analysis', {}).get('total', {}).get('differential', 0)
    sharp_list = game.get('sharp_stories', [])
    sharp_pct_parts = []
    if abs(sharp_spread) >= 5:
        sharp_pct_parts.append(f"{'+'if sharp_spread>0 else ''}{sharp_spread:.0f}% spread")
    if abs(sharp_total) >= 5:
        sharp_pct_parts.append(f"{'+'if sharp_total>0 else ''}{sharp_total:.0f}% total")
    sharp_summary = (", ".join(sharp_pct_parts) + " — " if sharp_pct_parts else "") + (sharp_list[0] if sharp_list else "Balanced action")

    # Referee
    ref = game.get('referee_analysis', {})
    ref_name = ref.get('referee', 'Unknown')
    ref_tendency = ref.get('ats_tendency', 'NEUTRAL')
    ats_pct = ref.get('ats_pct', 0)
    ou_pct = ref.get('ou_pct', 0)
    ref_line = f"{ref_name} · ATS {ats_pct:.0f}% ({ref_tendency}) · OU {ou_pct:.0f}%"

    # WARPS from betting card
    warps_alignment = card.get('warps_alignment', '')
    required_line = card.get('required_line', '')
    fair_match = re.search(r'fair\s+([-+]?\d+(?:\.\d+)?)', required_line or '', re.IGNORECASE)
    fair_str = f"fair {fair_match.group(1)}" if fair_match else ""
    warps_side = card.get('warps_side', '')
    if warps_alignment and fair_str:
        warps_line = f"WARPS: {warps_alignment} · {fair_str}" + (f" ({warps_side})" if warps_side else "")
    elif warps_alignment:
        warps_line = f"WARPS: {warps_alignment}"
    else:
        warps_line = ""

    # Context extras
    weather_text = game.get('weather_analysis', {}).get('description', '')
    injury_analysis = game.get('injury_analysis', {})
    total_injuries = len(injury_analysis.get('away_injuries', [])) + len(injury_analysis.get('home_injuries', []))
    injuries_text = injury_analysis.get('description', '') if total_injuries > 0 else ''
    stat_edge = next((f for f in game.get('statistical_analysis', {}).get('factors', [])), '')

    context_extras = []
    if weather_text and 'indoor' not in weather_text.lower() and 'no weather' not in weather_text.lower():
        context_extras.append(weather_text)
    if injuries_text and 'no significant' not in injuries_text.lower():
        context_extras.append(injuries_text)

    risk_flags = card.get('risk_flags', [])
    warning_html = ""
    if total_warning:
        warning_html = f'<p style="margin:5px 0 0 0; font-size:11px; color:#c62828; background:#ffebee; padding:3px 8px; border-radius:3px;">⚠️ {total_warning}</p>'

    intel_rows = [
        f'<span style="color:#e65100; font-weight:bold;">Sharp:</span> {sharp_summary}',
        f'<span style="color:#1565c0; font-weight:bold;">Ref:</span> {ref_line}',
    ]
    if warps_line:
        intel_rows.append(f'<span style="color:#6a1b9a; font-weight:bold;">WARPS:</span> {warps_line}')
    if context_extras:
        intel_rows.append(f'<span style="color:#2e7d32; font-weight:bold;">Context:</span> {" · ".join(context_extras)}')
    if stat_edge:
        intel_rows.append(f'<span style="color:#2e7d32; font-weight:bold;">Edge:</span> {stat_edge}')

    intel_html = "<br>".join(intel_rows)

    return f"""
    <div style="margin:14px 0; padding:14px 16px; border-left:5px solid {color}; background-color:{bg}; border-radius:3px; font-family:sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px;">
            <span style="font-size:16px; font-weight:bold; color:#222;">{emoji} {game['matchup']}</span>
            <span style="font-size:12px; color:#666;">{game_time}</span>
        </div>
        <p style="margin:6px 0 2px 0; font-weight:bold; color:{color}; font-size:13px;">{class_text} · {confidence:.1f}/20 · {recommendation}</p>
        <p style="margin:4px 0; font-size:12px; color:#555; font-family:monospace;">Spread: {spread_line} &nbsp;|&nbsp; Total: {total_line}</p>
        {warning_html}
        <div style="margin-top:8px; padding:8px 10px; background:rgba(255,255,255,0.7); border-radius:3px; font-size:12px; color:#444; line-height:1.7;">
            {intel_html}
        </div>
        {_risk_chips_html(risk_flags)}
    </div>"""


def _fade_card(game):
    """Compact warning card for FADE / LANDMINE games."""
    class_text = game.get('classification', '').upper()
    confidence = game.get('confidence', 0)
    recommendation = game.get('recommendation', '')
    game_time = game.get('game_time', '') or 'TBD'
    spread_line = game.get('sharp_analysis', {}).get('spread', {}).get('line', 'N/A')
    raw_total_line = game.get('sharp_analysis', {}).get('total', {}).get('line', 'N/A')
    total_line, total_warning = validate_total_line(raw_total_line)
    sharp_list = game.get('sharp_stories', [])
    sharp_summary = sharp_list[0] if sharp_list else "Multiple negative factors"
    ref_name = game.get('referee_analysis', {}).get('referee', 'Unknown')
    ref_tendency = game.get('referee_analysis', {}).get('ats_tendency', 'NEUTRAL')
    warning_html = ""
    if total_warning:
        warning_html = f'<span style="color:#c62828;"> ⚠️ {total_warning}</span>'

    return f"""
    <div style="margin:10px 0; padding:10px 14px; border-left:4px solid #f44336; background:#ffebee; border-radius:3px; font-family:sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px;">
            <span style="font-size:14px; font-weight:bold; color:#b71c1c;">❌ {game['matchup']}</span>
            <span style="font-size:11px; color:#888;">{game_time}</span>
        </div>
        <p style="margin:4px 0 2px 0; font-size:12px; color:#c62828; font-weight:bold;">{class_text} · {confidence:.1f}/20 · {recommendation}</p>
        <p style="margin:3px 0; font-size:11px; color:#555; font-family:monospace;">Spread: {spread_line} | Total: {total_line}{warning_html}</p>
        <p style="margin:3px 0; font-size:11px; color:#666;">{ref_name} ({ref_tendency}) · {sharp_summary}</p>
    </div>"""


def generate_report():
    week = os.getenv('WEEK')
    timestamp = os.getenv('TIMESTAMP')
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')
    season_type = os.getenv('NFL_SEASON_TYPE', 'REG').strip().upper()

    stage = os.getenv('ANALYSIS_TYPE', 'final')

    if season_type == 'PRE' and stage in ('update', 'lock'):
        print(f"SKIP: Preseason {stage} email suppressed")
        return

    json_path = f"data/week{week}/{stage}.json"
    try:
        with open(json_path, "r") as f:
            games_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load JSON: {e}")
        return

    card_lookup = _load_card_lookup(week)

    # Partition games into sections
    plays, fades, passes = [], [], []
    for g in games_data:
        ct = g.get('classification', '').upper()
        if any(x in ct for x in ('BLUE CHIP', 'TARGETED', 'LEAN')):
            plays.append(g)
        elif any(x in ct for x in ('FADE', 'LANDMINE')):
            fades.append(g)
        else:
            passes.append(g)

    # Sort plays by confidence descending
    plays.sort(key=lambda x: x.get('confidence', 0), reverse=True)

    # Build plays section
    plays_html = ""
    for game in plays:
        ct = game.get('classification', '').upper()
        if 'BLUE CHIP' in ct:
            color, bg, emoji = "#2196F3", "#e3f2fd", "🔵"
        elif 'TARGETED' in ct:
            color, bg, emoji = "#ff9800", "#fff3e0", "🎯"
        else:
            color, bg, emoji = "#4CAF50", "#f1f8e9", "📈"
        plays_html += _play_card(game, card_lookup, color, bg, emoji)

    # Build fades section
    fades_html = "".join(_fade_card(g) for g in fades)

    # Build passes compact list
    passes_html = ""
    if passes:
        pass_labels = []
        for g in passes:
            mk = g.get('matchup_key') or g.get('matchup', '').replace(' @ ', '@')
            pass_labels.append(mk)
        passes_html = f"""
    <div style="margin:20px 0 8px 0; padding:12px 14px; background:#f8f9fa; border-radius:4px; font-family:sans-serif;">
        <p style="margin:0 0 6px 0; font-size:12px; font-weight:bold; color:#777; text-transform:uppercase; letter-spacing:0.5px;">Passes ({len(passes)})</p>
        <p style="margin:0; font-size:12px; color:#999; font-family:monospace; line-height:1.8;">{' &nbsp;·&nbsp; '.join(pass_labels)}</p>
    </div>"""

    # Section headers
    def section_header(title, count, color):
        return f'<p style="margin:20px 0 4px 0; font-size:11px; font-weight:bold; color:{color}; text-transform:uppercase; letter-spacing:1px; font-family:sans-serif;">{title} ({count})</p>'

    game_cards_html = ""
    if plays:
        game_cards_html += section_header("Plays", len(plays), "#2e7d32")
        game_cards_html += plays_html
    if fades:
        game_cards_html += section_header("Fades — Avoid", len(fades), "#b71c1c")
        game_cards_html += fades_html
    game_cards_html += passes_html

    # Summary stats
    blue_chips = [g for g in plays if 'BLUE CHIP' in g.get('classification', '').upper()]
    targeted = [g for g in plays if 'TARGETED' in g.get('classification', '').upper()]
    leans = [g for g in plays if 'LEAN' in g.get('classification', '').upper()]

    best_edge_game = max(games_data, key=lambda x: x.get('total_score', -999)) if games_data else {}
    top_matchup = best_edge_game.get('matchup', 'N/A')
    top_score = best_edge_game.get('confidence', 0)

    preseason_banner = ""
    if season_type == 'PRE':
        preseason_banner = """
    <div style="background:#fff3cd; padding:12px 15px; border-left:4px solid #ffc107; border-radius:4px; margin:15px 0;">
        <strong>⚠️ PRESEASON DRY RUN</strong> — Referee history is regular-season data only and not applicable to preseason games.
        RotoWire lineups unavailable. Markets are thin. <strong>No bets recommended until regular season.</strong>
    </div>"""

    summary_html = f"""
    <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin:20px 0; border-left:4px solid #007bff;">
        <h3 style="margin:0 0 10px 0; color:#007bff;">📊 Week {week} Summary</h3>
        {preseason_banner}
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
            <div>
                <p style="margin:5px 0;"><strong>🔵 Blue Chips:</strong> {len(blue_chips)} plays{f" (avg {sum(g.get('confidence',0) for g in blue_chips)/len(blue_chips):.1f}/20)" if blue_chips else ""}</p>
                <p style="margin:5px 0;"><strong>🎯 Targeted:</strong> {len(targeted)} plays{f" (avg {sum(g.get('confidence',0) for g in targeted)/len(targeted):.1f}/20)" if targeted else ""}</p>
                <p style="margin:5px 0;"><strong>📈 Lean:</strong> {len(leans)} plays</p>
            </div>
            <div>
                <p style="margin:5px 0;"><strong>❌ Fades:</strong> {len(fades)}</p>
                <p style="margin:5px 0;"><strong>⏭ Passes:</strong> {len(passes)}</p>
                <p style="margin:5px 0;"><strong>🏆 Top Play:</strong> {top_matchup} ({top_score:.1f}/20)</p>
            </div>
        </div>
    </div>
    """

    # Line move alert
    line_moves_total = int(os.getenv('LINE_MOVES_TOTAL', '0') or 0)
    line_moves_pick_affected = int(os.getenv('LINE_MOVES_PICK_AFFECTED', '0') or 0)
    line_moves_summary_str = os.getenv('LINE_MOVES_SUMMARY', '').strip()
    line_move_banner = ""
    if line_moves_total > 0:
        pick_note = f" &mdash; <strong>{line_moves_pick_affected} affect model pick(s)</strong>" if line_moves_pick_affected else ""
        move_detail = f"<br><small style='color:#555;'>{line_moves_summary_str}</small>" if line_moves_summary_str else ""
        line_move_banner = (
            f"<div style='background:#fde8e8; padding:12px 15px; border-left:4px solid #e53e3e;"
            f" border-radius:4px; margin:15px 0;'>"
            f"<strong>📉 LINE ALERT: {line_moves_total} significant move(s) since last analysis{pick_note}</strong>"
            f"{move_detail}"
            f"<br><small>Re-analysis ran automatically with updated lines.</small></div>"
        )

    # Subject line
    subject_prefix = os.getenv('SUBJECT_PREFIX', '🏈')
    if plays:
        top_action = plays[0]
        subject_detail = f"{top_action.get('matchup','?')} | {len(plays)} play{'s' if len(plays)!=1 else ''}, {len(fades)} fade{'s' if len(fades)!=1 else ''}"
    else:
        subject_detail = f"No plays | {len(fades)} fade{'s' if len(fades)!=1 else ''}"

    msg = MIMEMultipart()
    msg['Subject'] = f"{subject_prefix} Wk {week}: {subject_detail}"
    msg['From'] = gmail_user
    msg['To'] = "lvarughese@gmail.com"

    stage_label = {'initial': 'Initial Look', 'update': 'Midweek Update', 'lock': 'Lines Locked', 'final': ''}.get(stage, stage.title())
    stage_context = f"<p style='text-align:center; color:#e67e22; font-weight:bold; font-size:13px;'>{stage_label}</p>" if stage_label else ""

    full_html = f"""
    <html>
        <body style="background-color:#f4f4f4; padding:20px;">
            <div style="max-width:800px; margin:auto; background:white; padding:20px; border-radius:8px;">
                <h1 style="text-align:center; color:#2c3e50;">NFL Week {week} Report</h1>
                {stage_context}
                <p style="text-align:center; color:#7f8c8d; font-size:12px;">Generated: {timestamp}</p>
                {summary_html}
                {line_move_banner}
                {game_cards_html}
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(full_html, 'html'))

    # Attachments
    def _attach(filepath, filename):
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={filename}')
            msg.attach(part)
            return True
        return False

    attached = []
    for ext, label in [('.json', 'JSON'), ('.csv', 'CSV'), ('_pro_analysis.txt', 'TXT'),
                       ('_selector_audit.csv', 'Selector Audit'), ('_run_manifest.json', 'Run Manifest'),
                       ('_source_health.json', 'Source Health JSON'), ('_source_health.txt', 'Source Health TXT')]:
        src = f"data/week{week}/{stage}{ext}"
        fname = f"week{week}_{stage}{ext}"
        if _attach(src, fname):
            attached.append(label)
    if attached:
        print(f"Attached: {', '.join(attached)}")

    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(gmail_user, gmail_password)
        s.send_message(msg)
        s.quit()
        print("SUCCESS: Email sent with attachments!")
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    generate_report()
