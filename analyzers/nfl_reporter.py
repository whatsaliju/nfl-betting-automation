import smtplib, os, re, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def generate_report():
    # 1. Get variables from GitHub Environment
    week = os.getenv('WEEK')
    timestamp = os.getenv('TIMESTAMP')
    analysis_type = os.getenv('ANALYSIS_TYPE', 'NFL Analysis')
    subject_prefix = os.getenv('SUBJECT_PREFIX', '📊')
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')

    # Debug logs for GitHub Action Console
    print(f"DEBUG: Starting report generation for Week: {week}")
    print(f"DEBUG: Using Analysis Type: {analysis_type}")

    if not week:
        print("ERROR: WEEK environment variable is missing!")
        return

    # 2. Load the Analysis Text
    content = ""
    analysis_path = f"data/week{week}/week{week}_pro_analysis.txt"
    
    try:
        if os.path.exists(analysis_path):
            with open(analysis_path, "r") as f:
                content = f.read()
            print(f"SUCCESS: Loaded analysis file from {analysis_path}")
        else:
            print(f"ERROR: File not found at {analysis_path}")
            content = "Pro analysis data currently unavailable."
    except Exception as e:
        print(f"ERROR: Failed to read file: {str(e)}")
        content = "Error reading analysis file."

    # 3. Parse Game Sections
    games = []
    sections = content.split("======================================================================")
    
    for section in sections:
        if "Classification:" in section:
            # 1. Reset the dictionary for a fresh game
            game = {
                'matchup': "Unknown Matchup",
                'classification': "STANDARD",
                'confidence': "0",
                'sharp_stories': [], 
                'referee_context': [], 
                'weather': 'No significant impact'
            }
            
            lines = section.strip().split('\n')
            current_section = None  # <--- CRITICAL: Reset context for every game
            
            for line in lines:
                line = line.strip()
                if not line: continue

                # Detect Matchup, Class, Confidence
                if line.startswith("=== ") and " ===" in line:
                    game['matchup'] = line.replace("===", "").strip()
                elif line.startswith("Classification:"):
                    game['classification'] = line.replace("Classification:", "").strip()
                elif line.startswith("Confidence:"):
                    game['confidence'] = line.replace("Confidence:", "").strip().split('/')[0]
                
                # Detect Section Headers - These act as "Switches"
                if "SHARP MONEY STORY:" in line: 
                    current_section = "sharp"
                elif "REFEREE CONTEXT:" in line: 
                    current_section = "referee"
                elif "WEATHER IMPACT:" in line: 
                    current_section = "weather"
                
                # Logic: If we are 'inside' a section and see a bullet, add it
                elif (line.startswith("•") or line.startswith("→") or line.startswith("-")):
                    clean_line = line[1:].strip()
                    if current_section == "sharp":
                        game['sharp_stories'].append(clean_line)
                    elif current_section == "referee":
                        game['referee_context'].append(clean_line)
                    elif current_section == "weather":
                        game['weather'] = clean_line
                
                # If we hit a line that ISN'T a bullet and ISN'T a header, 
                # we've probably left the specific section.
                else:
                    current_section = None 

            if game.get('matchup'):
                games.append(game)

    # 4. Build the HTML
    game_cards_html = ""
    for game in games:
        classification = game.get('classification', 'STANDARD')
        if "BLUE CHIP" in classification: color, bg, emoji = "#2196F3", "#e3f2fd", "🔵"
        elif "TARGETED" in classification: color, bg, emoji = "#ff9800", "#fff3e0", "🎯"
        elif "❌" in classification or "LANDMINE" in classification: color, bg, emoji = "#f44336", "#ffebee", "❌"
        else: color, bg, emoji = "#4CAF50", "#f1f8e9", "📈"

        sharp_html = "".join([f"<li style='margin-bottom:5px;'>{s}</li>" for s in game['sharp_stories'][:3]])
        ref_html = "".join([f"<li style='margin-bottom:5px;'>{r}</li>" for r in game['referee_context'][:2]])

        game_cards_html += f"""
        <div style="margin:20px 0; padding:15px; border-left:6px solid {color}; background-color:{bg}; border-radius:4px;">
            <h2 style="margin:0; color:#333;">{emoji} {game['matchup']}</h2>
            <p style="font-weight:bold; color:{color};">{classification} | Confidence: {game.get('confidence', '?')}/20</p>
            <div style="background:white; padding:12px; border-radius:4px; border:1px solid #ddd;">
                <h4 style="margin:0 0 8px 0; color:#e65100; border-bottom:1px solid #eee;">💰 Sharp Activity</h4>
                <ul style="margin:0; padding-left:20px; font-size:13px;">{sharp_html if sharp_html else '<li>No specific sharp story recorded.</li>'}</ul>
                <h4 style="margin:12px 0 8px 0; color:#5d4e75; border-bottom:1px solid #eee;">⚖️ Referee Factor</h4>
                <ul style="margin:0; padding-left:20px; font-size:13px;">{ref_html if ref_html else '<li>Neutral referee impact.</li>'}</ul>
            </div>
        </div>"""

    # 5. Final Email Assembly
    msg = MIMEMultipart()
    msg['Subject'] = f"{subject_prefix} Week {week} NFL Pro Analysis & Data Package"
    msg['From'] = gmail_user
    msg['To'] = "lvarughese@gmail.com"
    
    full_html = f"""
    <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height:1.6; color:#333; max-width:800px;">
            <div style="background:#2c3e50; color:white; padding:20px; text-align:center; border-radius:4px 4px 0 0;">
                <h1 style="margin:0;">NFL Week {week} Report</h1>
                <p style="margin:5px 0 0 0; opacity:0.8;">{analysis_type} | Generated: {timestamp}</p>
            </div>
            {game_cards_html if game_cards_html else '<p>No analysis data could be parsed from the file.</p>'}
            <hr style="border:0; border-top:1px solid #eee; margin:30px 0;">
            <p style="font-size:11px; color:#888;">Automated NFL Analysis Pipeline - Scrapers / Analyzers / Folders</p>
        </body>
    </html>
    """
    msg.attach(MIMEText(full_html, 'html'))

    # 6. Attach Files
    for suffix in ["executive_summary.txt", "pro_analysis.txt", "analytics.csv", "analytics.json"]:
        file_path = f"data/week{week}/week{week}_{suffix}"
        if os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)
                    print(f"DEBUG: Attached {file_path}")
            except Exception as e:
                print(f"DEBUG: Failed to attach {file_path}: {e}")

    # 7. Send
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(gmail_user, gmail_password)
        s.send_message(msg)
        s.quit()
        print("SUCCESS: Email sent successfully!")
    except Exception as e:
        print(f"FATAL ERROR: Could not send email: {e}")

if __name__ == "__main__":
    generate_report()
