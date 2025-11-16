#!/usr/bin/env python3
"""
NFL Professional Betting Analysis Engine
==========================================
Synthesizes sharp money, referee trends, weather, injuries, and context
into actionable betting intelligence with narrative analysis.

Outputs:
- week{X}_executive_summary.txt (Top plays only)
- week{X}_pro_analysis.txt (Full narrative breakdowns)
- week{X}_quick_reference.txt (Bullet points)
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


# ================================================================
# UTILITY FUNCTIONS
# ================================================================

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
    # We explicitly search the 'data' subdirectory and return the full path
    directory = 'data'
    # List files in the 'data' directory
    if os.path.exists(directory):
        matches = [f for f in os.listdir(directory) if f.startswith(prefix)]
        
        if matches:
            latest_filename = sorted(matches)[-1]
            # Return the full relative path
            return os.path.join(directory, latest_filename)
            
    return None # Return None if directory doesn't exist or no file is found


# ================================================================
# SHARP MONEY ANALYZER
# ================================================================

class SharpMoneyAnalyzer:
    """Analyzes sharp action across spread/total/moneyline"""
    
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
                'description': 'No data'
            }
        
        row = market_data.iloc[0]
        bets = SharpMoneyAnalyzer.parse_percentage_pair(row['Bets %'])
        money = SharpMoneyAnalyzer.parse_percentage_pair(row['Money %'])
        
        # Use away team (first value) as reference
        diff = SharpMoneyAnalyzer.calculate_differential(money[0], bets[0])
        score = SharpMoneyAnalyzer.score_differential(diff)
        
        # Determine direction
        if market_type == 'Total':
            direction = 'OVER' if diff > 0 else 'UNDER' if diff < 0 else 'NEUTRAL'
        else:
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
# WEATHER ANALYZER
# ================================================================

class WeatherAnalyzer:
    """Analyzes weather impact"""
    
    @staticmethod
    def analyze(weather_str):
        s = str(weather_str).lower().strip()
        
        if not s or s == 'none':
            return {'score': 0, 'factors': [], 'description': 'None'}
        
        if 'dome' in s:
            return {'score': 0, 'factors': ['Dome'], 'description': 'Dome (no impact)'}
        
        score = 0
        factors = []
        
        # Precipitation
        for token in s.split():
            if token.endswith('%'):
                try:
                    precip = int(token.replace('%', ''))
                    if precip >= 70:
                        score -= 2
                        factors.append(f"Heavy precipitation ({precip}%)")
                    elif precip >= 50:
                        score -= 1
                        factors.append(f"Moderate precipitation ({precip}%)")
                except:
                    pass
        
        # Wind
        for token in s.replace(',', ' ').split():
            try:
                mph = float(token)
                if mph >= 20:
                    score -= 2
                    factors.append(f"High wind ({mph} mph)")
                elif mph >= 15:
                    score -= 1
                    factors.append(f"Windy ({mph} mph)")
            except:
                continue
        
        # Temperature
        if '°' in s:
            try:
                temp_str = s.split('°')[0].split()[-1]
                temp = int(temp_str)
                if temp <= 32:
                    score -= 1
                    factors.append(f"Freezing ({temp}°F)")
                elif temp <= 40:
                    factors.append(f"Cold ({temp}°F)")
            except:
                pass
        
        desc = ' + '.join(factors) if factors else 'Minimal impact'
        
        return {
            'score': score,
            'factors': factors,
            'description': desc
        }


# ================================================================
# INJURY ANALYZER
# ================================================================

class InjuryAnalyzer:
    """Analyzes injury impact"""
    
    @staticmethod
    def analyze(injury_str):
        s = str(injury_str).lower().strip()
        
        if not s or s == 'none':
            return {'score': 0, 'factors': [], 'description': 'None'}
        
        score = 0
        factors = []
        
        # Severity
        if any(x in s for x in ['out', 'o', 'ir']):
            score -= 1
            factors.append("Player OUT")
        elif any(x in s for x in ['doubtful', 'd']):
            score -= 1
            factors.append("Player DOUBTFUL")
        elif any(x in s for x in ['questionable', 'q']):
            factors.append("Player QUESTIONABLE")
        
        # Position impact
        if any(x in s for x in ['qb', 'quarterback']):
            score -= 2
            factors.append("QB injury (critical)")
        
        if any(x in s for x in ['wr', 'wide receiver']):
            score -= 1
            factors.append("WR injury")
        
        if any(x in s for x in ['rb', 'running back']):
            score -= 1
            factors.append("RB injury")
        
        if any(x in s for x in ['ol', 'tackle', 'guard', 'center']):
            score -= 1
            factors.append("OL injury")
        
        desc = ', '.join(factors) if factors else 'Minor/None'
        
        return {
            'score': score,
            'factors': factors,
            'description': desc
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
        
        if game_data['injury_analysis']['factors']:
            narrative.append("INJURY CONCERNS:")
            for factor in game_data['injury_analysis']['factors']:
                narrative.append(f"  • {factor}")
            narrative.append("")
        
        # Recommendation
        narrative.append("THE VERDICT:")
        narrative.append(f"  Total Score: {game_data['total_score']}/10")
        narrative.append(f"  Confidence: {game_data['confidence']}")
        narrative.append(f"  Recommendation: {game_data['recommendation']}")
        
        return "\n".join(narrative)


# ================================================================
# CLASSIFICATION ENGINE
# ================================================================

class ClassificationEngine:
    """Classifies games into tiers"""
    
    @staticmethod
    def classify(game_analysis):
        """Determine game classification"""
        total = game_analysis['total_score']
        sharp_score = game_analysis['sharp_consensus_score']
        ref_score = game_analysis['referee_analysis']['ats_score']
        
        # Blue Chip: Strong alignment across all factors
        if total >= 8 and sharp_score >= 2 and ref_score >= 2:
            return "🔵 BLUE CHIP", "STRONG PLAY", 9
        
        # Targeted Play: Good edge with supporting factors
        if total >= 5 and sharp_score >= 1:
            return "🎯 TARGETED PLAY", "SOLID EDGE", 7
        
        # Lean: Modest edge
        if total >= 3:
            return "📊 LEAN", "SLIGHT EDGE", 5
        
        # Trap Game: Public/sharp divergence
        if sharp_score >= 2 and game_analysis['public_exposure'] >= 65:
            return "🚨 TRAP GAME", "FADE PUBLIC", 6
        
        # Fade: Multiple negative factors
        if total <= -2:
            return "❌ FADE", "AVOID", 2
        
        # Landmine: Mixed signals
        return "⚠️ LANDMINE", "PASS", 3
    
    @staticmethod
    def generate_recommendation(classification, game_analysis):
        """Generate specific betting recommendation"""
        cat = classification[0]
        sharp = game_analysis['sharp_analysis']
        
        if "BLUE CHIP" in cat:
            return f"Strong play on {sharp['spread']['direction']} side"
        elif "TARGETED" in cat:
            return f"Good value on {sharp['spread']['direction']}"
        elif "TRAP" in cat:
            return "Fade the public, consider opposite side"
        elif "FADE" in cat:
            return "Avoid this game entirely"
        else:
            return "Wait for better information"


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
    # Normalize query matchups
    sdql = safe_load_csv("data/historical/sdql_results.csv")
    
    # Standardize query game_time
    if "game_time" in queries.columns:
        queries["game_time"] = queries["game_time"].astype(str).str.strip().str.lower()

    
    
    
    # ---------------------------------------------------------------
    # MATCHUP NORMALIZATION (define BEFORE using it)
    # ---------------------------------------------------------------
    def normalize_matchup(s):
        if not s:
            return ""
        s = s.lower().strip()
    
        # unify separators
        s = s.replace(" at ", " @ ")
        s = s.replace(" vs ", " @ ")
        s = s.replace(" vs. ", " @ ")
        s = s.replace("  ", " ")
    
        # split into two teams
        parts = [p.strip() for p in s.split("@")]
        if len(parts) != 2:
            return s
    
        left, right = parts
    
        # convert abbreviations like NE → patriots only if they ARE abbreviations
        left = TEAM_MAP[left.upper()] if left.upper() in TEAM_MAP else left
        right = TEAM_MAP[right.upper()] if right.upper() in TEAM_MAP else right
    
        # final normalized form
        return f"{left.lower()} @ {right.lower()}"

    # ---------------------------------------------------------------
    # LOAD ACTION NETWORK DATA
    # ---------------------------------------------------------------

    # find_latest now returns the full path (e.g., 'data/action_all_markets_...')
    action_file_path = find_latest("action_all_markets_") 

    # CORRECT LINE: Pass the full path directly to safe_load_csv
    action = safe_load_csv(action_file_path) if action_file_path else pd.DataFrame()

    print(f"DIAGNOSTIC: Action file loaded: {action_file_path}")
    print(f"DIAGNOSTIC: Action DF rows: {len(action)}")

    # Standardize Game Time column casing
    if "Game Time" in action.columns:
        action["game_time"] = action["Game Time"]
    elif "game_time" not in action.columns:
        action["game_time"] = ""

    # ---------------------------------------------------------------
    # REMOVE FINAL GAMES COMPLETELY FROM ACTION FEED
    # ---------------------------------------------------------------
    final_games = set()
    if not action.empty:
    
        # Normalize Action matchups
        action["normalized_matchup"] = action["Matchup"].apply(normalize_matchup)

        # --- DIAGNOSTIC PRINT (ONLY KEEPING NECESSARY ONE) ---
        # Check raw game_time column before filtering
        # This will tell us if the raw Action data uses "Final", "FINAL", "Completed", etc.
        print(f"DIAGNOSTIC: Unique game_time values: {action['game_time'].unique()}")
        # ------------------------------------

        # Detect FINAL games
        final_games = set(
            action[action["game_time"]
                    .astype(str)
                    .str.strip()
                    .str.lower() == "final"]["normalized_matchup"]
        )

        print(f"🧹 Detected FINAL games: {final_games}")

        # Remove ALL rows (all markets) for FINAL matchups
        before = len(action)
        action = action[~action["normalized_matchup"].isin(final_games)].copy()
        after = len(action)
        print(f"    → Removed {before - after} FINAL rows from Action data")
        # ------------------------------------

        # Detect FINAL games
        final_games = set(
            action[action["game_time"]
                    .astype(str)
                    .str.strip()
                    .str.lower() == "final"]["normalized_matchup"]
        )
    
        print(f"🧹 Detected FINAL games: {final_games}")
    
        # Remove ALL rows (all markets) for FINAL matchups
        before = len(action)
        action = action[~action["normalized_matchup"].isin(final_games)].copy()
        after = len(action)
        print(f"    → Removed {before - after} FINAL rows from Action data")

    # ---------------------------------------------------------------
    # BUILD KICKOFF LOOKUP (Only for NON-FINAL games)
    # ---------------------------------------------------------------
    kickoff_lookup = {}
    
    if not action.empty:
        for _, row in action.iterrows():
            matchup_key = normalize_matchup(row.get("Matchup", ""))

            kickoff = (
                row.get("Date")
                or row.get("commence_time")
                or row.get("start_time")
                or row.get("EventDateUTC")
                or row.get("game_time")
            )
            kickoff_lookup[matchup_key] = pd.to_datetime(
                kickoff, utc=True, errors="coerce"
            )


    # Load supplemental data (rest of the code is unchanged here)
    
    rotowire_file = find_latest("rotowire_lineups_")
    rotowire = safe_load_csv(f"data/{rotowire_file}") if rotowire_file else pd.DataFrame()
    
    # Load Action Network supplemental data
    an_injuries_file = find_latest("action_injuries_")
    an_injuries = safe_load_csv(f"data/{an_injuries_file}") if an_injuries_file else pd.DataFrame()
    
    an_weather_file = find_latest("action_weather_")
    an_weather = safe_load_csv(f"data/{an_weather_file}") if an_weather_file else pd.DataFrame()
    
    if queries.empty:
        print("❌ No games found")
        return
    
    # Merge base data
    final = queries.merge(sdql, on='query', how='left') if not sdql.empty else queries
    
    # Ensure normalized_matchup exists AFTER merge
    final["normalized_matchup"] = final["matchup"].apply(normalize_matchup)
    
    # ---------------------------------------------------------------
    # 🔥 CORE FILTER 1: REMOVE GAMES MARKED AS 'FINAL'
    # ---------------------------------------------------------------
    # Remove final games based on normalized matchups (from action data)
    before_final_filter = len(final)
    final = final[~final["normalized_matchup"].isin(final_games)].copy()
    after_final_filter = len(final)
    print(f"🧹 Removed {before_final_filter - after_final_filter} FINAL games from analysis list.")


    # ---------------------------------------------------------------
    # 🔥 CORE FILTER 2: REMOVE GAMES WHOSE KICKOFF HAS PASSED
    # ---------------------------------------------------------------
    now = datetime.now(timezone.utc)
    filtered_rows = []
    
    for _, row in final.iterrows():
        matchup_norm = row.get("normalized_matchup", "")
        
        # Get kickoff from the lookup built earlier
        kickoff = kickoff_lookup.get(matchup_norm)

        # If no kickoff found OR kickoff is invalid → keep the game (assume not started)
        if kickoff is None or pd.isna(kickoff):
            filtered_rows.append(True)
            continue
        
        # If kickoff time is in the past → remove it (False)
        # If kickoff time is in the future → keep it (True)
        filtered_rows.append(kickoff > now)
    
    before_started = len(final)
    final = final[filtered_rows].copy()
    after_started = len(final)
    
    print(f"🧹 Removed {before_started - after_started} already-started games (time check).")

    # Normalize rotowire
    if not rotowire.empty:
        rotowire['home_std'] = rotowire['home'].map(TEAM_MAP)
        rotowire['away_std'] = rotowire['away'].map(TEAM_MAP)
        
    
    # Process each game
    games = []
    
    print(f"\n🔬 Analyzing {len(final)} games...\n")
    
    for idx, row in final.iterrows():
        away_full = TEAM_MAP.get(row.get('away', ''), '')
        home_full = TEAM_MAP.get(row.get('home', ''), '')
        
        # Sharp Money Analysis - Initialize with defaults first
        sharp_analysis = {
            'spread': {'differential': 0, 'score': 0, 'direction': 'NEUTRAL', 'bets_pct': 0, 'money_pct': 0, 'line': '', 'description': 'No data'},
            'total': {'differential': 0, 'score': 0, 'direction': 'NEUTRAL', 'bets_pct': 0, 'money_pct': 0, 'line': '', 'description': 'No data'},
            'moneyline': {'differential': 0, 'score': 0, 'direction': 'NEUTRAL', 'bets_pct': 0, 'money_pct': 0, 'line': '', 'description': 'No data'}
        }
        
        if not action.empty:
            for market_name in ['Spread', 'Total', 'Moneyline']:
                market_data = action[
                    action["normalized_matchup"] == row["normalized_matchup"]
                ]
                market_data = market_data[market_data["Market"] == market_name]

                sharp_analysis[market_name.lower()] = SharpMoneyAnalyzer.analyze_market(
                    market_data, market_name
                )      
        
        # Calculate sharp consensus score
        sharp_scores = [v.get('score', 0) for v in sharp_analysis.values()]
        sharp_consensus_score = sum(sharp_scores)
        
        # Referee Analysis
        ref_analysis = RefereeAnalyzer.analyze(row)
        
        # Weather Analysis
        weather_data = ""
        injury_data = ""
        if not rotowire.empty:
            match = rotowire[
                (rotowire['away_std'] == away_full) &
                (rotowire['home_std'] == home_full)
            ]
            if not match.empty:
                weather_data = match.iloc[0].get('weather', '')
                injury_data = match.iloc[0].get('injuries', '')
        
        weather_analysis = WeatherAnalyzer.analyze(weather_data)
        injury_analysis = InjuryAnalyzer.analyze(injury_data)
        
        # Calculate total score
        total_score = (
            sharp_consensus_score +
            ref_analysis['ats_score'] +
            weather_analysis['score'] +
            injury_analysis['score']
        )
        
        # Public exposure (from bets %)
        public_exposure = sharp_analysis.get('spread', {}).get('bets_pct', 50)
        
        # Generate narratives
        sharp_stories = NarrativeEngine.generate_sharp_story(sharp_analysis)
        
        # Build game analysis
        game_analysis = {
            'matchup': row.get('matchup', f"{away_full} @ {home_full}"),
            'away': away_full,
            'home': home_full,
            'game_time': row.get('game_time', ''),
            'sharp_analysis': sharp_analysis,
            'sharp_consensus_score': sharp_consensus_score,
            'referee_analysis': ref_analysis,
            'weather_analysis': weather_analysis,
            'injury_analysis': injury_analysis,
            'total_score': total_score,
            'public_exposure': public_exposure,
            'sharp_stories': sharp_stories
        }
        
        # Classification
        classification, recommendation, confidence = ClassificationEngine.classify(game_analysis)
        game_analysis['classification'] = classification
        game_analysis['recommendation'] = ClassificationEngine.generate_recommendation(
            classification, game_analysis
        )
        game_analysis['confidence'] = confidence
        
        games.append(game_analysis)
        
        print(f"  ✓ {game_analysis['matchup']}: {classification}")
    
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


def generate_outputs(week, games):
    """Generate all output files"""
    
    # Executive Summary
    with open(f"week{week}_executive_summary.txt", "w") as f:
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
    with open(f"week{week}_pro_analysis.txt", "w") as f:
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
            'injury_score': game['injury_analysis']['score']
        })
    
    pd.DataFrame(data_rows).to_csv(f"week{week}_analytics.csv", index=False)
    
    # JSON export
    with open(f"week{week}_analytics.json", "w") as f:
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
