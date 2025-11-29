#!/usr/bin/env python3
"""
NFL Professional Betting Analysis Engine - Complete Restored Version
==========================================
Synthesizes sharp money, referee trends, weather, injuries, situational factors,
statistical modeling, game theory, and schedule analysis into actionable betting intelligence.

Outputs:
- week{X}_executive_summary.txt (Top plays only)
- week{X}_pro_analysis.txt (Full narrative breakdowns)
- week{X}_analytics.csv (All data + scores)
- week{X}_analytics.json (Structured data)
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timezone
from collections import defaultdict
# >>> NEW IMPORTS FOR CONCURRENCY <<<
from concurrent.futures import ThreadPoolExecutor
from functools import partial 
# >>> END NEW IMPORTS <<<
from data.schedule_rest_2025 import SCHEDULE_REST_DATA_2025

# ================================================================
# CONFIGURATION AND WEIGHTS (NEW)
# ================================================================

# Define weights for each factor's score contribution to the total_score
# You can tune these multipliers to increase or decrease a factor's influence.
# Example tuning: Giving Statistical and Sharp a higher weight.
FACTOR_WEIGHTS = {
    'sharp_consensus_score': 1.5,   # High influence
    'referee_ats_score': 0.7,
    'referee_ou_score': 0.7,
    'weather_score': 0.5,           # Low influence, often secondary
    'injury_score': 1.2,
    'situational_score': 1.0,
    'statistical_score': 1.8,       # Highest influence
    'game_theory_score': 1.0,
    'schedule_score': 0.8
}

# Define conflict penalties and caps (Now externalized)
ANALYSIS_CONFIG = {
    # Penalty when strong Statistical Signal opposes Consensus
    'CONFLICT_PENALTY_SPREAD': -2.0, 
    
    # Penalty when Sharp Total conflicts with Referee O/U
    'CONFLICT_PENALTY_TOTAL': -3.0,
    
    # Max confidence level to assign a game with Total Conflict
    'CONFIDENCE_CAP_TOTAL_CONFLICT': 4 
}

# ================================================================
# CONSTANTS
# ================================================================

TEAM_MAP = {
    "NE": "Patriots", "NYJ": "Jets", "WAS": "Commanders", "MIA": "Dolphins",
    "CAR": "Panthers", "ATL": "Falcons", "TB": "Buccaneers", "BUF": "Bills",
    "LAC": "Chargers", "JAX": "Jaguars", "CHI": "Bears", "MIN": "Vikings",
    "GB": "Packers", "NYG": "Giants", "CIN": "Bengals", "PIT": "Steelers",
    "HOU": "Texans", "TEN": "Titans", "SF": "49ers", "ARI": "Cardinals",
    "SEA": "Seahawks", "LAR": "Rams", "BAL": "Ravens", "CLE": "Browns",
    "KC": "Chiefs", "DEN": "Broncos", "DET": "Lions", "PHI": "Eagles",
    "DAL": "Cowboys", "LV": "Raiders",
    "IND": "Colts", "NO": "Saints"

}
FULL_NAME_TO_TLA = {v.lower(): k for k, v in TEAM_MAP.items()}

# --- DATA CONSTANT: SCHEDULE REST DATA ---
# This dictionary holds the rest days for all teams entering each week of the 2025 NFL season.
# NEW FORMAT: {Week: {Team_TLA: Rest_Days}}
# This format allows the calculate_schedule_score function to look up rest days directly by TLA.
# ================================================================

# Simplified map for time zone logic (Used to calculate W2E/E2W travel fatigue)
TEAM_TIME_ZONES = {
    'SEA': 'PST', 'SF': 'PST', 'LAR': 'PST', 'LV': 'PST', 'LAC': 'PST', 'ARI': 'MST',
    'DEN': 'MST', 'KC': 'CST', 'DAL': 'CST', 'HOU': 'CST', 'CHI': 'CST', 'MIN': 'CST',
    'GB': 'CST', 'NO': 'CST', 'TEN': 'CST', 'IND': 'EST', 'JAX': 'EST', 'MIA': 'EST',
    'BUF': 'EST', 'NE': 'EST', 'NYJ': 'EST', 'NYG': 'EST', 'PHI': 'EST', 'WAS': 'EST',
    'BAL': 'EST', 'CIN': 'EST', 'CLE': 'EST', 'PIT': 'EST', 'ATL': 'EST', 'CAR': 'EST',
    'TB': 'EST', 'DET': 'EST'
}

# Teams playing in an international game (Week N) and playing *again* the following week (Week N+1)
# (i.e., they did not have a Week N+1 bye)
INTERNATIONAL_HANGOVER_WEEKS = {
    # Week 1 (Sao Paulo): KC vs LAC[cite: 1]. No Week 2 byes.
    2: ['KC', 'LAC'],

    # Week 4 (Dublin): MIN vs PIT[cite: 8]. PIT has a Week 5 bye[cite: 10].
    5: ['MIN'],

    # Week 5 (Tottenham): MIN vs CLE[cite: 9]. MIN has a Week 6 bye[cite: 11].
    6: ['CLE'],

    # Week 6 (Tottenham): DEN vs NYJ[cite: 10]. (Assuming no Week 7 byes for these teams)
    7: ['DEN', 'NYJ'],

    # Week 7 (Wembley): LAR vs JAX[cite: 12]. (Assuming no Week 8 byes for these teams)
    8: ['LAR', 'JAX'],

    # Week 10 (Madrid): WAS vs MIA[cite: 19]. (Assuming no Week 11 byes for these teams)
    11: ['WAS', 'MIA'],
}

# NOTE: The last international game (Week 12 in Germany) is not visible in the provided schedule, 
# so its subsequent hangover week (Week 13) is not included here.

# ================================================================
# UTILITY FUNCTIONS
# ================================================================
# --- UTILITY FUNCTION: CALCULATE SCHEDULE SCORE ---
def calculate_schedule_score(week, home_tla, away_tla):
    """
    Calculates schedule score with robust error handling for all weeks
    """
    try:
        # Import with error details
        from data.schedule_rest_2025 import SCHEDULE_REST_DATA_2025
        
        week_key = f"W{week}" if isinstance(week, int) else week
        rest_data = SCHEDULE_REST_DATA_2025.get(week_key, {})
        
        if not rest_data:
            # This will help debug if specific weeks are missing
            available_weeks = list(SCHEDULE_REST_DATA_2025.keys())
            return 0, f"Week {week_key} not found. Available: {available_weeks[:5]}..."
        
        home_rest = rest_data.get(home_tla, 7)
        away_rest = rest_data.get(away_tla, 7)
        
        rest_differential = home_rest - away_rest
        
        score = 0
        factors = []
        
        if rest_differential > 2:
            score = 2
            factors.append(f"HOME rest advantage (+{rest_differential} days)")
        elif rest_differential < -2:
            score = -2
            factors.append(f"AWAY rest advantage (+{abs(rest_differential)} days)")
        elif rest_differential != 0:
            score = 1 if rest_differential > 0 else -1
            factors.append(f"Minor rest edge ({abs(rest_differential)} days)")
        else:
            factors.append("Neutral schedule situation (standard rest)")
        
        description = " | ".join(factors)
        
        return score, description
        
    except ImportError as e:
        return 0, f"Schedule import failed: {e}"
    except Exception as e:
        return 0, f"Schedule error: {e}"
        
def safe_load_csv(path, required=False):
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
        if required:
            print(f"❌ Required: {path}")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error loading {path}: {e}")
        return pd.DataFrame()


def find_latest(prefix):
    directory = 'data'
    if os.path.exists(directory):
        matches = [f for f in os.listdir(directory) if f.startswith(prefix)]
        
        if matches:
            latest_filename = sorted(matches)[-1]
            return os.path.join(directory, latest_filename)
            
    return None


def normalize_matchup(s):
    """Normalize matchup string for consistent matching"""
    if not s:
        return ""
    s = s.lower().strip()

    # Unify separators
    s = s.replace(" at ", " @ ")
    s = s.replace(" vs ", " @ ")
    s = s.replace(" vs. ", " @ ")
    s = s.replace("  ", " ")
    
    # Split into teams
    parts = [p.strip() for p in s.split("@")]
    if len(parts) != 2:
        return s

    left, right = parts

    # Convert abbreviations to full names
    left = TEAM_MAP[left.upper()] if left.upper() in TEAM_MAP else left
    right = TEAM_MAP[right.upper()] if right.upper() in TEAM_MAP else right

    return f"{left.lower()} @ {right.lower()}"


def parse_injury_entry(entry_text, away_team, home_team):
    """Parse a single injury entry from RotoWire data."""
    try:
        # Basic parsing - you can enhance this based on RotoWire format
        # Example formats: "Josh Allen (Q)", "Ja'Marr Chase (Probable - Ankle)"
        
        if '(' in entry_text and ')' in entry_text:
            player_part = entry_text.split('(')[0].strip()
            status_part = entry_text.split('(')[1].split(')')[0].strip()
            
            # Determine team (simple logic - you can enhance)
            team = away_team  # Default, could be improved with team matching
            
            # Extract injury type if present
            injury_type = ''
            if '-' in status_part:
                parts = status_part.split('-')
                status = parts[0].strip()
                injury_type = parts[1].strip()
            else:
                status = status_part
            
            # Match to whitelist
            player_id = match_player_to_whitelist(player_part, team)
            
            if player_id:
                return {
                    'player_id': player_id,
                    'status': status,
                    'injury_type': injury_type,
                    'team_context': get_team_context(team)
                }
    except Exception as e:
        print(f"⚠️  Error parsing injury entry '{entry_text}': {e}")
    
    return None


def match_player_to_whitelist(player_name, team):
    """Helper to match player to injury whitelist."""
    try:
        import json
        import os
        
        whitelist_path = 'config/injury_whitelist.json'
        
        if os.path.exists(whitelist_path):
            with open(whitelist_path, 'r') as f:
                whitelist = json.load(f)
            
            players_dict = {p['id']: p for p in whitelist['injury_whitelist']['players']}
            
            # Define name_lower FIRST
            name_lower = player_name.lower().strip()
            
            # Team mapping
            team_mapping = {
                "Miami Dolphins": "MIA",
                "Washington Commanders": "WAS", 
                "Cincinnati Bengals": "CIN",
                "Pittsburgh Steelers": "PIT",
                "Buffalo Bills": "BUF",
                "Kansas City Chiefs": "KC",
                "Denver Broncos": "DEN",
                "Seattle Seahawks": "SEA",
                "Los Angeles Rams": "LAR",
                "Chicago Bears": "CHI",
                "Minnesota Vikings": "MIN",
                "Detroit Lions": "DET",
                "Philadelphia Eagles": "PHI",
                "Dallas Cowboys": "DAL",
                "Las Vegas Raiders": "LV",
                "Green Bay Packers": "GB",
                "New York Giants": "NYG",
                "Baltimore Ravens": "BAL",
                "Cleveland Browns": "CLE",
                "Tampa Bay Buccaneers": "TB",
                "Carolina Panthers": "CAR",
                "Atlanta Falcons": "ATL",
                "New Orleans Saints": "NO",
                "San Francisco 49ers": "SF",
                "Arizona Cardinals": "ARI",
                "Los Angeles Chargers": "LAC",
                "Jacksonville Jaguars": "JAX",
                "Houston Texans": "HOU",
                "Tennessee Titans": "TEN",
                "Indianapolis Colts": "IND",
                "New York Jets": "NYJ",
                "New England Patriots": "NE"
            }
            
            team_abbrev = team_mapping.get(team, "")
            
            for player_id, player_data in players_dict.items():
                player_whitelist_name = player_data['name'].lower()
                if (name_lower in player_whitelist_name or 
                    player_whitelist_name in name_lower):
                    if team_abbrev == player_data['team']:
                        print(f"✅ MATCH FOUND: {player_id}")
                        return player_id
        
        return None
    except Exception as e:
        print(f"⚠️  Error in player matching: {e}")
        return None


def get_team_context(team):
    """Get team context for injury calculations."""
    # You can expand this with actual team data
    team_contexts = {
        # QB backup situations
        'Buffalo Bills': {'backup_quality': 'poor_backup', 'scheme_dependency': 'system_dependent'},
        'Kansas City Chiefs': {'backup_quality': 'good_backup', 'scheme_dependency': 'player_dependent'},
        'Cincinnati Bengals': {'backup_quality': 'poor_backup', 'scheme_dependency': 'player_dependent'},
        'Miami Dolphins': {'backup_quality': 'poor_backup', 'scheme_dependency': 'system_dependent'},
        'Washington Commanders': {'backup_quality': 'poor_backup', 'scheme_dependency': 'player_dependent'},
        'Pittsburgh Steelers': {'backup_quality': 'good_backup', 'scheme_dependency': 'scheme_flexible'},
        'Green Bay Packers': {'backup_quality': 'average_backup', 'scheme_dependency': 'player_dependent'},
        
        # Teams with good skill position depth
        'Detroit Lions': {'backup_quality': 'good_backup', 'scheme_dependency': 'scheme_flexible'},
        'Philadelphia Eagles': {'backup_quality': 'good_backup', 'scheme_dependency': 'scheme_flexible'},
        'San Francisco 49ers': {'backup_quality': 'good_backup', 'scheme_dependency': 'system_dependent'},
        
        # Teams with poor depth
        'Carolina Panthers': {'backup_quality': 'poor_backup', 'scheme_dependency': 'player_dependent'},
        'New York Giants': {'backup_quality': 'poor_backup', 'scheme_dependency': 'player_dependent'},
        'Arizona Cardinals': {'backup_quality': 'average_backup', 'scheme_dependency': 'player_dependent'},
        # Add more teams as needed
    }
    
    return team_contexts.get(team, {
        'backup_quality': 'average_backup',
        'scheme_dependency': 'player_dependent',
        'season_importance': 'normal'
    })

# ================================================================
# SHARP MONEY ANALYZER (FIXED)
# ================================================================

class SharpMoneyAnalyzer:
    """Analyzes sharp action across spread/total/moneyline and generates narrative"""
    
    # Define the thresholds for story generation
    MODERATE_THRESHOLD = 4.0
    MASSIVE_THRESHOLD = 10.0

    @staticmethod
    def parse_percentage_pair(pct_str):
        """Parse '60% | 40%' -> (60.0, 40.0)"""
        try:
            parts = str(pct_str).split("|")
            return (float(parts[0].strip().replace("%", "")),
                    float(parts[1].strip().replace("%", "")))
        except:
            return (0.0, 0.0)

    @staticmethod
    def calculate_differential(money_pct, bets_pct):
        """Calculate sharp edge: money % - bets %"""
        return money_pct - bets_pct

    @staticmethod
    def score_differential(diff):
        """Score the differential strength"""
        if abs(diff) >= 15: return 3
        if abs(diff) >= 10: return 2
        if abs(diff) >= 5: return 1
        return 0

    @staticmethod
    def analyze_market(market_data, market_type):
        """Analyze a single market (spread/total/ML)"""
        if market_data.empty:
            return {
                'differential': 0,
                'score': 0,
                'direction': 'NEUTRAL',
                'bets_pct': 0,
                'money_pct': 0,
                'line': '',
                'description': 'No data'
            }
        
        row = market_data.iloc[0]
        bets = SharpMoneyAnalyzer.parse_percentage_pair(row['Bets %'])
        money = SharpMoneyAnalyzer.parse_percentage_pair(row['Money %'])
        
        # Use away team (first value) as reference for spread/moneyline, OVER for total
        diff = SharpMoneyAnalyzer.calculate_differential(money[0], bets[0])
        score = SharpMoneyAnalyzer.score_differential(diff)
        
        # Determine direction
        if market_type == 'Total':
            direction = 'OVER' if diff > 0 else 'UNDER' if diff < 0 else 'NEUTRAL'
        else:
            # Positive diff means money on AWAY team, Negative means money on HOME team
            direction = 'AWAY' if diff > 0 else 'HOME' if diff < 0 else 'NEUTRAL'
        
        return {
            'differential': diff,
            'score': score * (1 if diff > 0 else -1),
            'direction': direction,
            'bets_pct': bets[0],
            'money_pct': money[0],
            'line': row.get('Line', ''),
            'description': f"{direction} ({diff:+.1f}% edge)"
        }

    # ============================================================
    # 🎯 NEW: NARRATIVE GENERATOR FUNCTION (THE FIX)
    # ============================================================
    @staticmethod
    def generate_sharp_story_text(sharp_spread_diff, sharp_total_diff):
        """
        Generates the narrative for the SHARP MONEY STORY section.
        Implements the fix for the too-high threshold.
        """
        
        insights = []
        
        # Determine Spread Action
        abs_spread = abs(sharp_spread_diff)
        if abs_spread >= SharpMoneyAnalyzer.MASSIVE_THRESHOLD:
            direction = "AWAY" if sharp_spread_diff > 0 else "HOME"
            insights.append(f"💰 MASSIVE EDGE: {abs_spread:.1f}% differential on Spread ({direction})")
        elif abs_spread >= SharpMoneyAnalyzer.MODERATE_THRESHOLD:
            direction = "AWAY" if sharp_spread_diff > 0 else "HOME"
            insights.append(f"📉 Moderate sharp action detected on the Spread ({direction})")

        # Determine Total Action
        abs_total = abs(sharp_total_diff)
        if abs_total >= SharpMoneyAnalyzer.MASSIVE_THRESHOLD:
            direction = "OVER" if sharp_total_diff > 0 else "UNDER"
            insights.append(f"💰 MASSIVE EDGE: {abs_total:.1f}% differential on Total ({direction})")
        elif abs_total >= SharpMoneyAnalyzer.MODERATE_THRESHOLD:
            direction = "OVER" if sharp_total_diff > 0 else "UNDER"
            insights.append(f"📈 Moderate sharp action detected on the Total ({direction})")

        # Check for Sharp Divergence (Significant action on both, but opposite trends)
        if insights and len(insights) == 2:
            spread_dir = "HOME" if sharp_spread_diff < 0 else "AWAY"
            total_dir = "UNDER" if sharp_total_diff < 0 else "OVER"
            
            # Divergence logic (e.g., Home/Under or Away/Over are typical divergences)
            is_divergence = (spread_dir == 'HOME' and total_dir == 'UNDER') or \
                            (spread_dir == 'AWAY' and total_dir == 'OVER')

            if is_divergence:
                 # Override separate stories with a single, clear divergence story
                return (f"📈 DIVERGENCE: Sharps on {spread_dir} team and {total_dir} - "
                        f"expect action on the {spread_dir} and a high-scoring game.")
            
            # No divergence, just list the insights
            return "\n  ".join(insights)
        
        # Return only the single insight or the default balance message
        if insights:
            return insights[0]

        # Default message if no significant action detected on either market
        return "Sharp action relatively balanced across markets"


# ================================================================
# REFEREE ANALYZER
# ================================================================

class RefereeAnalyzer:
    """Analyzes referee trends"""
    
    @staticmethod
    def score_ats(ats_pct):
        if ats_pct >= 60: return 3
        if ats_pct >= 55: return 2
        if ats_pct <= 40: return -2
        if ats_pct <= 35: return -3
        return 0
    
    @staticmethod
    def score_ou(ou_pct):
        if ou_pct >= 60: return 2  # Over trend
        if ou_pct <= 40: return -2  # Under trend
        return 0
    
    @staticmethod
    @staticmethod
    def analyze(ref_data):
        # Check for and safely access 'ats_pct' attribute (Fixes AttributeError)
        if hasattr(ref_data, 'ats_pct'):
            ats_pct = float(str(ref_data.ats_pct).replace('%', ''))
        else:
            ats_pct = 50.0 # Default if column is missing
    
        # Check for and safely access 'ou_pct' attribute (Fixes AttributeError)
        if hasattr(ref_data, 'ou_pct'):
            ou_pct = float(str(ref_data.ou_pct).replace('%', ''))
        else:
            ou_pct = 50.0 # Default if column is missing
    
        ats_score = RefereeAnalyzer.score_ats(ats_pct)
        ou_score = RefereeAnalyzer.score_ou(ou_pct)
    
        # Determine tendency
        if ats_pct >= 55:
            ats_tend = "STRONG FAVORITE COVERAGE"
        elif ats_pct <= 45:
            ats_tend = "DOG-FRIENDLY"
        else:
            ats_tend = "NEUTRAL"
    
        if ou_pct >= 55:
            ou_tend = "OVER TENDENCY"
        elif ou_pct <= 45:
            ou_tend = "UNDER TENDENCY"
        else:
            ou_tend = "NEUTRAL TOTAL"
    
        return {
            'ats_pct': ats_pct,
            'ou_pct': ou_pct,
            'ats_score': ats_score,
            'ou_score': ou_score,
            'ats_tendency': ats_tend,
            'ou_tendency': ou_tend,
            # FINAL CORRECTION: Use getattr() for the namedtuple
            'referee': getattr(ref_data, 'referee', 'Unknown')
        }


# ================================================================
# WEATHER ANALYZER (FIXED)
# ================================================================

class WeatherAnalyzer:
    """Analyzes weather impact with improved parsing and scoring for heat/cold/wind"""
    
    @staticmethod
    def analyze(weather_str):
        """
        Parse weather from RotoWire format:
        Example: "47% Rain\n40°  18 mph W Wind"
        or "Dome\nIn Domed Stadium"
        """
        s = str(weather_str).strip()
        
        if not s or s.lower() == 'none':
            return {'score': 0, 'factors': [], 'description': 'None'}
        
        # Dome detection
        if 'dome' in s.lower():
            return {'score': 0, 'factors': ['Dome'], 'description': 'Dome (no weather impact)'}
        
        score = 0
        factors = []
        
        # Split by newline (RotoWire format)
        lines = s.split('\n')
        
        for line in lines:
            # Precipitation percentage
            if '%' in line:
                import re
                precip_match = re.search(r'(\d+)%', line)
                if precip_match:
                    precip = int(precip_match.group(1))
                    if precip >= 60:
                        score -= 2
                        factors.append(f"Heavy precipitation ({precip}%)")
                    elif precip >= 40:
                        score -= 1
                        factors.append(f"Moderate precipitation ({precip}%)")
                    elif precip >= 20:
                        factors.append(f"Light precipitation ({precip}%)")
                
                # Check for rain/snow keywords
                if 'rain' in line.lower():
                    if 'heavy' not in line.lower() and precip < 60:
                        factors.append("Rain expected")
                if 'snow' in line.lower():
                    score -= 1
                    factors.append("Snow expected")
            
            # Wind speed
            if 'mph' in line.lower():
                import re
                wind_match = re.search(r'(\d+)\s*mph', line, re.IGNORECASE)
                if wind_match:
                    wind = int(wind_match.group(1))
                    if wind >= 20:
                        score -= 2
                        factors.append(f"High wind ({wind} mph)")
                    elif wind >= 15:
                        score -= 1
                        factors.append(f"Windy conditions ({wind} mph)")
            
            # Temperature (Enhanced with Extreme Heat)
            if '°' in line:
                import re
                temp_match = re.search(r'(\d+)°', line)
                if temp_match:
                    temp = int(temp_match.group(1))
                    if temp <= 32:
                        score -= 1
                        factors.append(f"Freezing temperature ({temp}°F)")
                    elif temp <= 40:
                        factors.append(f"Cold weather ({temp}°F)")
                    elif temp >= 90:
                        score -= 1  # Extreme heat can impact offensive pace
                        factors.append(f"Extreme heat ({temp}°F)")
        
        desc = ' | '.join(factors) if factors else 'Good conditions'
        
        return {
            'score': score,
            'factors': factors,
            'description': desc
        }


# ================================================================
# ENHANCED INJURY ANALYZER
# ================================================================

class InjuryAnalyzer:
    """Analyzes injury impact from Action Network, RotoWire, and whitelist data"""
    
    def __init__(self):
        """Initialize with injury whitelist."""
        self.whitelist = self.load_whitelist()
        self.players_dict = {p['id']: p for p in self.whitelist.get('players', [])} if self.whitelist else {}
    
    def load_whitelist(self):
        """Load the injury whitelist from config."""
        try:
            whitelist_path = 'config/injury_whitelist.json'
            if os.path.exists(whitelist_path):
                with open(whitelist_path, 'r') as f:
                    data = json.load(f)
                    return data['injury_whitelist']
            else:
                print(f"⚠️ Injury whitelist not found at {whitelist_path}")
                return None
        except Exception as e:
            print(f"⚠️ Error loading injury whitelist: {e}")
            return None
    
   def process_rotowire_injuries(self, rotowire_file):
    """Process injury data from RotoWire file."""
    injury_data = []
    
    if not os.path.exists(rotowire_file):
        print(f"⚠️ RotoWire file not found: {rotowire_file}")
        return injury_data
    
    try:
        df = pd.read_csv(rotowire_file)
        
        for _, row in df.iterrows():
            injury_str = row.get('injuries', '')
            if injury_str and pd.notna(injury_str) and injury_str.lower() != 'none':
                # Parse injury string
                injuries = self.parse_rotowire_injuries(injury_str)
                for inj in injuries:
                    # FIX: Convert team abbreviations to full names
                    away_tla = row.get('away', '')
                    home_tla = row.get('home', '')
                    away_full = TEAM_MAP.get(away_tla, away_tla)
                    home_full = TEAM_MAP.get(home_tla, home_tla)
                    inj['team'] = f"{away_full} / {home_full}"
                    injury_data.append(inj)
    except Exception as e:
        print(f"⚠️ Error processing RotoWire injuries: {e}")
    
    return injury_data
    
    @staticmethod
    def parse_rotowire_injuries(injury_str):
        """Parse RotoWire injury format: 'Player (POS)-STATUS, Player (POS)-STATUS'"""
        s = str(injury_str).strip()
        
        if not s or s.lower() == 'none':
            return []
        
        injuries = []
        # Split by comma for multiple injuries
        parts = s.split(',')
        
        # Use regex for robust parsing of "Player Name (POS)-STATUS"
        import re
        # Pattern captures: (Player Name) (POS) (STATUS)
        injury_pattern = re.compile(r'(.+?)\s*\((.+?)\)\s*-\s*(.+)', re.IGNORECASE)

        for part in parts:
            part = part.strip()
            if not part or part.lower() == 'none':
                continue
            
            match = injury_pattern.match(part)
            
            if match:
                try:
                    player_name = match.group(1).strip()
                    pos = match.group(2).strip()
                    status = match.group(3).strip()

                    injuries.append({
                        'player': player_name,
                        'position': pos,
                        'status': status
                    })
                except:
                    # Skip malformed entry
                    continue
        
        return injuries
    
    def analyze_game_injuries(self, away_team, home_team, injury_data):
        """Comprehensive game-level injury analysis."""
        away_injuries = []
        home_injuries = []
        
        # Process available injury data
        for injury in injury_data:
            if away_team.lower() in injury.get('team', '').lower():
                away_injuries.append(injury)
            elif home_team.lower() in injury.get('team', '').lower():
                home_injuries.append(injury)
        
        # Calculate team impacts
        away_impact = self.calculate_team_impact(away_injuries, away_team)
        home_impact = self.calculate_team_impact(home_injuries, home_team)
        
        # Net impact (positive favors home, negative favors away)
        net_impact = home_impact - away_impact
        
        # Generate analysis
        game_analysis = self.generate_game_analysis(away_team, home_team, away_impact, home_impact, net_impact)
        
        # Betting recommendations
        betting_recs = self.generate_betting_recommendations(away_team, home_team, net_impact, away_injuries, home_injuries)
        
        return {
            'away_injuries': away_injuries,
            'home_injuries': home_injuries,
            'away_impact': away_impact,
            'home_impact': home_impact,
            'net_impact': net_impact,
            'injury_edge': 'STRONG EDGE' if abs(net_impact) >= 3 else 'MODERATE EDGE' if abs(net_impact) >= 1 else 'NO EDGE',
            'game_analysis': game_analysis,
            'betting_recommendations': betting_recs
        }
    
    def calculate_team_impact(self, injuries, team_name):
        """Calculate total injury impact for a team."""
        total_impact = 0
        
        for injury in injuries:
            player_id = self.enhanced_match_player(injury['player'], team_name)
            if player_id and player_id in self.players_dict:
                player_data = self.players_dict[player_id]
                impact = self.calculate_player_impact(injury, player_data)
                total_impact += impact
        
        return min(total_impact, 10)  # Cap at 10 points

    def enhanced_match_player(self, player_name, team_name):
        """Enhanced player matching with fuzzy name matching for abbreviations"""
        if not self.players_dict:
            return None
        
        name_lower = player_name.lower().strip()
        
        # Team abbreviation mapping (your existing one)
        team_mapping = {
            "Miami Dolphins": "MIA", "Washington Commanders": "WAS", "Cincinnati Bengals": "CIN",
            "Pittsburgh Steelers": "PIT", "Buffalo Bills": "BUF", "Kansas City Chiefs": "KC",
            "Denver Broncos": "DEN", "Seattle Seahawks": "SEA", "Los Angeles Rams": "LAR",
            "Chicago Bears": "CHI", "Minnesota Vikings": "MIN", "Detroit Lions": "DET",
            "Philadelphia Eagles": "PHI", "Dallas Cowboys": "DAL", "Las Vegas Raiders": "LV",
            "Green Bay Packers": "GB", "New York Giants": "NYG", "Baltimore Ravens": "BAL",
            "Cleveland Browns": "CLE", "Tampa Bay Buccaneers": "TB", "Carolina Panthers": "CAR",
            "Atlanta Falcons": "ATL", "New Orleans Saints": "NO", "San Francisco 49ers": "SF",
            "Arizona Cardinals": "ARI", "Los Angeles Chargers": "LAC", "Jacksonville Jaguars": "JAX",
            "Houston Texans": "HOU", "Tennessee Titans": "TEN", "Indianapolis Colts": "IND",
            "New York Jets": "NYJ", "New England Patriots": "NE"
        }
        
        team_abbrev = team_mapping.get(team_name, team_name)
        
        # Enhanced matching with multiple strategies
        for player_id, player_data in self.players_dict.items():
            if team_abbrev != player_data['team']:
                continue  # Skip wrong team
                
            player_whitelist_name = player_data['name'].lower()
            
            # Strategy 1: Exact match (existing)
            if name_lower == player_whitelist_name:
                return player_id
                
            # Strategy 2: Simple substring match (existing)
            if name_lower in player_whitelist_name or player_whitelist_name in name_lower:
                return player_id
                
            # Strategy 3: Handle abbreviations (NEW)
            # Example: "A. St. Brown" should match "Amon-Ra St. Brown"
            if self._matches_with_abbreviation(name_lower, player_whitelist_name):
                return player_id
                
            # Strategy 4: Last name + first initial match (NEW)
            # Example: "J. Allen" should match "Josh Allen" 
            if self._matches_last_name_initial(name_lower, player_whitelist_name):
                return player_id
        
        return None
    
    def _matches_with_abbreviation(self, input_name, whitelist_name):
        """Check if abbreviated name matches full name"""
        # Split both names into parts
        input_parts = input_name.replace('.', '').split()
        whitelist_parts = whitelist_name.split()
        
        if len(input_parts) != len(whitelist_parts):
            return False
        
        for i, (inp, wl) in enumerate(zip(input_parts, whitelist_parts)):
            # If input is single character, check if it's first letter of whitelist
            if len(inp) == 1:
                if inp != wl[0]:
                    return False
            else:
                # Full word must match exactly
                if inp != wl:
                    return False
        
        return True
    
    def _matches_last_name_initial(self, input_name, whitelist_name):
        """Check if 'J. Allen' matches 'Josh Allen' pattern"""
        input_parts = input_name.replace('.', '').split()
        whitelist_parts = whitelist_name.split()
        
        if len(input_parts) != 2 or len(whitelist_parts) != 2:
            return False
            
        # First part should be single initial matching first letter of whitelist first name
        if len(input_parts[0]) == 1 and input_parts[0] == whitelist_parts[0][0]:
            # Second part should match last name exactly
            if input_parts[1] == whitelist_parts[1]:
                return True
        
        return False
    
    # Test the matching with your actual data
    def test_enhanced_matching():
        """Test the enhanced matching with real examples"""
        
        # Simulate your whitelist entry
        test_whitelist = {
            "stbrown_amonra_det_wr": {
                "name": "Amon-Ra St. Brown",
                "team": "DET", 
                "pos": "WR"
            },
            "allen_josh_buf_qb": {
                "name": "Josh Allen",
                "team": "BUF",
                "pos": "QB"  
            }
        }
        
        # Test cases from RotoWire format
        test_cases = [
            ("A. St. Brown", "Detroit Lions", "stbrown_amonra_det_wr"),
            ("J. Allen", "Buffalo Bills", "allen_josh_buf_qb"),
            ("Josh Allen", "Buffalo Bills", "allen_josh_buf_qb"),
            ("Amon-Ra St. Brown", "Detroit Lions", "stbrown_amonra_det_wr")
        ]
        
        # Create mock analyzer
        class MockAnalyzer:
            def __init__(self):
                self.players_dict = test_whitelist
                
            def enhanced_match_player(self, player_name, team_name):
                # Your enhanced function logic here
                pass
        
        print("Testing enhanced player matching:")
        for player, team, expected in test_cases:
            print(f"'{player}' + '{team}' -> Expected: {expected}")
    
    if __name__ == "__main__":
        test_enhanced_matching()
    
    def calculate_player_impact(self, injury, player_data):
        """Calculate impact points for a specific injured player."""
        status = injury.get('status', '').upper()
        position = player_data.get('pos', '').upper()
        tier = player_data.get('tier', 3)
        
        # Base impact by tier and position
        if position == 'QB':
            base_impact = {1: 5, 2: 4, 3: 3}.get(tier, 2)
        elif position in ['WR', 'RB', 'TE']:
            base_impact = {1: 3, 2: 2, 3: 1.5}.get(tier, 1)
        elif position in ['LT', 'EDGE', 'CB']:
            base_impact = {1: 2.5, 2: 2, 3: 1}.get(tier, 0.5)
        else:
            base_impact = {1: 1.5, 2: 1, 3: 0.5}.get(tier, 0.5)
        
        # Status multiplier
        if 'OUT' in status or 'O' == status:
            multiplier = 1.0
        elif 'DOUBTFUL' in status or 'D' == status:
            multiplier = 0.7
        elif 'QUESTIONABLE' in status or 'Q' == status:
            multiplier = 0.4
        else:
            multiplier = 0.2
        
        return base_impact * multiplier
    
    def generate_game_analysis(self, away_team, home_team, away_impact, home_impact, net_impact):
        """Generate readable analysis of injury situation."""
        if abs(net_impact) < 0.5:
            return f"No significant injury edge detected between {away_team} and {home_team}."
        
        if net_impact > 2:
            return f"Major injury advantage for {home_team}. {away_team} dealing with {away_impact:.1f} points of injury impact vs {home_impact:.1f} for {home_team}."
        elif net_impact > 1:
            return f"Moderate injury edge favors {home_team}. Net advantage of {net_impact:.1f} points."
        elif net_impact < -2:
            return f"Major injury advantage for {away_team}. {home_team} dealing with {home_impact:.1f} points of injury impact vs {away_impact:.1f} for {away_team}."
        elif net_impact < -1:
            return f"Moderate injury edge favors {away_team}. Net advantage of {abs(net_impact):.1f} points."
        else:
            return f"Minor injury edge detected. Net impact: {net_impact:+.1f} points."
    
    def generate_betting_recommendations(self, away_team, home_team, net_impact, away_injuries, home_injuries):
        """Generate specific betting recommendations based on injuries."""
        recs = []
        
        if abs(net_impact) >= 2:
            if net_impact > 0:
                recs.append(f"Consider {home_team} spread due to injury advantage")
            else:
                recs.append(f"Consider {away_team} spread due to injury advantage")
        
        # Check for QB injuries specifically
        qb_injuries = [inj for inj in (away_injuries + home_injuries) if 'QB' in inj.get('position', '')]
        if qb_injuries:
            recs.append("QB injury detected - consider UNDER total")
        
        return recs
    
    @staticmethod
    def match_action_network_injuries(team_name, action_injuries_df):
        """Match injuries from Action Network by team name"""
        if action_injuries_df.empty:
            return []
        
        # Match team name (Action Network uses full names like "New England Patriots")
        team_injuries = action_injuries_df[
            action_injuries_df['team'].str.contains(team_name, case=False, na=False)
        ]
        
        injuries = []
        for _, inj in team_injuries.iterrows():
            injuries.append({
                'player': inj['player'],
                'position': inj['pos'],
                'status': inj['status'],
                'injury_type': inj.get('injury', 'Unknown')
            })
        
        return injuries
    
    @staticmethod
    def score_injury_impact(injuries):
        """Calculate injury impact score based on position and status"""
        score = 0
        factors = []
        
        for inj in injuries:
            pos = inj.get('position', '').upper()
            status = inj.get('status', '').upper()
            player = inj.get('player', 'Player')
            
            # Critical positions
            if pos == 'QB':
                if 'OUT' in status or 'O' == status:
                    score -= 3
                    factors.append(f"🚨 CRITICAL: {player} (QB) OUT")
                elif 'DOUBTFUL' in status or 'D' == status:
                    score -= 2
                    factors.append(f"⚠️ {player} (QB) DOUBTFUL")
                elif 'QUESTIONABLE' in status or 'Q' == status:
                    score -= 1
                    factors.append(f"⚠️ {player} (QB) QUESTIONABLE")
            
            # Impact skill positions
            elif pos in ['WR', 'RB', 'TE']:
                if 'OUT' in status or 'O' == status:
                    score -= 1
                    factors.append(f"{player} ({pos}) OUT")
                elif 'DOUBTFUL' in status or 'D' == status:
                    score -= 1
                    factors.append(f"{player} ({pos}) DOUBTFUL")
            
            # Offensive line
            elif pos in ['OL', 'T', 'G', 'C']:
                if 'OUT' in status or 'O' == status:
                    score -= 1
                    factors.append(f"{player} ({pos}) OUT")
        
        return score, factors
    
    @staticmethod
    def analyze(injury_str, team_name=None, action_injuries_df=None):
        """
        Main injury analysis - uses both RotoWire and Action Network data
        
        Args:
            injury_str: RotoWire injury string
            team_name: Full team name for Action Network matching
            action_injuries_df: Action Network injuries DataFrame
        """
        all_injuries = []
        
        # Parse RotoWire injuries
        rotowire_injuries = InjuryAnalyzer.parse_rotowire_injuries(injury_str)
        all_injuries.extend(rotowire_injuries)
        
        # Add Action Network injuries if available
        if team_name and action_injuries_df is not None and not action_injuries_df.empty:
            an_injuries = InjuryAnalyzer.match_action_network_injuries(team_name, action_injuries_df)
            # Merge without duplicates (prioritize RotoWire status if same player)
            for an_inj in an_injuries:
                if not any(rw['player'].lower() in an_inj['player'].lower() for rw in rotowire_injuries):
                    all_injuries.append(an_inj)
        
        # Score the combined injuries
        score, factors = InjuryAnalyzer.score_injury_impact(all_injuries)
        
        return {
            'score': score,
            'factors': factors,
            'description': ', '.join(factors) if factors else 'No significant injuries'
        }


# ================================================================
# INJURY INTEGRATION CLASS
# ================================================================

class InjuryIntegration:
    """Integrates injury analysis into game breakdowns."""
    
    @staticmethod
    def analyze_game_injuries(away_full, home_full, week):
        """Analyze injuries for a specific game."""
        try:
            analyzer = InjuryAnalyzer()
            
            # Load RotoWire injury data
            rotowire_week_pattern = f"rotowire_lineups_week{week}_"
            rotowire_file = find_latest(rotowire_week_pattern)
            
            # Fall back to global if no week file found
            if not rotowire_file:
                rotowire_file = find_latest("rotowire_lineups_")
            
            print(f"🔍 Looking for injury file: {rotowire_file}")
            print(f"🔍 File exists: {os.path.exists(rotowire_file)}")
            injury_data = analyzer.process_rotowire_injuries(rotowire_file)
            print(f"🔍 Injury data loaded: {len(injury_data)} injuries found")
            
            if not injury_data:
                return {
                    'away_team': away_full,
                    'home_team': home_full,
                    'analysis': 'No significant injury impacts identified',
                    'recommendations': [],
                    'injury_score': 0
                }
            
            # Analyze game-level injuries
            game_analysis = analyzer.analyze_game_injuries(away_full, home_full, injury_data)
            
            return {
                'away_team': away_full,
                'home_team': home_full,
                'analysis': game_analysis['game_analysis'],
                'recommendations': game_analysis['betting_recommendations'],
                'injury_score': game_analysis['net_impact'],
                'away_injuries': game_analysis['away_injuries'],
                'home_injuries': game_analysis['home_injuries'],
                'injury_edge': game_analysis['injury_edge']
            }
            
        except Exception as e:
            print(f"⚠️  Error in injury analysis for {away_full} @ {home_full}: {e}")
            
            return {
                'away_team': away_full,
                'home_team': home_full,
                'analysis': 'Injury analysis unavailable',
                'recommendations': [],
                'injury_score': 0
            }


# ================================================================
# SITUATIONAL ANALYZER
# ================================================================

class SituationalAnalyzer:
    """Analyzes situational betting factors"""
    
    # NFL Division mappings
    DIVISIONS = {
        'AFC_EAST': ['Patriots', 'Jets', 'Bills', 'Dolphins'],
        'AFC_NORTH': ['Steelers', 'Ravens', 'Browns', 'Bengals'],
        'AFC_SOUTH': ['Texans', 'Colts', 'Titans', 'Jaguars'],
        'AFC_WEST': ['Chiefs', 'Raiders', 'Broncos', 'Chargers'],
        'NFC_EAST': ['Cowboys', 'Giants', 'Eagles', 'Commanders'],
        'NFC_NORTH': ['Packers', 'Bears', 'Lions', 'Vikings'],
        'NFC_SOUTH': ['Saints', 'Panthers', 'Falcons', 'Buccaneers'],
        'NFC_WEST': ['49ers', 'Seahawks', 'Rams', 'Cardinals']
    }
    
    # High-profile teams that get public attention
    PUBLIC_TEAMS = ['Cowboys', 'Packers', 'Steelers', 'Patriots', 'Chiefs']
    
    # Teams that struggle with travel/weather
    DOME_TEAMS = ['Saints', 'Falcons', 'Lions', 'Vikings', 'Cardinals', 'Rams', 'Chargers']
    WARM_WEATHER_TEAMS = ['Dolphins', 'Buccaneers', 'Jaguars', 'Texans', 'Cardinals', 'Chargers', 'Raiders']
    
    @staticmethod
    def get_team_division(team):
        """Find which division a team belongs to"""
        for div, teams in SituationalAnalyzer.DIVISIONS.items():
            if team in teams:
                return div
        return None
    
    @staticmethod
    def is_divisional_game(away_team, home_team):
        """Check if this is a divisional matchup"""
        away_div = SituationalAnalyzer.get_team_division(away_team)
        home_div = SituationalAnalyzer.get_team_division(home_team)
        return away_div == home_div and away_div is not None
    
    @staticmethod
    def is_primetime(game_time):
        """Detect primetime games (SNF, MNF, TNF)"""
        if not game_time or str(game_time).lower() == 'none':
            return False
        
        time_str = str(game_time).lower()
        # Look for evening games or specific primetime indicators
        if any(indicator in time_str for indicator in ['8:', '7:', '9:', 'pm', 'snf', 'mnf', 'tnf']):
            return True
        return False
    
    @staticmethod
    def has_travel_disadvantage(away_team, home_team, game_time):
        """Detect challenging travel situations"""
        factors = []
        
        # International game detection (London, Germany, Mexico)
        time_str = str(game_time).lower()
        if any(indicator in time_str for indicator in ['9:30', '9:', 'london', 'germany', 'mexico', 'international']):
            factors.append("International game - travel/time zone factors")
        
        # West coast team traveling east for early games
        west_coast = ['49ers', 'Seahawks', 'Rams', 'Chargers', 'Raiders', 'Cardinals']
        east_coast = ['Patriots', 'Jets', 'Bills', 'Dolphins', 'Giants', 'Eagles', 'Commanders', 'Panthers', 'Falcons', 'Buccaneers']
        
        if (away_team in west_coast and home_team in east_coast and 
            game_time and '1:' in str(game_time)):
            factors.append("West coast early travel")
        
        # Altitude advantage (Denver)
        if home_team == 'Broncos' and away_team not in ['Broncos']:
            factors.append("Altitude advantage")
            
        return factors
    
    @staticmethod
    def has_weather_advantage(away_team, home_team, weather_data):
        """Detect weather-based advantages"""
        factors = []
        weather_str = str(weather_data).lower()
        
        if not weather_str or weather_str == 'none':
            return factors
        
        # Dome teams playing in bad weather
        if (away_team in SituationalAnalyzer.DOME_TEAMS and 
            any(cond in weather_str for cond in ['rain', 'snow', 'wind', 'cold'])):
            factors.append("Dome team in bad weather")
        
        # Warm weather teams in cold
        if (away_team in SituationalAnalyzer.WARM_WEATHER_TEAMS and
            any(cond in weather_str for cond in ['°f', 'cold', 'snow']) and
            any(str(temp) in weather_str for temp in range(20, 45))):
            factors.append("Warm weather team in cold")
            
        return factors
    
    @staticmethod
    def has_public_bias(away_team, home_team, public_pct):
        """Detect public betting bias"""
        factors = []
        
        # High-profile teams getting too much public action
        if public_pct >= 65:
            if away_team in SituationalAnalyzer.PUBLIC_TEAMS:
                factors.append(f"Public overexposed on {away_team}")
            elif home_team in SituationalAnalyzer.PUBLIC_TEAMS:
                factors.append(f"Public overexposed on {home_team}")
        
        return factors
    
    @staticmethod
    def detect_scheduling_edge(week, game_data):
        """Detect scheduling advantages"""
        factors = []
        
        # Thursday games tend to be sloppy
        if game_data.get('game_time') and 'thu' in str(game_data.get('game_time')).lower():
            factors.append("Thursday Night Football (typically lower scoring)")
            
        return factors
    
    @staticmethod
    def detect_cupcake_games(away_team, home_team, spread_line):
        """Detect potential cupcake/blowout games"""
        factors = []
        
        if not spread_line:
            return factors
            
        try:
            # Extract spread value from line
            import re
            spread_match = re.search(r'([+-]?\d+\.?\d*)', str(spread_line))
            if not spread_match:
                return factors
                
            spread = abs(float(spread_match.group(1)))
            
            # Large spreads often lead to cupcake scenarios
            if spread >= 14:
                factors.append(f"Large spread ({spread}) - potential cupcake game")
            elif spread >= 10:
                factors.append(f"Double-digit spread ({spread}) - blowout risk")
                
        except (ValueError, AttributeError):
            pass
            
        return factors
    
    @staticmethod
    def detect_let_down_spots(away_team, home_team, week):
        """Detect potential letdown spots"""
        factors = []
        
        # Teams that might have motivation issues in certain weeks
        if week >= 15:  # Late season games where playoff spots are locked
            factors.append("Late season - motivation concerns")
            
        return factors
    
    @staticmethod
    def analyze(game_data, week):
        """Main situational analysis function"""
        away_team = game_data.get('away', '')
        home_team = game_data.get('home', '')
        game_time = game_data.get('game_time', '')
        weather = game_data.get('weather_analysis', {}).get('description', '')
        public_pct = game_data.get('public_exposure', 50)
        spread_line = game_data.get('spread_line', '')
        
        situational_score = 0
        factors = []
        
        # Divisional game analysis
        if SituationalAnalyzer.is_divisional_game(away_team, home_team):
            situational_score += 1  # Slight edge for unders in divisional games
            factors.append("Divisional matchup (familiarity factor)")
        
        # Primetime analysis
        if SituationalAnalyzer.is_primetime(game_time):
            situational_score -= 1  # Primetime games often have public overreaction
            factors.append("Primetime game (public overexposure)")
        
        # Travel disadvantages
        travel_factors = SituationalAnalyzer.has_travel_disadvantage(away_team, home_team, game_time)
        if travel_factors:
            situational_score += 1  # Advantage for home team
            factors.extend(travel_factors)
        
        # Weather advantages
        weather_factors = SituationalAnalyzer.has_weather_advantage(away_team, home_team, weather)
        if weather_factors:
            situational_score += 1  # Advantage for home team
            factors.extend(weather_factors)
        
        # Public bias detection
        public_factors = SituationalAnalyzer.has_public_bias(away_team, home_team, public_pct)
        if public_factors:
            situational_score += 1  # Contrarian value
            factors.extend(public_factors)
        
        # Scheduling edges
        schedule_factors = SituationalAnalyzer.detect_scheduling_edge(week, game_data)
        if schedule_factors:
            situational_score += 1
            factors.extend(schedule_factors)
        
        # Cupcake/blowout detection
        cupcake_factors = SituationalAnalyzer.detect_cupcake_games(away_team, home_team, spread_line)
        if cupcake_factors:
            situational_score -= 1  # Negative for betting favorites in cupcakes
            factors.extend(cupcake_factors)
        
        # Letdown spots
        letdown_factors = SituationalAnalyzer.detect_let_down_spots(away_team, home_team, week)
        if letdown_factors:
            situational_score -= 1  # Motivation concerns
            factors.extend(letdown_factors)
        
        return {
            'score': situational_score,
            'factors': factors,
            'description': ', '.join(factors) if factors else 'No significant situational factors'
        }


# ================================================================
# STATISTICAL MODELING ANALYZER
# ================================================================

class StatisticalAnalyzer:
    """Advanced statistical modeling for team performance"""
    
    @staticmethod
    def calculate_implied_probability(line):
        """Convert American odds to implied probability"""
        try:
            # Extract odds from line format like "+150 | -165"
            import re
            odds_match = re.findall(r'([+-]\d+)', str(line))
            if not odds_match:
                return 0.5
            
            odds = int(odds_match[0])  # Take first odds (away team)
            
            if odds > 0:
                return 100 / (odds + 100)
            else:
                return abs(odds) / (abs(odds) + 100)
        except:
            return 0.5
    
    @staticmethod
    def estimate_team_rating(team_name, week):
        """Estimate team strength rating"""
        # Rough estimates based on general team strength
        strong_teams = ['Chiefs', 'Bills', 'Ravens', '49ers', 'Cowboys', 'Eagles']
        weak_teams = ['Panthers', 'Cardinals', 'Patriots', 'Broncos']
        
        if team_name in strong_teams:
            return 85
        elif team_name in weak_teams:
            return 65
        else:
            return 75  # Average
    
    @staticmethod
    def calculate_expected_margin(away_team, home_team, week):
        """Calculate expected point margin based on team ratings"""
        away_rating = StatisticalAnalyzer.estimate_team_rating(away_team, week)
        home_rating = StatisticalAnalyzer.estimate_team_rating(home_team, week)
        
        # Home field advantage (~3 points)
        home_advantage = 3
        expected_margin = (home_rating + home_advantage) - away_rating
        
        return expected_margin
    
    @staticmethod
    def analyze_line_value(away_team, home_team, spread_line, week):
        """Analyze if the betting line offers value vs. expected margin"""
        factors = []
        score = 0
        
        try:
            # Extract spread value
            import re
            spread_match = re.search(r'([+-]?\d+\.?\d*)', str(spread_line))
            if not spread_match:
                return score, factors
            
            market_spread = float(spread_match.group(1))
            expected_margin = StatisticalAnalyzer.calculate_expected_margin(away_team, home_team, week)
            
            # Compare market line to our expectation
            value_difference = expected_margin - market_spread
            
            if abs(value_difference) >= 3:
                if value_difference > 0:
                    score += 2
                    factors.append(f"Statistical value on home team ({value_difference:+.1f} points)")
                else:
                    score += 2
                    factors.append(f"Statistical value on away team ({abs(value_difference):.1f} points)")
            elif abs(value_difference) >= 1.5:
                score += 1
                factors.append(f"Modest statistical edge ({abs(value_difference):.1f} points)")
                
        except (ValueError, TypeError):
            pass
            
        return score, factors


# ================================================================
# GAME THEORY ANALYZER
# ================================================================

class GameTheoryAnalyzer:
    """Analyze market dynamics and betting psychology"""
    
    @staticmethod
    def analyze_market_efficiency(sharp_edge, public_pct):
        """Analyze how efficiently the market is pricing this game"""
        factors = []
        score = 0
        
        # Large sharp edges suggest market inefficiency
        if abs(sharp_edge) >= 10:
            score += 2
            factors.append(f"Market inefficiency detected ({sharp_edge:+.1f}% sharp edge)")
        elif abs(sharp_edge) >= 5:
            score += 1
            factors.append(f"Market mispricing possible ({sharp_edge:+.1f}% edge)")
        
        # Extreme public betting percentages
        if public_pct >= 80 or public_pct <= 20:
            score += 1
            factors.append(f"Extreme public sentiment ({public_pct:.0f}% on one side)")
        
        return score, factors
    
    @staticmethod
    def detect_steam_moves(sharp_edge, public_pct):
        """Detect potential steam move scenarios"""
        factors = []
        score = 0
        
        # Steam move: Sharp money against public sentiment
        if sharp_edge > 8 and public_pct > 65:
            score += 3
            factors.append("STEAM MOVE: Sharps heavily against public")
        elif sharp_edge < -8 and public_pct < 35:
            score += 3
            factors.append("STEAM MOVE: Sharps heavily against public")
        elif abs(sharp_edge) >= 5 and ((sharp_edge > 0 and public_pct > 60) or (sharp_edge < 0 and public_pct < 40)):
            score += 2
            factors.append("Potential steam move developing")
            
        return score, factors
    
    @staticmethod
    def analyze_contrarian_value(public_pct, prime_time, team_popularity):
        """Identify contrarian betting opportunities"""
        factors = []
        score = 0
        
        # High public percentage + popular team = contrarian opportunity
        if public_pct >= 70:
            score += 1
            factors.append("High contrarian value (fade the public)")
            
            if prime_time:
                score += 1
                factors.append("Primetime public overreaction")
                
            if team_popularity == "high":
                score += 1
                factors.append("Popular team getting overbet")
        
        # Low public percentage on popular team = potential value
        elif public_pct <= 30 and team_popularity == "high":
            score += 1
            factors.append("Popular team getting underbet")
            
        return score, factors
    
    @staticmethod
    def analyze(game_data):
        """Main game theory analysis"""
        sharp_edge = game_data.get('sharp_analysis', {}).get('spread', {}).get('differential', 0)
        public_pct = game_data.get('public_exposure', 50)
        away_team = game_data.get('away', '')
        home_team = game_data.get('home', '')
        
        # Determine team popularity
        popular_teams = ['Cowboys', 'Packers', 'Steelers', 'Patriots', 'Chiefs']
        team_popularity = "high" if away_team in popular_teams or home_team in popular_teams else "normal"
        
        # Check if primetime
        game_time = str(game_data.get('game_time', '')).lower()
        prime_time = any(indicator in game_time for indicator in ['8:', '9:', 'pm', 'snf', 'mnf', 'tnf'])
        
        total_score = 0
        all_factors = []
        
        # Market efficiency analysis
        efficiency_score, efficiency_factors = GameTheoryAnalyzer.analyze_market_efficiency(sharp_edge, public_pct)
        total_score += efficiency_score
        all_factors.extend(efficiency_factors)
        
        # Steam move detection
        steam_score, steam_factors = GameTheoryAnalyzer.detect_steam_moves(sharp_edge, public_pct)
        total_score += steam_score
        all_factors.extend(steam_factors)
        
        # Contrarian value
        contrarian_score, contrarian_factors = GameTheoryAnalyzer.analyze_contrarian_value(public_pct, prime_time, team_popularity)
        total_score += contrarian_score
        all_factors.extend(contrarian_factors)
        
        return {
            'score': total_score,
            'factors': all_factors,
            'description': ', '.join(all_factors) if all_factors else 'Standard market dynamics'
        }

# ================================================================
# SCHEDULE ANALYZER CLASS (Ensure these parameter names match your call)
# ================================================================

class ScheduleAnalyzer:
    """Analyzes non-standard rest, international hangover, and travel fatigue."""

    # Penalty constants (Negative score favors the opponent)
    REST_ADVANTAGE_SCORE = 1.5      
    MAJOR_REST_ADVANTAGE_SCORE = 3.0 
    W2E_TRAVEL_PENALTY = -2.0       
    INTERNATIONAL_HANGOVER_PENALTY = -4.0 

    @staticmethod
    def is_significant_travel(team_tla: str, opponent_tla: str):
        """Checks for major time zone travel (W2E or E2W) for the current week's travel."""
        # **NOTE:** This method uses the TLA (three-letter acronym) because the 
        # TEAM_TIME_ZONES constant uses them.
        from_zone = TEAM_TIME_ZONES.get(team_tla)
        to_zone = TEAM_TIME_ZONES.get(opponent_tla)

        if not from_zone or not to_zone or from_zone == to_zone:
            return False

        # PST (West) to EST (East) is a 3-hour difference and a major factor
        if from_zone == 'PST' and to_zone == 'EST':
            return True
        
        # EST (East) to PST (West) is also a significant disruption
        if from_zone == 'EST' and to_zone == 'PST':
            return True
        
        return False

    @staticmethod
    # 🚨 CRITICAL CHANGE: Parameters must be named exactly 'away_team' and 'home_team'
    def analyze(away_team: str, home_team: str, away_rest_days: int, home_rest_days: int, current_week: int):
        """Calculates a schedule score based on rest, hangover, and travel."""
        
        # We need the TLA for the TIME_ZONES lookup, assuming the calling function
        # passes the full team names (e.g., 'Bills', 'Texans')
        # NOTE: This requires a reverse lookup if your calling function passes full names.
        # If your calling function passes TLAs ('BUF', 'HOU'), you can skip the lookup.
        # Assuming the calling function passes TLAs for simplicity for now.
        
        # If your calling function passes TLAs (like 'BUF', 'HOU'):
        away_tla = away_team
        home_tla = home_team
        
        # If your calling function passes Full Names (like 'Bills', 'Texans'), 
        # you need a reverse map here, or adjust the calling function.
        
        score = 0
        factors = []
        
        # 1. REST DAY DISPARITY (Core Logic)
        rest_diff = away_rest_days - home_rest_days # Positive diff means AWAY has more rest

        # Apply rest advantage/disadvantage
        if rest_diff >= 3: 
            score += ScheduleAnalyzer.REST_ADVANTAGE_SCORE
            factors.append(f"{away_team} has +{rest_diff} rest advantage (Short week for {home_team})")
        elif rest_diff <= -3: 
            score -= ScheduleAnalyzer.REST_ADVANTAGE_SCORE
            factors.append(f"{home_team} has {-rest_diff} rest advantage (Short week for {away_team})")
        
        # Apply mini-bye advantage (10+ days rest)
        if away_rest_days >= 10 and home_rest_days < 10: 
            score += ScheduleAnalyzer.MAJOR_REST_ADVANTAGE_SCORE
            factors.append(f"{away_team} coming off a mini-bye ({away_rest_days} days rest)")
        elif home_rest_days >= 10 and away_rest_days < 10: 
            score -= ScheduleAnalyzer.MAJOR_REST_ADVANTAGE_SCORE
            factors.append(f"{home_team} coming off a mini-bye ({home_rest_days} days rest)")

        # 2. INTERNATIONAL HANGOVER (Strongest Situational Penalty)
        teams_returning = INTERNATIONAL_HANGOVER_WEEKS.get(current_week, [])
        
        if away_tla in teams_returning:
            score += ScheduleAnalyzer.INTERNATIONAL_HANGOVER_PENALTY 
            factors.append(f"International Hangover penalty for {away_team}")
        
        if home_tla in teams_returning:
            score -= ScheduleAnalyzer.INTERNATIONAL_HANGOVER_PENALTY 
            factors.append(f"International Hangover penalty for {home_team}")

        # 3. SIGNIFICANT TIME ZONE TRAVEL FATIGUE (Current Week Travel)
        
        # West-to-East (W2E) penalty
        if ScheduleAnalyzer.is_significant_travel(away_tla, home_tla) and away_tla in ['SF', 'LAR', 'SEA', 'LV', 'LAC']:
            score += ScheduleAnalyzer.W2E_TRAVEL_PENALTY 
            factors.append(f"{away_team} faces W2E time-zone travel fatigue")
        
        # Final formatting
        final_description = ', '.join(factors) if factors else "No significant scheduling factors"
        
        return {
            'score': round(score, 1),
            'factors': factors,
            'description': final_description,
            'away_rest_days': away_rest_days,
            'home_rest_days': home_rest_days
        }
