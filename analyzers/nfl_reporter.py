import smtplib, os, re, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def generate_report():
    # Get variables from GitHub Environment
    week = os.getenv('WEEK')
    timestamp = os.getenv('TIMESTAMP')
    analysis_type = os.getenv('ANALYSIS_TYPE')
    subject_prefix = os.getenv('SUBJECT_PREFIX')
    flip_alert = os.getenv('FLIP_ALERT')

    # 1. Load the Analysis Text
    try:
        with open(f"data/week{week}/week{week}_pro_analysis.txt", "r") as f:
            content = f.read()
    except:
        content = "Pro analysis file not found"

    # 2. Parse Game Sections (Your original logic restored)
    games = []
    sections = content.split("======================================================================")
    for section in sections:
        if "===" in section and "Classification:" in section:
            game = {'sharp_stories': [], 'referee_context': [], 'situational': [], 'statistical': [], 'market': []}
            lines = section.strip().split('\n')
            current_section = None
            for line in lines:
                line = line.strip()
                if line.startswith("=== ") and " ===" in line:
                    game['matchup'] = line.replace("===", "").strip()
                elif line.startswith("Classification:"):
                    game['classification'] = line.replace("Classification:", "").strip()
                elif line.startswith("Total Score:"):
                    game['total_score'] = line.replace("Total Score:", "").strip()
                elif line.startswith("Confidence:"):
                    game['confidence'] = line.replace("Confidence:", "").strip().split('/')[0]
                elif line.startswith("Recommendation:"):
                    game['recommendation'] = line.replace("Recommendation:", "").strip()
                
                # Section detection
                if "SHARP MONEY STORY:" in line: current_section = "sharp"
                elif "REFEREE CONTEXT:" in line: current_section = "referee"
                elif "WEATHER IMPACT:" in line: current_section = "weather"
                elif "INJURY ANALYSIS:" in line: current_section = "injury"
                elif "SITUATIONAL FACTORS:" in line: current_section = "situational"
                elif "STATISTICAL EDGE:" in line: current_section = "statistical"
                elif "MARKET DYNAMICS:" in line: current_section = "market"
                
                elif (line.startswith("•") or line.startswith("→") or line.startswith("-")) and current_section:
                    content_line = line[1:].strip()
                    if current_section == "sharp": game['sharp_stories'].append(content_line)
                    elif current_section == "referee": game['referee_context'].append(content_line)
                    elif current_section == "situational": game['situational'].append(content_line)
                    elif current_section == "statistical": game['statistical'].append(content_line)
                    elif current_section == "market": game['market'].append(content_line)
                    elif current_section == "weather": game['weather'] = content_line
            if game.get('matchup'): games.append(game)

    # 3. Build the HTML (Your specific styling restored)
    game_cards_html = ""
    for game in games:
        classification = game.get('classification', '')
        # Determine Color/Emoji
        if "BLUE CHIP" in classification: color, bg, emoji = "#2196F3", "#e3f2fd", "🔵"
        elif "TARGETED" in classification: color, bg, emoji = "#ff9800", "#fff3e0", "🎯"
        elif "❌ FADE" in classification or "LANDMINE" in classification: color, bg, emoji = "#f44336", "#ffebee", "❌"
        else: color, bg, emoji = "#666", "#f5f5f5", "📈"

        # Content blocks
        sharp_html = "".join([f"<p style='margin:3px 0; font-size:13px;'>• {s}</p>" for s in game['sharp_stories'][:3]])
        ref_html = "".join([f"<p style='margin:3px 0; font-size:13px;'>• {r}</p>" for r in game['referee_context'][:2]])

        game_cards_html += f"""
        <div style="margin:20px 0; padding:20px; border:1px solid #ddd; border-radius:8px; border-left:5px solid {color}; background:{bg};">
            <h3 style="margin:0; color:#2c3e50;">{emoji} {game.get('matchup')}</h3>
            <p><strong>{classification}</strong> | Confidence: {game.get('confidence')}/20</p>
            <div style="background:white; padding:10px; border-radius:5px;">
                <h4 style="margin:0; color:#e65100;">💰 Sharp Story</h4>{sharp_html}
                <h4 style="margin:10px 0 0 0; color:#5d4e75;">⚖️ Ref Context</h4>{ref_html}
            </div>
        </div>"""

    # Final Email Assembly
    msg = MIMEMultipart()
    msg['Subject'] = f"{subject_prefix} Week {week} NFL Pro Analysis & Data Package"
    msg['From'] = os.getenv('GMAIL_USER')
    msg['To'] = "lvarughese@gmail.com"
    
    full_html = f"<html><body style='font-family:Arial;'><h1>Week {week} - {analysis_type}</h1>{game_cards_html}</body></html>"
    msg.attach(MIMEText(full_html, 'html'))

    # Attach all 4 files
    for suffix in ["executive_summary.txt", "pro_analysis.txt", "analytics.csv", "analytics.json"]:
        file_path = f"data/week{week}/week{week}_{suffix}"
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                msg.attach(part)

    # Send
    s = smtplib.SMTP('smtp.gmail.com', 587); s.starttls()
    s.login(os.getenv('GMAIL_USER'), os.getenv('GMAIL_APP_PASSWORD'))
    s.send_message(msg); s.quit()

if __name__ == "__main__":
    generate_report()
