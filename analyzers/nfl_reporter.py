import smtplib, os, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def generate_report():
    week = os.getenv('WEEK')
    timestamp = os.getenv('TIMESTAMP')
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')

    # 1. Load the JSON Data (The reliable source)
    # Fixed (uses your organized structure)
    stage = os.getenv('ANALYSIS_TYPE', 'final')  # Gets 'initial', 'update', or 'final'
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

        # Extract Sharp Stories
        sharp_list = game.get('sharp_stories', [])
        sharp_html = "".join([f"<li>{s}</li>" for s in sharp_list]) if sharp_list else "<li>No specific sharp story recorded.</li>"

        # Combine Referee and Situational Data (To match your preferred style)
        ref_name = game.get('referee_analysis', {}).get('referee', 'Unknown')
        ref_tendency = game.get('referee_analysis', {}).get('ats_tendency', 'NEUTRAL')
        
        # Get dynamic factors from JSON lists
        factors = []
        factors.extend(game.get('situational_analysis', {}).get('factors', []))
        factors.extend(game.get('statistical_analysis', {}).get('factors', []))
        
        factors_html = "".join([f"<li>{f}</li>" for f in factors]) if factors else "<li>Neutral factors detected.</li>"

        # Build Card
        game_cards_html += f"""
        <div style="margin:20px 0; padding:15px; border-left:6px solid {color}; background-color:{bg}; border-radius:4px; font-family:sans-serif;">
            <h2 style="margin:0; color:#333;">{emoji} {game['matchup']}</h2>
            <p style="font-weight:bold; color:{color}; margin:5px 0;">{class_text} | Confidence: {game.get('confidence', '0')}/20</p>
            <div style="background:white; padding:12px; border-radius:4px; border:1px solid #ddd;">
                <h4 style="margin:0 0 8px 0; color:#e65100; border-bottom:1px solid #eee;">💰 Sharp Activity</h4>
                <ul style="margin:0; padding-left:20px; font-size:13px; color:#444;">{sharp_html}</ul>
                
                <h4 style="margin:12px 0 8px 0; color:#5d4e75; border-bottom:1px solid #eee;">⚖️ Market & Ref Context</h4>
                <p style="font-size:12px; margin:0 0 5px 20px;"><strong>Official:</strong> {ref_name} ({ref_tendency})</p>
                <ul style="margin:0; padding-left:20px; font-size:13px; color:#444;">{factors_html}</ul>
            </div>
        </div>"""

    # 3. Final Email Assembly (Standard logic)
    msg = MIMEMultipart()
    # Fixed (stage-aware)
    subject_prefix = os.getenv('SUBJECT_PREFIX', '🏈')
    msg['Subject'] = f"{subject_prefix} Week {week} NFL Analysis"
    msg['From'] = gmail_user
    msg['To'] = "lvarughese@gmail.com"

    # Add this one line for stage context
    stage_context = f"<p style='text-align:center; color:#e67e22; font-weight:bold;'>{stage.title()} Analysis</p>" if stage != 'final' else ""
    
    full_html = f"""
    <html>
        <body style="background-color:#f4f4f4; padding:20px;">
            <div style="max-width:800px; margin:auto; background:white; padding:20px; border-radius:8px;">
                <h1 style="text-align:center; color:#2c3e50;">NFL Week {week} Report</h1>
                {stage_context}
                <p style="text-align:center; color:#7f8c8d;">Generated: {timestamp}</p>
                {game_cards_html}
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(full_html, 'html'))

    # Send
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(gmail_user, gmail_password)
        s.send_message(msg)
        s.quit()
        print("SUCCESS: Email sent from JSON source!")
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    generate_report()
