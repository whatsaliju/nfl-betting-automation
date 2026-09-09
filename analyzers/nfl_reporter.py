import smtplib, os, json, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def validate_total_line(total_line_str):
    """Return (display_str, warning) for a total line.

    Checks that over and under numbers are within 1.0 of each other.
    A gap larger than that indicates a parsing error (e.g. 'o44.5 / u54.5').
    Returns the original string if valid, or a ⚠️-flagged version if not.
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

def generate_report():
    week = os.getenv('WEEK')
    timestamp = os.getenv('TIMESTAMP')
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')
    season_type = os.getenv('NFL_SEASON_TYPE', 'REG').strip().upper()


    
    # 1. Load the JSON Data (The reliable source)
    stage = os.getenv('ANALYSIS_TYPE', 'final')  # Gets 'initial', 'update', or 'final'

    # Skip update/lock emails for preseason — markets too thin to warrant mid-week updates
    if season_type == 'PRE' and stage in ('update', 'lock'):
        print(f"SKIP: Preseason {stage} email suppressed (only initial/final sent for PRE weeks)")
        return

    json_path = f"data/week{week}/{stage}.json"
    try:
        with open(json_path, "r") as f:
            games_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load JSON: {e}")
        return
    
  
    game_cards_html = ""

    # 2. Map JSON keys to the Email Template
    for game in games_data:
        # Determine Color Coding
        class_text = game.get('classification', 'STANDARD').upper()
        if "BLUE CHIP" in class_text: color, bg, emoji = "#2196F3", "#e3f2fd", "🔵"
        elif "TARGETED" in class_text: color, bg, emoji = "#ff9800", "#fff3e0", "🎯"
        elif "LANDMINE" in class_text: color, bg, emoji = "#f44336", "#ffebee", "❌"
        else: color, bg, emoji = "#4CAF50", "#f1f8e9", "📈"

         # Extract richer data
                
        # Fix these field mappings:

        # Sharp money details (FIXED)
        sharp_spread = game.get('sharp_analysis', {}).get('spread', {}).get('differential', 0)
        sharp_total = game.get('sharp_analysis', {}).get('total', {}).get('differential', 0)
        
        # Market data
        spread_line = game.get('sharp_analysis', {}).get('spread', {}).get('line', 'N/A')
        raw_total_line = game.get('sharp_analysis', {}).get('total', {}).get('line', 'N/A')
        total_line, total_warning = validate_total_line(raw_total_line)

        # Injury analysis
        injury_analysis = game.get('injury_analysis', {})
        total_injuries = len(injury_analysis.get('away_injuries', [])) + len(injury_analysis.get('home_injuries', []))
        injuries_text = injury_analysis.get('description', 'No injuries') if total_injuries > 0 else 'No significant injuries'

        # Weather
        weather_data = game.get('weather_analysis', {})
        weather_text = weather_data.get('description', 'Indoor/No weather concerns')

        # Score
        total_score = game.get('total_score', 0)
        recommendation = game.get('recommendation', 'No specific recommendation')

        # Sharp — build one summary sentence
        sharp_list = game.get('sharp_stories', [])
        sharp_pct_parts = []
        if abs(sharp_spread) >= 5:
            sharp_pct_parts.append(f"{'+'if sharp_spread>0 else ''}{sharp_spread:.0f}% spread")
        if abs(sharp_total) >= 5:
            sharp_pct_parts.append(f"{'+'if sharp_total>0 else ''}{sharp_total:.0f}% total")
        sharp_summary = (", ".join(sharp_pct_parts) + " — " if sharp_pct_parts else "") + (sharp_list[0] if sharp_list else "Balanced action")

        # Context
        ref_name = game.get('referee_analysis', {}).get('referee', 'Unknown')
        ref_tendency = game.get('referee_analysis', {}).get('ats_tendency', 'NEUTRAL')
        stat_edge = next((f for f in game.get('statistical_analysis', {}).get('factors', [])), '')
        context_parts = [f"{ref_name} ({ref_tendency})"]
        if weather_text and 'indoor' not in weather_text.lower() and 'no weather' not in weather_text.lower():
            context_parts.append(weather_text)
        if injuries_text and 'no significant' not in injuries_text.lower():
            context_parts.append(injuries_text)
        context_line = ' · '.join(context_parts)

        # Data warning banner
        warning_html = ""
        if total_warning:
            warning_html = f'<p style="margin:6px 0 0 0; font-size:11px; color:#c62828; background:#ffebee; padding:4px 8px; border-radius:3px;">⚠️ {total_warning}</p>'

        # Compact card
        game_cards_html += f"""
        <div style="margin:16px 0; padding:14px 16px; border-left:5px solid {color}; background-color:{bg}; border-radius:3px; font-family:sans-serif;">
            <div style="display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px;">
                <span style="font-size:16px; font-weight:bold; color:#222;">{emoji} {game['matchup']}</span>
                <span style="font-size:12px; color:#666;">{game.get('game_time', '') or 'TBD'}</span>
            </div>
            <p style="margin:6px 0 2px 0; font-weight:bold; color:{color}; font-size:13px;">{class_text} · {game.get('confidence', 0):.1f}/20 · {recommendation}</p>
            <p style="margin:4px 0; font-size:12px; color:#555; font-family:monospace;">Spread: {spread_line} &nbsp;|&nbsp; Total: {total_line}</p>
            {warning_html}
            <div style="margin-top:8px; padding:8px 10px; background:rgba(255,255,255,0.7); border-radius:3px; font-size:12px; color:#444; line-height:1.6;">
                <span style="color:#e65100; font-weight:bold;">Sharp:</span> {sharp_summary}<br>
                <span style="color:#5d4e75; font-weight:bold;">Context:</span> {context_line}<br>
                {f'<span style="color:#2e7d32; font-weight:bold;">Edge:</span> {stat_edge}' if stat_edge else ''}
            </div>
        </div>"""

    # Add summary statistics at the top
    blue_chips = [g for g in games_data if 'BLUE CHIP' in g.get('classification', '').upper()]
    targeted = [g for g in games_data if 'TARGETED' in g.get('classification', '').upper()]
    landmines = [g for g in games_data if 'LANDMINE' in g.get('classification', '').upper()]
    leans = [g for g in games_data if 'LEAN' in g.get('classification', '').upper()]
    actionable = blue_chips + targeted + leans

    # Find top play by score
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
                <p style="margin:5px 0;"><strong>🔵 Blue Chips:</strong> {len(blue_chips)} plays{f" (avg: {sum(g.get('confidence',0) for g in blue_chips)/len(blue_chips):.1f}/20)" if blue_chips else ""}</p>
                <p style="margin:5px 0;"><strong>🎯 Targeted:</strong> {len(targeted)} plays{f" (avg: {sum(g.get('confidence',0) for g in targeted)/len(targeted):.1f}/20)" if targeted else ""}</p>
                <p style="margin:5px 0;"><strong>📊 Lean:</strong> {len(leans)} plays</p>
            </div>
            <div>
                <p style="margin:5px 0;"><strong>❌ Avoid:</strong> {len(landmines)} landmines</p>
                <p style="margin:5px 0;"><strong>🏆 Top Play:</strong> {top_matchup} ({top_score:.1f}/20)</p>
            </div>
        </div>
    </div>
    """

    # Line move alert banner (injected after summary_html is built)
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

    # Build subject line with top play info
    subject_prefix = os.getenv('SUBJECT_PREFIX', '🏈')
    if actionable:
        top_action = actionable[0]
        subject_detail = f"{top_action.get('matchup','?')} | {len(actionable)} play{'s' if len(actionable)!=1 else ''}, {len(landmines)} fade{'s' if len(landmines)!=1 else ''}"
    else:
        subject_detail = f"No plays | {len(landmines)} fade{'s' if len(landmines)!=1 else ''}"

    msg = MIMEMultipart()
    msg['Subject'] = f"{subject_prefix} Wk {week}: {subject_detail}"
    msg['From'] = gmail_user
    msg['To'] = "lvarughese@gmail.com"

    stage_context = f"<p style='text-align:center; color:#e67e22; font-weight:bold;'>{stage.title()} Analysis</p>" if stage != 'final' else ""
    
    full_html = f"""
    <html>
        <body style="background-color:#f4f4f4; padding:20px;">
            <div style="max-width:800px; margin:auto; background:white; padding:20px; border-radius:8px;">
                <h1 style="text-align:center; color:#2c3e50;">NFL Week {week} Report</h1>
                {stage_context}
                <p style="text-align:center; color:#7f8c8d;">Generated: {timestamp}</p>
                {summary_html}
                {line_move_banner}
                {game_cards_html}
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(full_html, 'html'))

    # Attach analysis files to the same email (no separate attachment email needed)
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
        src = f"data/week{week}/{stage}{ext}" if not ext.startswith('_') else f"data/week{week}/{stage}{ext}"
        fname = f"week{week}_{stage}{ext}"
        if _attach(src, fname):
            attached.append(label)
    if attached:
        print(f"Attached: {', '.join(attached)}")

    # Send
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