# ================================================================
# NARRATIVE ENGINE
# ================================================================

class NarrativeEngine:
    """Generates intelligent narratives from analysis"""
    
    @staticmethod
    def generate_sharp_story(sharp_analysis):
        """Create narrative from sharp money analysis"""
        spread = sharp_analysis['spread']
        total = sharp_analysis['total']
        ml = sharp_analysis['moneyline']
        
        stories = []
        
        # Check consensus
        if (spread['direction'] == 'AWAY' and 
            ml['direction'] == 'AWAY' and 
            abs(spread['differential']) >= 5):
            stories.append("🎯 SHARP CONSENSUS: Full alignment on away team across markets")
        elif (spread['direction'] == 'HOME' and 
              ml['direction'] == 'HOME' and 
              abs(spread['differential']) >= 5):
            stories.append("🎯 SHARP CONSENSUS: Full alignment on home team across markets")
        
        # Divergence patterns
        if spread['direction'] == 'AWAY' and total['direction'] == 'UNDER':
            stories.append("⚠️ DIVERGENCE: Sharps on away team but UNDER - expect low-scoring road win")
        elif spread['direction'] == 'HOME' and total['direction'] == 'UNDER':
            stories.append("⚠️ DIVERGENCE: Sharps on home team but UNDER - expect defensive grind")
        elif spread['direction'] == 'AWAY' and total['direction'] == 'OVER':
            stories.append("📈 DIVERGENCE: Sharps on away team + OVER - expect shootout with road team prevailing")
        
        # Trap game detection
        if abs(spread['differential']) >= 10 and spread['bets_pct'] > 65:
            if spread['differential'] > 0:
                stories.append("🚨 TRAP ALERT: Public hammering home, sharps quietly on away")
            else:
                stories.append("🚨 TRAP ALERT: Public hammering away, sharps quietly on home")
        
        # Strong edges
        if abs(spread['differential']) >= 15:
            stories.append(f"💰 MASSIVE EDGE: {abs(spread['differential']):.1f}% differential on spread")
        
        if abs(total['differential']) >= 15:
            stories.append(f"💰 MASSIVE EDGE: {abs(total['differential']):.1f}% differential on total")
        
        return stories if stories else ["Sharp action relatively balanced across markets"]
    
    @staticmethod
    def generate_game_narrative(game_data):
        """Generate complete game narrative"""
        narrative = []
        
        # Opening context
        matchup = game_data['matchup']
        classification = game_data['classification']
        narrative.append(f"=== {matchup} ===")
        narrative.append(f"Classification: {classification}")
        narrative.append("")
        
        # Sharp story
        narrative.append("SHARP MONEY STORY:")
        for story in game_data['sharp_stories']:
            narrative.append(f"  {story}")
        narrative.append("")
        
        # Referee context
        ref = game_data['referee_analysis']
        narrative.append("REFEREE CONTEXT:")
        narrative.append(f"  {ref['referee']}: {ref['ats_pct']:.1f}% ATS ({ref['ats_tendency']})")
        narrative.append(f"  O/U Trend: {ref['ou_pct']:.1f}% ({ref['ou_tendency']})")
        narrative.append("")
        
        # Environmental factors
        if game_data['weather_analysis']['factors']:
            narrative.append("WEATHER IMPACT:")
            for factor in game_data['weather_analysis']['factors']:
                narrative.append(f"  • {factor}")
            narrative.append("")
        
        # Enhanced Injury Analysis Output
        injury_data = game_data['injury_analysis']
        narrative.append("🏥 INJURY ANALYSIS:")
        narrative.append(f"   Impact: {injury_data['description']}")
        
        # Add injury edge information
        if 'edge' in injury_data and injury_data['edge'] != 'NO EDGE':
            narrative.append(f"   Edge: {injury_data['edge']} ({injury_data.get('net_impact', 0):+.1f} points)")
        
        # Add betting recommendations if available
        if injury_data.get('factors'):
            narrative.append(f"   Betting Impact: {' | '.join(injury_data['factors'][:2])}")
        
        # Add team-by-team breakdown if available
        if 'away_impact' in injury_data and 'home_impact' in injury_data:
            if injury_data['away_impact'] or injury_data['home_impact']:
                away_team = game_data['away']
                home_team = game_data['home'] 
                narrative.append(f"   Team Impacts: {away_team} ({injury_data['away_impact']:.1f}) vs {home_team} ({injury_data['home_impact']:.1f})")
       
        # Add prop recommendations if available
        if injury_data.get('prop_recommendations'):
            narrative.append(f"   Prop Opportunities:")
            for prop_rec in injury_data['prop_recommendations'][:3]:  # Top 3
                narrative.append(f"     • {prop_rec}")
       
        # Add specific injury details if available
        if 'away_injuries' in injury_data:
            for inj in injury_data.get('away_injuries', [])[:2]:  # Top 2 away injuries
                if inj.get('impact_points', 0) >= 0.5:
                    narrative.append(f"     • {inj.get('display_name', 'Player')}: {inj.get('analysis', 'Impact analysis')}")
        
        if 'home_injuries' in injury_data:
            for inj in injury_data.get('home_injuries', [])[:2]:  # Top 2 home injuries
                if inj.get('impact_points', 0) >= 0.5:
                    narrative.append(f"     • {inj.get('display_name', 'Player')}: {inj.get('analysis', 'Impact analysis')}")
        
        narrative.append("")
        
        # Situational factors
        if game_data['situational_analysis']['factors']:
            narrative.append("SITUATIONAL FACTORS:")
            for factor in game_data['situational_analysis']['factors']:
                narrative.append(f"  • {factor}")
            narrative.append("")
        
        # Statistical analysis
        if game_data['statistical_analysis']['factors']:
            narrative.append("STATISTICAL EDGE:")
            for factor in game_data['statistical_analysis']['factors']:
                narrative.append(f"  • {factor}")
            narrative.append("")
        
        # Game theory factors
        if game_data['game_theory_analysis']['factors']:
            narrative.append("MARKET DYNAMICS:")
            for factor in game_data['game_theory_analysis']['factors']:
                narrative.append(f"  • {factor}")
            narrative.append("")
        
        # Schedule factors
        if game_data['schedule_analysis']['factors']:
            narrative.append("SCHEDULE ANALYSIS:")
            for factor in game_data['schedule_analysis']['factors']:
                narrative.append(f"  • {factor}")
            narrative.append("")
        
        # Recommendation
        narrative.append("THE VERDICT:")
        narrative.append(f"  Total Score: {game_data['total_score']}")
        narrative.append(f"  Confidence: {game_data['confidence']}")
        narrative.append(f"  Recommendation: {game_data['recommendation']}")
        
        return "\n".join(narrative)


