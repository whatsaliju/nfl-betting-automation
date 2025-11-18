#!/usr/bin/env python3
"""
Enhanced Email Reports & File Distribution
========================================
Creates comprehensive email reports with full analysis details
and makes files easily downloadable without zipping.
"""

import os
import pandas as pd
import json
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import shutil

class EnhancedEmailReporter:
    """Generate comprehensive betting analysis emails with attachments."""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email = os.getenv('EMAIL_ADDRESS')
        self.password = os.getenv('EMAIL_PASSWORD')
    
    def generate_comprehensive_report(self, week, games):
        """Generate a comprehensive HTML email report with full analysis."""
        
        # Group games by classification
        blue_chip = [g for g in games if "BLUE CHIP" in g['classification']]
        targeted = [g for g in games if "TARGETED PLAY" in g['classification']]
        leans = [g for g in games if "LEAN" in g['classification']]
        traps = [g for g in games if "TRAP" in g['classification']]
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}
                .header {{ background: linear-gradient(135deg, #2196F3, #1976D2); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
                .game-card {{ border: 1px solid #ddd; border-radius: 8px; margin: 15px 0; padding: 15px; background: #fafafa; }}
                .blue-chip {{ border-left: 5px solid #2196F3; background: #e3f2fd; }}
                .targeted {{ border-left: 5px solid #ff9800; background: #fff3e0; }}
                .lean {{ border-left: 5px solid #9c27b0; background: #f3e5f5; }}
                .trap {{ border-left: 5px solid #f44336; background: #ffebee; }}
                .recommendation {{ font-size: 18px; font-weight: bold; color: #1976D2; margin: 10px 0; }}
                .analysis-section {{ margin: 10px 0; padding: 8px; background: white; border-radius: 5px; }}
                .sharp-story {{ color: #e65100; font-weight: bold; }}
                .score-breakdown {{ display: flex; justify-content: space-between; font-size: 12px; color: #666; }}
                .summary-stats {{ background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏈 NFL Week {week} Professional Analysis</h1>
                    <p>Generated: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p ET')}</p>
                    <p>Total Games Analyzed: {len(games)} | High Confidence Plays: {len(blue_chip + targeted)}</p>
                </div>
        """
        
        # Summary Statistics
        if games:
            avg_score = sum(g['total_score'] for g in games) / len(games)
            high_conf_count = len([g for g in games if g['confidence'] >= 7])
            
            html_content += f"""
                <div class="summary-stats">
                    <h3>📊 Weekly Analysis Summary</h3>
                    <p><strong>Average Analysis Score:</strong> {avg_score:.1f}</p>
                    <p><strong>High Confidence Plays:</strong> {high_conf_count}</p>
                    <p><strong>Sharp Money Opportunities:</strong> {len([g for g in games if abs(g.get('sharp_analysis', {}).get('spread', {}).get('differential', 0)) >= 10])}</p>
                    <p><strong>Weather Impacted Games:</strong> {len([g for g in games if g.get('weather_analysis', {}).get('factors')])}</p>
                </div>
            """
        
        # Blue Chip Plays (Full Detail)
        if blue_chip:
            html_content += f"""
                <h2>🔵 BLUE CHIP PLAYS ({len(blue_chip)})</h2>
                <p style="color: #1976D2; font-weight: bold;">Highest confidence recommendations with multiple confirming factors.</p>
            """
            
            for game in blue_chip:
                html_content += self._generate_detailed_game_card(game, "blue-chip")
        
        # Targeted Plays (Full Detail)  
        if targeted:
            html_content += f"""
                <h2>🎯 TARGETED PLAYS ({len(targeted)})</h2>
                <p style="color: #ff9800; font-weight: bold;">Solid edge plays with good supporting analysis.</p>
            """
            
            for game in targeted:
                html_content += self._generate_detailed_game_card(game, "targeted")
        
        # Leans & Traps (Summary)
        if leans:
            html_content += f"""
                <h2>👀 LEAN PLAYS ({len(leans)})</h2>
                <p>Proceed with caution - modest edges detected.</p>
            """
            for game in leans:
                html_content += self._generate_summary_card(game, "lean")
        
        if traps:
            html_content += f"""
                <h2>🚨 TRAP GAMES ({len(traps)})</h2>
                <p>Public/sharp divergence - fade the public.</p>
            """
            for game in traps:
                html_content += self._generate_summary_card(game, "trap")
        
        # Footer with file info
        html_content += f"""
                <div style="margin-top: 30px; padding: 15px; background: #f5f5f5; border-radius: 5px;">
                    <h3>📁 Analysis Files</h3>
                    <p>Complete analysis files are attached:</p>
                    <ul>
                        <li><strong>week{week}_analytics.csv</strong> - Spreadsheet with all scores and data</li>
                        <li><strong>week{week}_pro_analysis.txt</strong> - Complete text analysis</li>
                        <li><strong>week{week}_analytics.json</strong> - Raw data for further analysis</li>
                    </ul>
                    <p style="font-size: 12px; color: #666;">
                        Files are automatically synced to your cloud storage for mobile access.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _generate_detailed_game_card(self, game, card_class):
        """Generate detailed analysis card for high-confidence plays."""
        
        # Extract key data
        sharp = game.get('sharp_analysis', {})
        spread_diff = sharp.get('spread', {}).get('differential', 0)
        total_diff = sharp.get('total', {}).get('differential', 0)
        
        referee = game.get('referee_analysis', {})
        injury = game.get('injury_analysis', {})
        weather = game.get('weather_analysis', {})
        
        card_html = f"""
            <div class="game-card {card_class}">
                <h3>{game['matchup']}</h3>
                <div class="recommendation">{game['recommendation']}</div>
                
                <div class="analysis-section">
                    <h4>💰 Sharp Money Analysis</h4>
                    <div class="sharp-story">
        """
        
        # Add sharp money stories
        for story in game.get('sharp_stories', ['No significant sharp action'])[:2]:
            card_html += f"<p>• {story}</p>"
        
        card_html += f"""
                    </div>
                    <p><strong>Spread Edge:</strong> {spread_diff:+.1f}% | <strong>Total Edge:</strong> {total_diff:+.1f}%</p>
                </div>
                
                <div class="analysis-section">
                    <h4>⚖️ Referee & Situational</h4>
                    <p><strong>{referee.get('referee', 'Unknown')}:</strong> {referee.get('ats_pct', 0):.1f}% ATS ({referee.get('ats_tendency', 'Neutral')})</p>
                    <p><strong>O/U Tendency:</strong> {referee.get('ou_pct', 0):.1f}% ({referee.get('ou_tendency', 'Neutral')})</p>
        """
        
        # Add weather if significant
        if weather.get('factors'):
            card_html += f"<p><strong>Weather:</strong> {weather['description']}</p>"
        
        # Add injury analysis
        if injury.get('description') and injury['description'] != 'No significant injuries identified':
            card_html += f"<p><strong>Injuries:</strong> {injury['description']}</p>"
        
        # Add situational factors
        situational = game.get('situational_analysis', {})
        if situational.get('factors'):
            card_html += f"<p><strong>Situational:</strong> {situational['description']}</p>"
        
        card_html += f"""
                </div>
                
                <div class="score-breakdown">
                    <span>Total Score: {game['total_score']}</span>
                    <span>Confidence: {game['confidence']}/10</span>
                    <span>Sharp: {game.get('sharp_consensus_score', 0)}</span>
                    <span>Ref: {referee.get('ats_score', 0)}</span>
                    <span>Weather: {weather.get('score', 0)}</span>
                    <span>Injury: {injury.get('score', 0)}</span>
                </div>
            </div>
        """
        
        return card_html
    
    def _generate_summary_card(self, game, card_class):
        """Generate summary card for lower-confidence plays."""
        return f"""
            <div class="game-card {card_class}">
                <h4>{game['matchup']}</h4>
                <div class="recommendation" style="font-size: 16px;">{game['recommendation']}</div>
                <p>{game.get('sharp_stories', [''])[0] if game.get('sharp_stories') else 'Modest edge detected'}</p>
                <div class="score-breakdown">
                    <span>Score: {game['total_score']}</span>
                    <span>Confidence: {game['confidence']}/10</span>
                </div>
            </div>
        """
    
    def setup_cloud_sync(self, week):
        """Setup easy file access without zipping."""
        
        week_dir = f"data/week{week}"
        
        # Create a 'mobile' directory with renamed files for easy access
        mobile_dir = f"data/mobile_access"
        os.makedirs(mobile_dir, exist_ok=True)
        
        files_to_sync = [
            (f"{week_dir}/week{week}_executive_summary.txt", f"Week{week}_Summary.txt"),
            (f"{week_dir}/week{week}_pro_analysis.txt", f"Week{week}_Analysis.txt"),
            (f"{week_dir}/week{week}_analytics.csv", f"Week{week}_Data.csv"),
            (f"{week_dir}/week{week}_analytics.json", f"Week{week}_Raw.json")
        ]
        
        synced_files = []
        for source, dest_name in files_to_sync:
            if os.path.exists(source):
                dest_path = f"{mobile_dir}/{dest_name}"
                shutil.copy2(source, dest_path)
                synced_files.append(dest_name)
                print(f"📱 Synced: {dest_name}")
        
        # Create a simple index file
        with open(f"{mobile_dir}/Week{week}_Index.txt", "w") as f:
            f.write(f"NFL Week {week} Analysis Files\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Available Files:\n")
            for file_name in synced_files:
                f.write(f"- {file_name}\n")
            f.write(f"\nAccess these files directly - no zipping required!")
        
        return mobile_dir, synced_files
    
    def send_comprehensive_email(self, week, games, recipients):
        """Send the enhanced email with full analysis and attachments."""
        
        if not self.email or not self.password:
            print("⚠️ Email credentials not configured")
            return False
        
        try:
            # Generate HTML content
            html_content = self.generate_comprehensive_report(week, games)
            
            # Setup cloud sync
            mobile_dir, synced_files = self.setup_cloud_sync(week)
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email
            msg['To'] = ', '.join(recipients) if isinstance(recipients, list) else recipients
            msg['Subject'] = f"🏈 NFL Week {week} Professional Analysis - {len([g for g in games if g['confidence'] >= 7])} High Confidence Plays"
            
            # Attach HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Attach files
            week_dir = f"data/week{week}"
            attachments = [
                f"{week_dir}/week{week}_analytics.csv",
                f"{week_dir}/week{week}_pro_analysis.txt",
                f"{week_dir}/week{week}_analytics.json"
            ]
            
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(file_path)}'
                    )
                    msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email, self.password)
            text = msg.as_string()
            server.sendmail(self.email, recipients, text)
            server.quit()
            
            print(f"✅ Comprehensive email sent successfully")
            print(f"📱 Mobile files ready in: {mobile_dir}")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error sending email: {e}")
            return False


# Integration with your existing analyzer
def add_enhanced_email_to_analyzer():
    """Add enhanced email functionality to your existing analyzer."""
    
    def enhanced_generate_outputs(week, games):
        """Enhanced version of generate_outputs with comprehensive email."""
        
        # Your existing output generation
        os.makedirs(f"data/week{week}", exist_ok=True)
        
        print(f"📝 Generating enhanced reports for {len(games)} games...")
        
        # Generate all your existing files (executive summary, pro analysis, CSV, JSON)
        # ... [your existing generate_outputs code] ...
        
        # Add enhanced email reporting
        email_reporter = EnhancedEmailReporter()
        
        # Send comprehensive email
        recipients = [
            "your-email@gmail.com"  # Add your email(s) here
        ]
        
        success = email_reporter.send_comprehensive_email(week, games, recipients)
        
        if success:
            print(f"📧 Enhanced email report sent with full analysis details")
            print(f"📱 Files accessible without zipping in data/mobile_access/")
        else:
            print(f"📧 Email not configured - check environment variables:")
            print(f"   EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER")
    
    return enhanced_generate_outputs

# Usage example
if __name__ == "__main__":
    # Test the enhanced email system
    print("Enhanced Email Reporter - Test Mode")
    print("Set environment variables: EMAIL_ADDRESS, EMAIL_PASSWORD")
    print("Then integrate with your analyzer using add_enhanced_email_to_analyzer()")
