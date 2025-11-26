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
    "DAL": "Cowboys", "LV": "Raiders"
}

# --- DATA CONSTANT: SCHEDULE REST DATA ---
# This dictionary holds the rest days for all teams entering each week of the 2025 NFL season.
# NEW FORMAT: {Week: {Team_TLA: Rest_Days}}
# This format allows the calculate_schedule_score function to look up rest days directly by TLA.
# ================================================================

SCHEDULE_REST_DATA_2025 = {
    'W1': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W2': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 9, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 9, 'JAX': 7, 'KC': 8, 
        'LAC': 8, 'LAR': 7, 'LV': 9, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W3': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 14, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 14, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W4': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W5': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W6': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W7': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W8': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W9': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W10': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W11': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W12': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 18, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 3, 'IND': 14, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 4, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W13': {
        'ARI': 7, 'ATL': 7, 'BAL': 7, 'BUF': 14, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W14': {
        'ARI': 7, 'ATL': 7, 'BAL': 14, 'BUF': 7, 'CAR': 14, 'CHI': 7, 'CIN': 14, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 14, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 14, 
        'LAC': 7, 'LAR': 7, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 14, 'NO': 7, 'NYG': 14, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 14, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W15': {
        'ARI': 7, 'ATL': 3, 'BAL': 7, 'BUF': 7, 'CAR': 14, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 9, 'DEN': 7, 'DET': 9, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 5, 'LAR': 7, 'LV': 7, 'MIA': 8, 'MIN': 7, 'NE': 14, 'NO': 7, 'NYG': 14, 
        'NYJ': 7, 'PHI': 5, 'PIT': 8, 'SEA': 7, 'SF': 14, 'TB': 3, 'TEN': 7, 'WAS': 7
    },
    'W16': {
        'ARI': 7, 'ATL': 9, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 7, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 7, 
        'LAC': 7, 'LAR': 3, 'LV': 7, 'MIA': 5, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 5, 'SEA': 3, 'SF': 7, 'TB': 9, 'TEN': 7, 'WAS': 7
    },
    'W17': {
        'ARI': 7, 'ATL': 8, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 3, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 5, 'JAX': 7, 'KC': 3, 
        'LAC': 7, 'LAR': 11, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 8, 'SF': 5, 'TB': 7, 'TEN': 7, 'WAS': 7
    },
    'W18': {
        'ARI': 7, 'ATL': 5, 'BAL': 7, 'BUF': 7, 'CAR': 7, 'CHI': 7, 'CIN': 7, 'CLE': 7, 
        'DAL': 7, 'DEN': 10, 'DET': 7, 'GB': 7, 'HOU': 7, 'IND': 7, 'JAX': 7, 'KC': 10, 
        'LAC': 7, 'LAR': 5, 'LV': 7, 'MIA': 7, 'MIN': 7, 'NE': 7, 'NO': 7, 'NYG': 7, 
        'NYJ': 7, 'PHI': 7, 'PIT': 7, 'SEA': 7, 'SF': 7, 'TB': 7, 'TEN': 7, 'WAS': 7
    }
}