# ================================================================
# ENHANCED CLASSIFICATION ENGINE
# ================================================================

class ClassificationEngine:
    """Classifies games into tiers with enhanced recommendations"""

    @staticmethod
    def classify_game(game_analysis):
        """Determine game classification"""
        total = game_analysis['total_score']
        sharp_score = game_analysis['sharp_consensus_score']
        ref_score = game_analysis['referee_analysis']['ats_score']
        injury_score = game_analysis['injury_analysis']['score']
        
        # Blue Chip: Strong alignment across all factors
        if total >= 8 and sharp_score >= 2 and (ref_score >= 2 or injury_score >= 3):
            return "🔵 BLUE CHIP", "STRONG PLAY", 9
        
        # Targeted Play: Good edge with supporting factors  
        if total >= 5 and (sharp_score >= 1 or injury_score >= 2):
            return "🎯 TARGETED PLAY", "SOLID EDGE", 7
            
        # Lean: Modest edge
        if total >= 3:
            return "📊 LEAN", "SLIGHT EDGE", 5
        
        # Trap Game: Public/sharp divergence
        if sharp_score >= 2 and game_analysis['public_exposure'] >= 65:
            return "🚨 TRAP GAME", "FADE PUBLIC", 4
        
        # Fade: Multiple negative factors
        if total <= -2:
            return "❌ FADE", "AVOID", 2
        
        # Landmine: Mixed signals
        return "⚠️ LANDMINE", "PASS", 3
    
    @staticmethod
    def generate_enhanced_recommendation(classification, game_analysis):
        """Generate specific, actionable betting recommendations with actual lines and teams."""
        
        # Get game details
        away_team = game_analysis.get('away', '')
        home_team = game_analysis.get('home', '')
        
        # Extract line information from sharp analysis
        sharp = game_analysis['sharp_analysis']
        spread_line = sharp.get('spread', {}).get('line', '')
        total_line = sharp.get('total', {}).get('line', '')
        ml_line = sharp.get('moneyline', {}).get('line', '')
        
        spread_dir = sharp['spread']['direction'] 
        total_dir = sharp['total']['direction']
        spread_edge = abs(sharp['spread'].get('differential', 0))
        total_edge = abs(sharp['total'].get('differential', 0))
        
        # Parse spread line to get number
        spread_num = ClassificationEngine.extract_spread_number(spread_line)
        total_num = ClassificationEngine.extract_total_number(total_line)
        
        cat = classification

        # New BLUE CHIP Logic (Prioritizes Highest Edge):
        if "BLUE CHIP" in cat:
            # Determine which play has the absolute strongest edge (Spread or Total)
            if total_edge >= spread_edge and total_edge > 0:
                primary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num)
                secondary_rec = ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num) if spread_edge >= 10 else None
            else:
                primary_rec = ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num)
                secondary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num) if total_edge >= 10 else None
            
            # If a secondary recommendation is not possible, we check if the other play still has a high enough edge
            if not secondary_rec and total_edge >= 10 and primary_rec != ClassificationEngine.generate_total_bet(total_dir, total_num):
                secondary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num)
        
            if secondary_rec:
                return f"✅ STRONG PLAY: {primary_rec} + {secondary_rec}"
            else:
                return f"✅ STRONG PLAY: {primary_rec}"
                
        elif "TARGETED PLAY" in cat:
            # Targeted plays get the strongest single recommendation
            if spread_edge >= total_edge:
                return f"🎯 TARGETED PLAY: {ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num)}"
            else:
                return f"🎯 TARGETED PLAY: {ClassificationEngine.generate_total_bet(total_dir, total_num)}"
                
        elif "LEAN" in cat:
            return f"👀 LEAN: {ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num)} (proceed with caution)"
            
        elif "TRAP" in cat:
            # For trap games, recommend fading the public
            public_side = "home" if game_analysis.get('public_exposure', 50) > 50 else "away"
            fade_side = "away" if public_side == "home" else "home"
            fade_rec = ClassificationEngine.generate_primary_bet(fade_side.upper(), away_team, home_team, spread_num)
            return f"🚨 TRAP GAME: {fade_rec} (fade the public)"
            
        elif "FADE" in cat:
            return "❌ AVOID: Multiple negative factors align"
        else:
            return "⚠️ PASS: Mixed signals, no clear edge identified"
    
    @staticmethod
    def generate_primary_bet(direction, away_team, home_team, spread_num):
        """Generate specific spread bet recommendation with actual lines."""
        if direction == 'AWAY':
            if spread_num:
                return f"{away_team} {spread_num}"
            else:
                return f"{away_team} +X (check current line)"
        elif direction == 'HOME': 
            if spread_num:
                # Convert to home team spread
                home_spread = ClassificationEngine.flip_spread(spread_num)
                return f"{home_team} {home_spread}"
            else:
                return f"{home_team} -X (check current line)"
        else:
            return f"No clear spread edge"
    
    @staticmethod
    def generate_total_bet(direction, total_num):
        """Generate specific total bet recommendation with actual lines."""
        if direction == 'OVER':
            if total_num:
                return f"OVER {total_num}"
            else:
                return "OVER X.5 (check current total)"
        elif direction == 'UNDER':
            if total_num:
                return f"UNDER {total_num}"
            else:
                return "UNDER X.5 (check current total)"
        else:
            return "No clear total edge"
    
    @staticmethod
    def extract_spread_number(line_str):
        """Extract spread number from line string like 'KC -5.5 | DEN +5.5' or 'SEA +3 | LAR -3'."""
        if not line_str:
            return None
        
        import re
        # Look for pattern like "-5.5" or "+5.5" 
        # Try to get the away team line first (should be positive if they're underdogs)
        matches = re.findall(r'([+-]?\d+\.?\d*)', str(line_str))
        if matches:
            # Return the first spread value found
            return matches[0] if matches[0].startswith(('+', '-')) else '+' + matches[0]
        return None
    
    @staticmethod
    def extract_total_number(line_str):
        """Extract total number from line string like 'O45.5 | U45.5' or '45.5'."""
        if not line_str:
            return None
            
        import re
        # Look for number after O or U, or just a standalone number
        match = re.search(r'[OU]?(\d+\.?\d*)', str(line_str))
        if match:
            return match.group(1)
        return None
    
    @staticmethod
    def flip_spread(spread_str):
        """Convert away spread to home spread. '+5.5' becomes '-5.5'."""
        if not spread_str:
            return spread_str
            
        spread_str = str(spread_str).strip()
        if spread_str.startswith('-'):
            return '+' + spread_str[1:]
        elif spread_str.startswith('+'):
            return '-' + spread_str[1:]
        else:
            return '-' + spread_str

