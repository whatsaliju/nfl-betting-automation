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

         # Extract richer data
                
        # Fix these field mappings:

        # Sharp money details (FIXED)
        sharp_spread = game.get('sharp_analysis', {}).get('spread', {}).get('differential', 0)
        sharp_total = game.get('sharp_analysis', {}).get('total', {}).get('differential', 0)
        
        # Market data (FIXED)  
        spread_line = game.get('sharp_analysis', {}).get('spread', {}).get('line', 'N/A')
        total_line = game.get('sharp_analysis', {}).get('total', {}).get('line', 'N/A')
        
        # Injury analysis (FIXED)
        injury_analysis = game.get('injury_analysis', {})
        total_injuries = len(injury_analysis.get('away_injuries', [])) + len(injury_analysis.get('home_injuries', []))
        injuries_text = injury_analysis.get('description', 'No injuries') if total_injuries > 0 else 'No significant injuries'
        
        # Weather (FIXED)
        weather_data = game.get('weather_analysis', {})
        weather_text = weather_data.get('description', 'Indoor/No weather concerns')
        
        # Total score (FIXED)
        total_score = game.get('total_score', 0)

        recommendation = game.get('recommendation', 'No specific recommendation')

        # Enhanced sharp activity section
        sharp_details = []
        if abs(sharp_spread) >= 5:
            edge_text = f"+{sharp_spread:.1f}%" if sharp_spread > 0 else f"{sharp_spread:.1f}%"
            sharp_details.append(f"📈 Spread Edge: {edge_text}")
        if abs(sharp_total) >= 5:
            edge_text = f"+{sharp_total:.1f}%" if sharp_total > 0 else f"{sharp_total:.1f}%"
            sharp_details.append(f"📊 Total Edge: {edge_text}")
            
        # Add your existing sharp stories
        sharp_list = game.get('sharp_stories', [])
        all_sharp_content = sharp_details + sharp_list
        sharp_html = "".join([f"<li>{s}</li>" for s in all_sharp_content]) if all_sharp_content else "<li>No specific sharp story recorded.</li>"

        # Combine Referee and Situational Data
        ref_name = game.get('referee_analysis', {}).get('referee', 'Unknown')
        ref_tendency = game.get('referee_analysis', {}).get('ats_tendency', 'NEUTRAL')
        
        # Get dynamic factors from JSON lists
        factors = []
        factors.extend(game.get('situational_analysis', {}).get('factors', []))
        factors.extend(game.get('statistical_analysis', {}).get('factors', []))
        factors_html = "".join([f"<li>{f}</li>" for f in factors]) if factors else "<li>Neutral factors detected.</li>"

        # Build enhanced card
        game_cards_html += f"""
        <div style="margin:20px 0; padding:15px; border-left:6px solid {color}; background-color:{bg}; border-radius:4px; font-family:sans-serif;">
            <h2 style="margin:0; color:#333;">{emoji} {game['matchup']}</h2>
            <div style="display:grid; grid-template-columns:2fr 1fr; gap:15px; margin:10px 0;">
                <div>
                    <p style="font-weight:bold; color:{color}; margin:0;">{class_text} | Confidence: {game.get('confidence', '0'):.1f}/20</p>
                    <p style="color:#666; margin:5px 0; font-size:14px;">📋 {recommendation}</p>
                </div>
                <div style="text-align:right;">
                    <p style="margin:0; font-size:12px; color:#666;">Spread: {spread_line}</p>
                    <p style="margin:0; font-size:12px; color:#666;">Total: {total_line}</p>
                    <p style="margin:0; font-size:12px; font-weight:bold; color:{color};">Score: {total_score:.1f}</p>
                </div>
            </div>
            
            <div style="background:white; padding:12px; border-radius:4px; border:1px solid #ddd;">
                <h4 style="margin:0 0 8px 0; color:#e65100; border-bottom:1px solid #eee;">💰 Sharp Activity</h4>
                <ul style="margin:0; padding-left:20px; font-size:13px; color:#444;">{sharp_html}</ul>
                
                <h4 style="margin:12px 0 8px 0; color:#5d4e75; border-bottom:1px solid #eee;">⚖️ Context & Intel</h4>
                <p style="font-size:12px; margin:0 0 5px 20px;"><strong>Official:</strong> {ref_name} ({ref_tendency})</p>
                <p style="font-size:12px; margin:0 0 5px 20px;"><strong>Injuries:</strong> {injuries_text}</p>
                <p style="font-size:12px; margin:0 0 5px 20px;"><strong>Weather:</strong> {weather_text}</p>
                <ul style="margin:5px 0 0 0; padding-left:20px; font-size:13px; color:#444;">{factors_html}</ul>
            </div>
        </div>"""

    # Add summary statistics at the top
    blue_chips = [g for g in games_data if 'BLUE CHIP' in g.get('classification', '').upper()]
    targeted = [g for g in games_data if 'TARGETED' in g.get('classification', '').upper()]
    landmines = [g for g in games_data if 'LANDMINE' in g.get('classification', '').upper()]
    
    # Find best edge game
    best_edge_game = max(games_data, key=lambda x: x.get('confidence', 0))
    
    summary_html = f"""
    <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin:20px 0; border-left:4px solid #007bff;">
        <h3 style="margin:0 0 10px 0; color:#007bff;">📊 Week {week} Summary</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
            <div>
                <p style="margin:5px 0;"><strong>🔵 Blue Chips:</strong> {len(blue_chips)} plays{f" (avg: {sum(g.get('confidence',0) for g in blue_chips)/len(blue_chips):.1f})" if blue_chips else ""}</p>
                <p style="margin:5px 0;"><strong>🎯 Targeted:</strong> {len(targeted)} plays{f" (avg: {sum(g.get('confidence',0) for g in targeted)/len(targeted):.1f})" if targeted else ""}</p>
            </div>
            <div>
                <p style="margin:5px 0;"><strong>❌ Avoid:</strong> {len(landmines)} landmines</p>
                <p style="margin:5px 0;"><strong>💰 Best Edge:</strong> {best_edge_game.get('matchup', 'N/A')} ({best_edge_game.get('confidence', 0):.1f})</p>
            </div>
        </div>
    </div>
    """

    # Rest of email assembly stays the same, but add summary_html
    msg = MIMEMultipart()
    subject_prefix = os.getenv('SUBJECT_PREFIX', '🏈')
    msg['Subject'] = f"{subject_prefix} Week {week} NFL Analysis"
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