# ================================================================
# SCHEDULE-SPECIFIC CONSTANTS (Derived from 2025 NFL Schedule)
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
    Calculates a score based on the rest day differential between the two teams.
    A positive score favors the Home team (or punishes the Away team).
    """
    
    # Use the dummy data constant defined above
    rest_data = SCHEDULE_REST_DATA_2025.get(week, {})
    
    # Retrieve rest days, defaulting to 7 if data is missing
    home_rest = rest_data.get(home_tla, 7)
    away_rest = rest_data.get(away_tla, 7)
    
    rest_differential = home_rest - away_rest # Positive means Home team has more rest
    
    score = 0
    description = "Neutral schedule situation (standard rest)."
    
    if rest_differential > 2:
        score = 1
        description = f"Schedule Edge: HOME team ({home_tla}) has a significant rest advantage (+{rest_differential} days)."
    elif rest_differential < -2:
        score = -1
        description = f"Schedule Edge: AWAY team ({away_tla}) has a significant rest advantage (+{abs(rest_differential)} days)."
    elif rest_differential != 0:
        # For minor rest differences (1 or 2 days)
        team_with_rest = home_tla if rest_differential > 0 else away_tla
        score = 0.5 if rest_differential > 0 else -0.5
        description = f"Minor rest advantage for {team_with_rest} ({abs(rest_differential)} days)."

    # If both teams are coming off a bye (10 days) or a TNF game (3 days), the diff is 0, keeping the score 0.

    return score, description
    
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
    def analyze(ref_data):
        ats_pct = float(str(ref_data.get('ats_pct', '50')).replace('%', ''))
        ou_pct = float(str(ref_data.get('ou_pct', '50')).replace('%', ''))
        
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
            'referee': ref_data.get('referee', 'Unknown')
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
                if injury_str and pd.notna(injury_str):
                    # Parse injury string
                    injuries = self.parse_rotowire_injuries(injury_str)
                    for inj in injuries:
                        inj['team'] = row.get('away', '') + ' / ' + row.get('home', '')
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
            player_id = self.match_player(injury['player'], team_name)
            if player_id and player_id in self.players_dict:
                player_data = self.players_dict[player_id]
                impact = self.calculate_player_impact(injury, player_data)
                total_impact += impact
        
        return min(total_impact, 10)  # Cap at 10 points
    
    def match_player(self, player_name, team_name):
        """Match player to whitelist by name and team."""
        if not self.players_dict:
            return None
        
        name_lower = player_name.lower().strip()
        
        # Team abbreviation mapping
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
        
        for player_id, player_data in self.players_dict.items():
            player_whitelist_name = player_data['name'].lower()
            if (name_lower in player_whitelist_name or player_whitelist_name in name_lower):
                if team_abbrev == player_data['team']:
                    return player_id
        
        return None
    
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
            rotowire_file = f"data/rotowire_injuries_week_{week}.csv"
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
    def classify(game_analysis):
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
        
        if "BLUE CHIP" in cat:
            # Strong plays get both spread and total recommendations
            primary_rec = ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num)
            secondary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num) if total_edge >= 10 else None
            
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

    # Prepare rotowire data
    if not rotowire.empty:
        rotowire['home_std'] = rotowire['home'].map(TEAM_MAP)
        rotowire['away_std'] = rotowire['away'].map(TEAM_MAP)
        
    # Process each game
    games = []
    print(f"\n🔬 Analyzing {len(final)} games...\n")
    
    for idx, row in final.iterrows():
        away_full = TEAM_MAP.get(row.get('away', ''), '')
        home_full = TEAM_MAP.get(row.get('home', ''), '')
        
        # Sharp Money Analysis
        sharp_analysis = {
            'spread': {'differential': 0, 'score': 0, 'direction': 'NEUTRAL', 'bets_pct': 0, 'money_pct': 0, 'line': '', 'description': 'No data'},
            'total': {'differential': 0, 'score': 0, 'direction': 'NEUTRAL', 'bets_pct': 0, 'money_pct': 0, 'line': '', 'description': 'No data'},
            'moneyline': {'differential': 0, 'score': 0, 'direction': 'NEUTRAL', 'bets_pct': 0, 'money_pct': 0, 'line': '', 'description': 'No data'}
        }
        
        if not action.empty:
            for market_name in ['Spread', 'Total', 'Moneyline']:
                market_data = action[
                    (action["normalized_matchup"] == row["normalized_matchup"]) &
                    (action["Market"] == market_name)
                ]
                sharp_analysis[market_name.lower()] = SharpMoneyAnalyzer.analyze_market(
                    market_data, market_name
                )      
        
        # Calculate sharp consensus score
        sharp_scores = [v.get('score', 0) for v in sharp_analysis.values()]
        sharp_consensus_score = sum(sharp_scores)
        
        # Referee Analysis
        ref_analysis = RefereeAnalyzer.analyze(row)
        
        # Weather and Injury Analysis
        weather_data = ""
        injury_data_combined = ""
        
        if not rotowire.empty:
            match = rotowire[
                (rotowire['away_std'] == away_full) &
                (rotowire['home_std'] == home_full)
            ]
            if not match.empty:
                weather_data = match.iloc[0].get('weather', '')
                injury_data_combined = match.iloc[0].get('injuries', '')
        
        # Analyze weather
        weather_analysis = WeatherAnalyzer.analyze(weather_data)
        
        # Enhanced Injury Analysis using restored comprehensive system
        try:
            print(f"🔍 Starting enhanced injury analysis for {away_full} @ {home_full}")
            injury_integration = InjuryIntegration.analyze_game_injuries(away_full, home_full, week)
            
            # Convert to expected format for game analysis
            injury_analysis = {
                'score': injury_integration.get('injury_score', 0),
                'factors': injury_integration.get('recommendations', []),
                'description': injury_integration.get('analysis', 'No significant injuries identified'),
                'edge': injury_integration.get('injury_edge', 'NO EDGE'),
                'away_impact': injury_integration.get('away_injuries', []),
                'home_impact': injury_integration.get('home_injuries', []),
                'net_impact': injury_integration.get('injury_score', 0),
                'prop_recommendations': injury_integration.get('recommendations', [])
            }
            print(f"✅ Enhanced injury analysis completed for {away_full} @ {home_full}")
                
        except Exception as e:
            print(f"⚠️ Enhanced injury analysis failed, falling back to basic analysis: {e}")
            
            # Fallback to basic injury analysis
            away_injury_analysis = InjuryAnalyzer.analyze(
                injury_data_combined, team_name=away_full, action_injuries_df=action_injuries
            )
            home_injury_analysis = InjuryAnalyzer.analyze(
                injury_data_combined, team_name=home_full, action_injuries_df=action_injuries
            )
            
            # Calculate impacts from the analysis
            away_impact = abs(away_injury_analysis['score'])
            home_impact = abs(home_injury_analysis['score']) 
            net_impact = home_impact - away_impact
            
            injury_analysis = {
                'score': min(away_impact + home_impact, 15),  # Combined impact, capped at 15
                'factors': away_injury_analysis['factors'] + home_injury_analysis['factors'],
                'description': f"Away: {away_injury_analysis['description']} | Home: {home_injury_analysis['description']}",
                'edge': 'STRONG EDGE' if abs(net_impact) >= 3 else 'MODERATE EDGE' if abs(net_impact) >= 1 else 'NO EDGE',
                'away_impact': away_impact,
                'home_impact': home_impact,
                'net_impact': net_impact
            }
        
        # Situational Analysis
        temp_game_data = {
            'away': away_full,
            'home': home_full,
            'game_time': row.get('game_time', ''),
            'weather_analysis': weather_analysis,
            'public_exposure': sharp_analysis.get('spread', {}).get('bets_pct', 50),
            'spread_line': sharp_analysis.get('spread', {}).get('line', '')
        }
        situational_analysis = SituationalAnalyzer.analyze(temp_game_data, week)
        
        # Statistical Analysis
        stat_score, stat_factors = StatisticalAnalyzer.analyze_line_value(
            away_full, home_full, sharp_analysis.get('spread', {}).get('line', ''), week
        )
        statistical_analysis = {
            'score': stat_score,
            'factors': stat_factors,
            'description': ', '.join(stat_factors) if stat_factors else 'No statistical edge detected'
        }
        
        # Game Theory Analysis
        game_theory_data = {
            'sharp_analysis': sharp_analysis,
            'public_exposure': sharp_analysis.get('spread', {}).get('bets_pct', 50),
            'away': away_full,
            'home': home_full,
            'game_time': row.get('game_time', '')
        }
        game_theory_analysis = GameTheoryAnalyzer.analyze(game_theory_data)
        
        # Schedule Analysis
        # Ensure we have TLAs for the schedule lookup
        away_tla = row.get('away', '')
        home_tla = row.get('home', '')
        
        try:
            # Use the correct function to get the score and full description
            schedule_score, schedule_desc = calculate_schedule_score(
                week, home_tla, away_tla
            )
            
            # Structure the result to match the engine's expected format (including 'factors')
            schedule_analysis = {
                'score': schedule_score,
                'description': schedule_desc, # Full narrative/description
                'factors': [schedule_desc] # The factors list is required by the NarrativeEngine
            }
        except Exception as e:
            # Fallback in case of missing week data
            schedule_analysis = {
                'score': 0,
                'description': f"Schedule analysis failed: {e}",
                'factors': [] # Must include an empty list for compatibility
            }
        
        # Calculate total score
        # NOTE: Verify this sum exactly matches your expected Total Score. (The previous score of 9 vs expected 7 is a bug)
        total_score = (
            sharp_consensus_score +
            ref_analysis['ats_score'] +
            weather_analysis['score'] +
            injury_analysis['score'] +
            situational_analysis['score'] +
            statistical_analysis['score'] +
            game_theory_analysis['score'] +
            schedule_analysis['score']
        )
        
        # Initialize conflict flag for confidence capping
        cap_confidence_total = False

        # --- CRITICAL FIXES: CONFLICT PENALTIES ---
        
        # 1. Spread Conflict Penalty (Statistical vs. Consensus)
        # Penalize if a strong statistical signal (abs score >= 2) opposes the consensus (all other factors).
        statistical_score = statistical_analysis['score']
        
        # Calculate a consensus score *excluding* the statistical score
        consensus_score = total_score - statistical_score
        
        # Check for strong conflict: Statistical score is high (abs >= 2) AND 
        # it opposes the consensus (scores have opposite signs).
        if abs(statistical_score) >= 2 and (statistical_score * consensus_score < 0):
            # Apply a heavy penalty to force a drop in classification
            CONFLICT_PENALTY_SPREAD = -2.0 # reduced from -5.0
            total_score += CONFLICT_PENALTY_SPREAD
            
            # Log the penalty in situational factors for transparency
            conflict_msg = f"🚨 MAJOR SPREAD CONFLICT: Strong stat value ({statistical_score:+.1f}) opposes consensus ({consensus_score:+.1f}). Penalty: {CONFLICT_PENALTY_SPREAD}"
            situational_analysis['factors'].append(conflict_msg)
            situational_analysis['description'] += f" | {conflict_msg}"
            situational_analysis['score'] += CONFLICT_PENALTY_SPREAD # Update the situational score for CSV logging
            
        # 2. Total Conflict Penalty (Sharp Total vs. Referee O/U)
        # Penalize for high-variance total picks that cancel each other out.
        sharp_total_score = sharp_analysis['total']['score']
        ref_ou_score = ref_analysis['ou_score']
        
        # Check for opposing strong total signals (both abs >= 2)
        if (sharp_total_score * ref_ou_score < 0) and (abs(sharp_total_score) >= 2) and (abs(ref_ou_score) >= 2):
            CONFLICT_PENALTY_TOTAL = -3
            total_score += CONFLICT_PENALTY_TOTAL
            
            # Log the penalty in situational factors for transparency
            conflict_msg = f"⚠️ HIGH TOTAL VARIANCE: Sharp Total ({sharp_total_score:+.1f}) conflicts with Referee O/U ({ref_ou_score:+.1f}). Penalty: {CONFLICT_PENALTY_TOTAL}"
            situational_analysis['factors'].append(conflict_msg)
            situational_analysis['description'] += f" | {conflict_msg}"
            situational_analysis['score'] += CONFLICT_PENALTY_TOTAL # Update the situational score for CSV logging
            
            # Set flag to cap confidence heavily later
            cap_confidence_total = True
            
        # --- END: CRITICAL FIXES ---
        
        # Public exposure
        public_exposure = sharp_analysis.get('spread', {}).get('bets_pct', 50)
        
        # Generate narratives
        sharp_stories = NarrativeEngine.generate_sharp_story(sharp_analysis)
        
        # Build game analysis
        game_analysis = {
            'matchup': row.get('matchup', f"{away_full} @ {home_full}"),
            'normalized_matchup': row.get('normalized_matchup'),
            'away': away_full,
            'home': home_full,
            'game_time': row.get('game_time', ''),
            'sharp_analysis': sharp_analysis,
            'sharp_consensus_score': sharp_consensus_score,
            'referee_analysis': ref_analysis,
            'weather_analysis': weather_analysis,
            'injury_analysis': injury_analysis,
            'situational_analysis': situational_analysis,
            'statistical_analysis': statistical_analysis,
            'game_theory_analysis': game_theory_analysis,
            'schedule_analysis': schedule_analysis,
            'total_score': total_score, # This now includes penalties
            'public_exposure': public_exposure,
            'sharp_stories': sharp_stories
        }
        
        # Classification
        classification, recommendation, confidence = ClassificationEngine.classify(game_analysis)
        
        # Apply confidence cap if high total variance was detected (Flaw 2 fix)
        if cap_confidence_total:
            confidence = min(confidence, 4) # Cap at a LEAN/PASS level
            
        game_analysis['classification'] = classification
        game_analysis['recommendation'] = ClassificationEngine.generate_enhanced_recommendation(
            classification, game_analysis
        )
        game_analysis['confidence'] = confidence
        
        games.append(game_analysis)
        print(f"  ✓ {game_analysis['matchup']}: {classification}")
    
    # Sort games by tier
    tier_order = {
        '🔵 BLUE CHIP': 1,
        '🎯 TARGETED PLAY': 2,
        '📊 LEAN': 3,
        '🚨 TRAP GAME': 4,
        '⚠️ LANDMINE': 5,
        '❌ FADE': 6
    }
    games.sort(key=lambda x: (tier_order.get(x['classification'], 99), -x['confidence']))
    
    # Generate outputs
    print(f"\n📝 Generating reports...")
    generate_outputs(week, games)
    
    print(f"\n✅ Analysis complete!\n")

    # After generating outputs, log performance tracking
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
            'ref_ats_pct': game['referee_analysis']['ats_pct'],
            'ref_ou_pct': game['referee_analysis']['ou_pct'],
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