def canonical(team_raw: str) -> str:
    if not team_raw:
        return ""

    t = team_raw.strip().lower()

    # Already TLA
    if t.upper() in TEAM_MAP:
        return t.upper()

    # Exact full-name match
    if t in FULL_NAME_TO_TLA:
        return FULL_NAME_TO_TLA[t]

    # Partial match
    for tla, fullname in TEAM_MAP.items():
        lf = fullname.lower()
        if t == lf or t in lf or lf in t:
            return tla

    # Last-chance uppercase
    return t.upper()

def normalize_matchup(s: str) -> str:
    if not s:
        return ""

    s = s.lower().replace(" vs ", "@").replace(" at ", "@").replace(" ", "")
    parts = s.split("@")

    if len(parts) != 2:
        return s

    return f"{canonical(parts[0])}@{canonical(parts[1])}"




# ================================================================
# SINGLE GAME ANALYSIS (REFRACTORED FOR PARALLELISM)
# ================================================================
def analyze_single_game(row, week, action, action_injuries, rotowire, sdql):
    # Add sdql parameter
    """
    Core deterministic single-game analysis.
    Input row → output dict
    """

    # ======================================================
    # STEP 0 — RAW INPUT
    # ======================================================
    away_raw = getattr(row, 'away', '').strip()
    home_raw = getattr(row, 'home', '').strip()
    matchup_raw = getattr(row, 'matchup', '').strip()

    # ======================================================
    # STEP 1 — CANONICAL TEAMS
    # ======================================================
    away_tla = canonical(away_raw)
    home_tla = canonical(home_raw)

    away_full = TEAM_MAP.get(away_tla, away_tla)
    home_full = TEAM_MAP.get(home_tla, home_tla)

    # stable matchup key (NO lowercase, NO spaces)
    matchup_key = f"{away_tla}@{home_tla}"

    # ======================================================
    # STEP 2 — ACTION MATCHING (CANONICAL, STABLE)
    # ======================================================
    normalized_matchup = f"{away_tla}@{home_tla}"
    action_row = None
    
    if not action.empty:
        action_row = action[action['normalized_matchup'] == normalized_matchup]

    # ======================================================
    # STEP 3 — SHARP MONEY
    # ======================================================
    sharp_analysis = {
        'spread': {},
        'total': {},
        'moneyline': {}
    }

    if action_row is not None and not action_row.empty:
        spread_data = action_row[action_row['Market'].str.contains("Spread", case=False)]
        total_data  = action_row[action_row['Market'].str.contains("Total", case=False)]
        ml_data     = action_row[action_row['Market'].str.contains("Money", case=False)]

        sharp_analysis['spread']     = SharpMoneyAnalyzer.analyze_market(spread_data, "Spread")
        sharp_analysis['total']      = SharpMoneyAnalyzer.analyze_market(total_data, "Total")
        sharp_analysis['moneyline']  = SharpMoneyAnalyzer.analyze_market(ml_data, "Moneyline")
    
    # STEP 3.5 — SHARP STORIES (add after sharp analysis)
    sharp_stories = NarrativeEngine.generate_sharp_story(sharp_analysis)

    # ======================================================
    # STEP 4 — WEATHER
    # ======================================================
    if action_row is not None and not action_row.empty:
        weather_raw = action_row.iloc[0].get("Weather", "")
        weather_analysis = WeatherAnalyzer.analyze(weather_raw)
    else:
        weather_analysis = {'score': 0, 'description': 'N/A', 'factors': []}

    # ======================================================
    # STEP 5 — REFEREE
    # ======================================================
    # STEP 5 — REFEREE (FROM SDQL DATA)
    if sdql is not None and not sdql.empty and hasattr(row, 'query'):
        # Match by query field
        ref_row = sdql[sdql['query'] == row.query]
        if not ref_row.empty:
            referee_analysis = RefereeAnalyzer.analyze(ref_row.iloc[0])
            if 'factors' not in referee_analysis:
                referee_analysis['factors'] = []
        else:
            referee_analysis = {
                'ats_score': 0, 'ou_score': 0, 'factors': [], 
                'ats_pct': 50.0, 'ou_pct': 50.0, 
                'referee': 'No SDQL match'
            }
    else:
        referee_analysis = {
            'ats_score': 0, 'ou_score': 0, 'factors': [], 
            'ats_pct': 50.0, 'ou_pct': 50.0, 
            'referee': 'SDQL unavailable'
        }

    # STEP 6 — INJURIES
    try:
        inj = InjuryIntegration.analyze_game_injuries(away_full, home_full, week)
        injury_analysis = {
            'score': inj.get('injury_score', 0),
            'edge': inj.get('injury_edge', 'NO EDGE'),
            'analysis': inj.get('analysis', ''),
            'description': inj.get('analysis', 'No significant injury impacts identified'),
            'factors': inj.get('recommendations', []),
            'away_impact': inj.get('away_injuries', []),
            'home_impact': inj.get('home_injuries', []),
        }
    except Exception as e:
        injury_analysis = {
            'score': 0,
            'edge': 'NO EDGE',
            'analysis': f"injury analyzer fail: {e}",
            'description': f"injury analyzer fail: {e}",
            'factors': [],
        }
    
    # STEP 7 — SITUATIONAL
    situational_analysis = SituationalAnalyzer.analyze({
        'away': away_full,
        'home': home_full,
        'weather_analysis': weather_analysis,
        'spread_line': sharp_analysis['spread'].get('line', ""),
        'public_exposure': sharp_analysis['spread'].get('bets_pct', 50),
    }, week)
    
    # STEP 8 — STATISTICAL
    stat_score, stat_factors = StatisticalAnalyzer.analyze_line_value(
        away_full, home_full, sharp_analysis['spread'].get('line', ""), week
    )
    statistical_analysis = {
        'score': stat_score,
        'factors': stat_factors,
        'description': ', '.join(stat_factors) if stat_factors else 'No stat edge'
    }
    
    # STEP 9 — GAME THEORY
    game_theory_analysis = GameTheoryAnalyzer.analyze({
        'away': away_full,
        'home': home_full,
        'sharp_analysis': sharp_analysis,
        'public_exposure': sharp_analysis['spread'].get('bets_pct', 50),
    })
    
    # STEP 10 — SCHEDULE REST
    schedule_score, schedule_desc = calculate_schedule_score(week, home_tla, away_tla)
    schedule_analysis = {
        'score': schedule_score,
        'factors': [schedule_desc] if schedule_desc != "No significant scheduling factors" else [],
        'description': schedule_desc
    }

    # ======================================================
    # STEP 11 — SCORE
    # ======================================================
    total_score = (
        FACTOR_WEIGHTS['sharp_consensus_score'] * sharp_analysis['spread'].get('score', 0)
        + FACTOR_WEIGHTS['weather_score']      * weather_analysis.get('score', 0)
        + FACTOR_WEIGHTS['referee_ats_score']  * referee_analysis.get('ats_score', 0)
        + FACTOR_WEIGHTS['referee_ou_score']   * referee_analysis.get('ou_score', 0)
        + FACTOR_WEIGHTS['injury_score']       * injury_analysis.get('score', 0)
        + FACTOR_WEIGHTS['situational_score']  * situational_analysis.get('score', 0)
        + FACTOR_WEIGHTS['statistical_score']  * statistical_analysis['score']
        + FACTOR_WEIGHTS['game_theory_score']  * game_theory_analysis.get('score', 0)
        + FACTOR_WEIGHTS['schedule_score']     * schedule_analysis['score']
    )
    
    classification, recommendation_label, tier_score = ClassificationEngine.classify_game({
        'total_score': total_score,
        'sharp_consensus_score': sharp_analysis['spread'].get('score', 0),
        'referee_analysis': referee_analysis,
        'injury_analysis': injury_analysis,
        'public_exposure': sharp_analysis['spread'].get('bets_pct', 50),
    })
    
    recommendation = ClassificationEngine.generate_enhanced_recommendation(
        classification,
        {
            'away': away_full,
            'home': home_full,
            'sharp_analysis': sharp_analysis,
            'injury_analysis': injury_analysis,
            'public_exposure': sharp_analysis['spread'].get('bets_pct', 50)
        }
    )




    return {
        'matchup': f"{away_full} @ {home_full}",
        'matchup_key': matchup_key,
        'away': away_full,
        'home': home_full,
        'away_tla': away_tla,
        'home_tla': home_tla,
        'classification': classification,
        'classification_label': recommendation_label,
        'recommendation': recommendation,
        'tier_score': tier_score,
        'total_score': total_score,
        'confidence': abs(total_score),
        'sharp_analysis': sharp_analysis,
        'weather_analysis': weather_analysis,
        'referee_analysis': referee_analysis,
        'injury_analysis': injury_analysis,
        'situational_analysis': situational_analysis,
        'statistical_analysis': statistical_analysis,
        'game_theory_analysis': game_theory_analysis,
        'schedule_analysis': schedule_analysis,
        'sharp_stories': sharp_stories,
    }

# ================================================================
# MAIN ANALYSIS ENGINE
# ================================================================

def analyze_week(week):
    """Main analysis pipeline"""
    
    print(f"\n{'='*70}")
    print(f"NFL WEEK {week} PROFESSIONAL ANALYSIS ENGINE")
    print(f"{'='*70}\n")
    
    # Load data
    print("📥 Loading data sources...")
    queries = safe_load_csv(f"data/week{week}/week{week}_queries.csv", required=True)
    queries["away_std"] = queries["away"].apply(canonical)
    queries["home_std"] = queries["home"].apply(canonical)
    queries["normalized_matchup"] = queries["matchup"].apply(normalize_matchup)

    sdql = safe_load_csv("data/historical/sdql_results.csv")
    
    if queries.empty:
        print("❌ No games found")
        return
    
    # Load Action Network data
    action_file_path = find_latest("action_all_markets_") 
    action = safe_load_csv(action_file_path) if action_file_path else pd.DataFrame()
    
    # Load Action Network injuries
    action_injuries_path = find_latest("action_injuries_")
    action_injuries = safe_load_csv(action_injuries_path) if action_injuries_path else pd.DataFrame()
    if not action_injuries.empty:
        print(f"  ✓ Loaded {len(action_injuries)} injury records from Action Network")
    else:
        print(f"  ⚠️ No Action Network injury data")
    
    # Set up time tracking
    now = datetime.now(timezone.utc)
    
    # Standardize game time column
    if not action.empty and "Game Time" in action.columns:
        action["game_time"] = action["Game Time"]
    
    # Detect and remove completed games
    final_games = set()
    if not action.empty:
        action["normalized_matchup"] = action["Matchup"].apply(normalize_matchup)
        action["normalized_matchup"] = action["normalized_matchup"].str.strip()
        
        # Better filtering that catches all completed games
        final_games = set(
            action[action["game_time"].astype(str).str.contains("Final", na=False)]["normalized_matchup"]
        )
        
        if final_games:
            print(f"🧹 Detected {len(final_games)} completed games")
            # Remove completed games from Action data
            action = action[~action["normalized_matchup"].isin(final_games)].copy()
    
    # Build kickoff time lookup for time-based filtering
    kickoff_lookup = {}
    if not action.empty:
        for _, row in action.iterrows():
            matchup_key = normalize_matchup(row.get("Matchup", ""))
            kickoff = (
                row.get("Date") or row.get("commence_time") or 
                row.get("start_time") or row.get("EventDateUTC") or 
                row.get("game_time")
            )
            kickoff_lookup[matchup_key] = pd.to_datetime(kickoff, utc=True, errors="coerce")

    # Load supplemental data
    rotowire_file = find_latest("rotowire_lineups_")
    rotowire = safe_load_csv(rotowire_file) if rotowire_file else pd.DataFrame()

    # Prepare rotowire data
    if not rotowire.empty:
        rotowire['home_std'] = rotowire['home'].apply(canonical)
        rotowire['away_std'] = rotowire['away'].apply(canonical)
    
    # Merge base data
    final = queries.merge(sdql, on='query', how='left') if not sdql.empty else queries
    final["normalized_matchup"] = final["matchup"].apply(normalize_matchup)
    
    # Filter out completed games
    before_filter = len(final)
    final = final[~final["normalized_matchup"].isin(final_games)].copy()
    completed_removed = before_filter - len(final)
    
    # Filter out games that have already started
    if kickoff_lookup:
        time_filtered = []
        for _, row in final.iterrows():
            kickoff = kickoff_lookup.get(row.get("normalized_matchup", ""))
            # Keep games with no kickoff time (safer) or future kickoff times
            if kickoff is None or pd.isna(kickoff) or kickoff > now:
                time_filtered.append(True)
            else:
                time_filtered.append(False)
        
        before_time = len(final)
        final = final[time_filtered].copy()
        started_removed = before_time - len(final)
    else:
        started_removed = 0
    
    if completed_removed or started_removed:
        print(f"🧹 Filtered out {completed_removed} completed + {started_removed} started games")

    # Process each game IN PARALLEL
    games = []
    num_games = len(final)
    print(f"\n🔬 Analyzing {num_games} games in parallel...\n")
    
    # Use partial to 'lock in' the arguments that are constant for all games
    analyzer = partial(
        analyze_single_game, 
        week=week, 
        action=action, 
        action_injuries=action_injuries, 
        rotowire=rotowire,
        sdql=sdql
    )

    # Use ThreadPoolExecutor to run the single-game analysis concurrently
    # Max workers set to 8, which is generally efficient for I/O and processing
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Use .itertuples() to efficiently iterate over rows as namedtuples
        # The executor will handle collecting the results from the threads
        game_analyses = executor.map(analyzer, final.itertuples(index=False))
        
        # Collect and print results as they complete
        for game_analysis in game_analyses:
            games.append(game_analysis)
            # Printing inside the loop provides real-time feedback on completion
            print(f"  ✓ {game_analysis['matchup']}: {game_analysis['classification']} (Score: {game_analysis['total_score']:+.1f})")

    # Sort games by tier (UNCHANGED)
    tier_order = {
        '🔵 BLUE CHIP': 1,
        '🎯 TARGETED PLAY': 2,
        '📊 LEAN': 3,
        '🚨 TRAP GAME': 4,
        '⚠️ LANDMINE': 5,
        '❌ FADE': 6
    }
    games.sort(key=lambda x: (tier_order.get(x['classification'], 99), -x['confidence']))
    
    # Generate outputs (UNCHANGED)
    print(f"\n📝 Generating reports...")
    generate_outputs(week, games)
    
    print(f"\n✅ Analysis complete!\n")

    # After generating outputs, log performance tracking (UNCHANGED)
    try:
        from performance_tracker import PerformanceTracker
        tracker = PerformanceTracker()
        tracker.log_week_recommendations(week, f"data/week{week}/week{week}_analytics.json")
        print(f"📊 Performance tracking logged for Week {week}")
    except Exception as e:
        print(f"⚠️ Performance tracking failed: {e}")
       

def generate_outputs(week, games):
    """Generate all output files"""
    
    # Create week directory
    os.makedirs(f"data/week{week}", exist_ok=True)
    
    print(f"📝 Generating reports for {len(games)} games...")
    
    # Executive Summary
    with open(f"data/week{week}/week{week}_executive_summary.txt", "w") as f:
        f.write(f"NFL WEEK {week} - EXECUTIVE SUMMARY\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
        f.write("="*70 + "\n\n")
        
        # Group by tier
        tiers = defaultdict(list)
        for game in games:
            tiers[game['classification']].append(game)
        
        for tier_name in ['🔵 BLUE CHIP', '🎯 TARGETED PLAY', '🚨 TRAP GAME', '❌ FADE']:
            if tier_name in tiers:
                f.write(f"{tier_name}\n")
                f.write("-"*70 + "\n")
                for game in tiers[tier_name]:
                    f.write(f"{game['matchup']}\n")
                    f.write(f"  → {game['recommendation']}\n")
                    if game['sharp_stories']:
                        f.write(f"  → {game['sharp_stories'][0]}\n")
                    f.write("\n")
    
    # Full Analysis
    with open(f"data/week{week}/week{week}_pro_analysis.txt", "w") as f:
        f.write(f"NFL WEEK {week} - PROFESSIONAL ANALYSIS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
        f.write("="*70 + "\n\n")
        
        for game in games:
            f.write(NarrativeEngine.generate_game_narrative(game))
            f.write("\n\n" + "="*70 + "\n\n")
    
    # Analytics CSV
    data_rows = []
    for game in games:
        data_rows.append({
            'matchup': game['matchup'],
            'classification': game['classification'],
            'total_score': game['total_score'],
            'confidence': game['confidence'],
            'sharp_spread_diff': game['sharp_analysis'].get('spread', {}).get('differential', 0),
            'sharp_total_diff': game['sharp_analysis'].get('total', {}).get('differential', 0),
            'ref_ats_pct': game['referee_analysis'].get('ats_pct', 50),
            'ref_ou_pct': game['referee_analysis'].get('ou_pct', 50),
            'weather_score': game['weather_analysis']['score'],
            'injury_score': game['injury_analysis']['score'],
            'injury_edge': game['injury_analysis'].get('edge', 'NO EDGE'),
            'injury_net_impact': game['injury_analysis'].get('net_impact', 0),
            'injury_description': game['injury_analysis']['description'],
            'situational_score': game['situational_analysis']['score'],
            'situational_factors': game['situational_analysis']['description'],
            'statistical_score': game['statistical_analysis']['score'],
            'statistical_edge': game['statistical_analysis']['description'],
            'game_theory_score': game['game_theory_analysis']['score'],
            'market_dynamics': game['game_theory_analysis']['description'],
            'schedule_score': game['schedule_analysis']['score'],
            'schedule_factors': game['schedule_analysis']['description']
        })
    
    pd.DataFrame(data_rows).to_csv(f"data/week{week}/week{week}_analytics.csv", index=False)
    
    # JSON export
    with open(f"data/week{week}/week{week}_analytics.json", "w") as f:
        json.dump(games, f, indent=2, default=str)
    
    print(f"  ✓ week{week}_executive_summary.txt")
    print(f"  ✓ week{week}_pro_analysis.txt")
    print(f"  ✓ week{week}_analytics.csv")
    print(f"  ✓ week{week}_analytics.json")


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    analyze_week(week)
