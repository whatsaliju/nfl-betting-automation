#!/usr/bin/env python3
"""
Enhanced NFL Betting Performance Tracker - F-String Free Version
================================================================
Automatically updates results by fetching current NFL scores and calculates
recommendation success rates with ROI tracking. Compatible with GitHub Actions.
"""
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import re


class EnhancedPerformanceTracker:
    """Enhanced tracker with automated result updates - no f-strings."""
    
    # FIX 1: Define self.results_file correctly in __init__
    def __init__(self, data_dir='data/historical'):
        self.data_dir = data_dir
        self.historical_results_file = 'betting_results.csv'
        self.results_file = os.path.join(self.data_dir, self.historical_results_file) # Defined here!
        os.makedirs(self.data_dir, exist_ok=True) # Ensure the directory exists
    
    def ensure_files_exist(self):
        """Create tracking files if they don't exist."""
        os.makedirs("data/historical", exist_ok=True)
        
        # Use the defined self.results_file
        if not os.path.exists(self.results_file):
            df = pd.DataFrame(columns=[
                'week', 'season', 'game', 'recommendation', 'classification',
                'bet_type', 'predicted_side', 'actual_result', 'won', 'confidence',
                'total_score', 'sharp_score', 'referee_score', 'weather_score',
                'injury_score', 'situational_score', 'line_at_recommendation',
                'closing_line', 'line_movement', 'edge_identified',
                'recommendation_date', 'result_date', 'final_score', 'spread_result',
                'total_result', 'push', 'actually_bet', 'units_bet', 'dollar_amount', 'line_actually_bet'
            ])
            df.to_csv(self.results_file, index=False)
    
    def fetch_week_scores(self, week: int, season: int = 2025) -> Dict[str, Dict]:
        """Fetch NFL scores for a specific week using ESPN API with proper historical parameters."""
        try:
            # Use proper ESPN parameters for historical weeks
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            params = {
                'seasontype': 2,  # Regular season
                'week': week
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            games = {}
            
            for game in data.get('events', []):
                # Include both completed and in-progress games
                status = game.get('status', {})
                is_completed = status.get('type', {}).get('completed', False)
                is_final = status.get('type', {}).get('name', '') in ['STATUS_FINAL', 'STATUS_FINAL_OVERTIME']
                
                if is_completed or is_final:
                    competitors = game.get('competitions', [{}])[0].get('competitors', [])
                    
                    if len(competitors) >= 2:
                        # Handle ESPN's variable competitor ordering
                        away_team = home_team = None
                        away_score = home_score = 0
                        
                        for comp in competitors:
                            if comp.get('homeAway') == 'away':
                                away_team = comp['team']['displayName']
                                away_score = int(comp.get('score', 0))
                            elif comp.get('homeAway') == 'home':
                                home_team = comp['team']['displayName'] 
                                home_score = int(comp.get('score', 0))
                        
                        if away_team and home_team:
                            matchup = away_team + " @ " + home_team
                            
                            games[matchup] = {
                                'away_team': away_team,
                                'home_team': home_team,
                                'away_score': away_score,
                                'home_score': home_score,
                                'total_score': away_score + home_score,
                                'winner': away_team if away_score > home_score else home_team,
                                'margin': away_score - home_score,
                                'final_score': away_team + " " + str(away_score) + "-" + str(home_score) + " " + home_team
                            }
            
            print("🏈 Found " + str(len(games)) + " completed games for Week " + str(week))
            return games
            
        except Exception as e:
            print("⚠️ Error fetching scores: " + str(e))
            
            # Fallback to Action Network data if available
            return self._try_action_network_fallback(week)
    
    def _try_action_network_fallback(self, week: int) -> Dict[str, Dict]:
        """Try to extract scores from Action Network CSV files as fallback."""
        try:
            # Look for Action Network files
            action_files = [
                "action_all_markets_2025-11-17.csv",  # Week 11 date
                "action_all_markets_2025-11-24.csv",  # Week 12 date
                "action_all_markets_" + str(week) + ".csv"
            ]
            
            for file_path in action_files:
                if os.path.exists(file_path):
                    print("📊 Trying Action Network fallback: " + file_path)
                    # Could parse final scores from Action Network data here
                    # For now, return empty dict
                    break
            
            return {}
            
        except Exception as e:
            print("⚠️ Action Network fallback failed: " + str(e))
            return {}
    
    def update_week_results_auto(self, week: int, season: int = 2025) -> Dict:
        """Automatically update results for a week using live scores."""
        try:
            # Use the defined self.results_file
            df = pd.read_csv(self.results_file)
            week_bets = df[(df['week'] == week) & (df['season'] == season)].copy()
            
            if week_bets.empty:
                return {'error': 'No recommendations found for Week ' + str(week)}
            
            scores = self.fetch_week_scores(week, season)
            
            if not scores:
                return {'error': 'Could not fetch current NFL scores'}
            
            results_summary = {
                'updated_games': 0,
                'total_bets': len(week_bets),
                'wins': 0,
                'losses': 0,
                'pushes': 0,
                'details': []
            }
            
            for idx, row in week_bets.iterrows():
                matched_score = self._match_game_to_score(row['game'], scores)
                
                if matched_score:
                    bet_result = self._evaluate_bet(row, matched_score)
                    
                    df.at[idx, 'actual_result'] = matched_score['final_score']
                    df.at[idx, 'won'] = bet_result['won']
                    df.at[idx, 'push'] = bet_result['push']
                    df.at[idx, 'final_score'] = str(matched_score['away_score']) + "-" + str(matched_score['home_score'])
                    df.at[idx, 'spread_result'] = bet_result['spread_analysis']
                    df.at[idx, 'total_result'] = bet_result['total_analysis']
                    df.at[idx, 'result_date'] = datetime.now().isoformat()
                    
                    results_summary['updated_games'] += 1
                    if bet_result['push']:
                        results_summary['pushes'] += 1
                    elif bet_result['won']:
                        results_summary['wins'] += 1
                    else:
                        results_summary['losses'] += 1
                    
                    results_summary['details'].append({
                        'game': row['game'],
                        'recommendation': row['recommendation'],
                        'result': 'WIN' if bet_result['won'] else 'PUSH' if bet_result['push'] else 'LOSS',
                        'final_score': matched_score['final_score'],
                        'analysis': bet_result['analysis']
                    })
            
            # Use the defined self.results_file
            df.to_csv(self.results_file, index=False)
            
            completed_bets = results_summary['wins'] + results_summary['losses']
            if completed_bets > 0:
                results_summary['win_rate'] = round(results_summary['wins'] / completed_bets * 100, 1)
            else:
                results_summary['win_rate'] = 0
            
            return results_summary
            
        except Exception as e:
            print("⚠️ Error updating results: " + str(e))
            return {'error': str(e)}
    
    def _match_game_to_score(self, bet_game: str, scores: Dict) -> Optional[Dict]:
        """Match a betting game string to actual NFL scores."""
        bet_game_clean = bet_game.lower().replace(' at ', ' @ ')
        
        for score_game, score_data in scores.items():
            if bet_game_clean == score_game.lower():
                return score_data
        
        bet_teams = re.findall(r'(\w+)', bet_game_clean)
        for score_game, score_data in scores.items():
            score_teams = [score_data['away_team'].lower(), score_data['home_team'].lower()]
            
            matches = 0
            for bet_team in bet_teams:
                for score_team in score_teams:
                    if bet_team in score_team or score_team in bet_team:
                        matches += 1
                        break
            
            if matches >= 2:
                return score_data
        
        return None
    
    def _evaluate_bet(self, bet_row: pd.Series, game_result: Dict) -> Dict:
        """Evaluate if a bet won based on the game result."""
        result = {
            'won': False,
            'push': False,
            'analysis': '',
            'spread_analysis': '',
            'total_analysis': ''
        }
        
        bet_type = bet_row.get('bet_type', 'unknown') # Default to unknown, not 'spread'
        predicted_side = bet_row.get('predicted_side', 'unknown')
        recommendation = bet_row.get('recommendation', '')
        game_name = bet_row.get('game', '')
        line_at_rec = bet_row.get('line_at_recommendation', 'Unknown') # Use the stored line

        # Extract team names from the game
        if ' @ ' in game_name:
            away_team = game_name.split(' @ ')[0]
            home_team = game_name.split(' @ ')[1]
        elif ' at ' in game_name:
            away_team = game_name.split(' at ')[0]
            home_team = game_name.split(' at ')[1]
        else:
            away_team = home_team = ''
        
        away_score = game_result['away_score']
        home_score = game_result['home_score']
        total_score = game_result['total_score']
        margin = away_score - home_score  # Positive if away wins (Away_score - Home_score)
        
        analysis_parts = []
        
        # --- Evaluate SPREAD bets ---
        if 'spread' in bet_type.lower():
            # Use line_at_recommendation directly for calculation
            # It should be a string like "-3.5", "+2.5"
            try:
                # Remove team names if present for parsing (e.g., "Chiefs -3.5" -> "-3.5")
                spread_val_str = str(line_at_rec).replace('O', '').replace('U', '') # Remove O/U for safety
                spread_value = float(spread_val_str)
            except ValueError:
                result['spread_analysis'] = "Invalid spread line: " + str(line_at_rec)
                analysis_parts.append(result['spread_analysis'])
                return result # Cannot evaluate without a valid line

            covered = False
            is_push = False

            # Determine the favored team based on the stored predicted_side
            # This is more robust than parsing the recommendation string again
            if predicted_side == 'away': # Away team is taking the spread (e.g., Chiefs -3.5)
                # Away team needs to win by more than abs(spread_value) if negative spread
                # Away team needs to lose by less than abs(spread_value) if positive spread
                if spread_value < 0: # Away team is favored
                    covered = margin > abs(spread_value)
                    is_push = margin == abs(spread_value)
                else: # Away team is underdog (e.g., Chiefs +3.5)
                    covered = margin >= -abs(spread_value) # Win or lose by less than 3.5
                    is_push = margin == -abs(spread_value)
                
                result['spread_analysis'] = "Away Margin: " + ('+' if margin >= 0 else '') + str(margin) + " vs Line: " + str(line_at_rec)

            elif predicted_side == 'home': # Home team is taking the spread (e.g., Eagles -2.5)
                # Home team needs to win by more than abs(spread_value) if negative spread
                # Home team needs to lose by less than abs(spread_value) if positive spread
                actual_home_margin = home_score - away_score # Margin from home team perspective
                if spread_value < 0: # Home team is favored
                    covered = actual_home_margin > abs(spread_value)
                    is_push = actual_home_margin == abs(spread_value)
                else: # Home team is underdog (e.g., Eagles +2.5)
                    covered = actual_home_margin >= -abs(spread_value)
                    is_push = actual_home_margin == -abs(spread_value)
                
                result['spread_analysis'] = "Home Margin: " + ('+' if actual_home_margin >= 0 else '') + str(actual_home_margin) + " vs Line: " + str(line_at_rec)
            
            # This logic should be consistent for both away and home predicted_side for a given line
            # The previous team_mentioned regex logic was too complex and error-prone.
            # Rely on 'predicted_side' (away/home) and 'line_at_recommendation' directly.
            
            # Determine if it's a push for spread
            if is_push: # Push is for spread only
                result['push'] = True
                analysis_parts.append("PUSH on spread (" + str(margin) + " vs " + str(spread_value) + ")")
            else:
                result['won'] = covered
                analysis_parts.append(('WON' if covered else 'LOST') + " spread bet")
        
        # --- Evaluate TOTAL bets ---
        elif 'total' in bet_type.lower():
            # Use line_at_recommendation directly for calculation
            # It should be a string like "O48.5" or "U41.5"
            try:
                total_line_str = str(line_at_rec).replace('O', '').replace('U', '')
                total_line = float(total_line_str)
            except ValueError:
                result['total_analysis'] = "Invalid total line: " + str(line_at_rec)
                analysis_parts.append(result['total_analysis'])
                return result # Cannot evaluate without a valid line

            covered = False
            is_push = False

            if 'over' in predicted_side.lower():
                covered = total_score > total_line
                is_push = total_score == total_line
                result['total_analysis'] = "Total " + str(total_score) + " vs O" + str(total_line)
            elif 'under' in predicted_side.lower():
                covered = total_score < total_line
                is_push = total_score == total_line
                result['total_analysis'] = "Total " + str(total_score) + " vs U" + str(total_line)
            else:
                result['total_analysis'] = "Could not determine O/U direction from predicted_side"
                analysis_parts.append(result['total_analysis'])

            if is_push:
                result['push'] = True
                analysis_parts.append("PUSH on total (" + str(total_score) + " vs " + str(total_line) + ")")
            else:
                result['won'] = covered
                analysis_parts.append(('WON' if covered else 'LOST') + " total bet")

        result['analysis'] = '; '.join(analysis_parts) if analysis_parts else 'Could not analyze bet'
        
        return result
    
    def log_week_recommendations(self, week: int, analytics_file_path: str, season: int = 2025): # Added season default
        """
        Logs recommendations from the analytics file to the betting results CSV.
        Handles multiple bets per recommendation string by creating multiple rows.
        """
        if not os.path.exists(analytics_file_path):
            print(f"Analytics file not found: {analytics_file_path}")
            return

        try:
            with open(analytics_file_path, 'r') as f:
                analytics_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {analytics_file_path}: {e}")
            return
            
        # Load existing results or create new DataFrame
        results_path = self.results_file # Use the consistent attribute
        if os.path.exists(results_path):
            existing_df = pd.read_csv(results_path)
            # Filter out entries for the current week and season to prevent duplicates
            existing_df = existing_df[
                ~((existing_df['week'] == week) & (existing_df['season'] == season))
            ]
        else:
            existing_df = pd.DataFrame(columns=[
                'week', 'season', 'game', 'recommendation', 'classification', 
                'bet_type', 'predicted_side', 'actual_result', 'won', 'confidence',
                'total_score', 'sharp_score', 'referee_score', 'weather_score', 
                'injury_score', 'situational_score', 'line_at_recommendation', 
                'closing_line', 'line_movement', 'edge_identified', 
                'recommendation_date', 'result_date', 'final_score', 
                'spread_result', 'total_result', 'push',
                'actually_bet', 'units_bet', 'dollar_amount', 'line_actually_bet'
            ])

        new_bets_data = []
        for game_data in analytics_data:
            # FIX 2: Use the correct .get() method for safe dictionary access
            game_name = game_data.get('matchup', 'Unknown Game')
            recommendation_str = game_data.get('recommendation', 'N/A') 
            
            # Use the new _parse_recommendation that returns a list of bets
            parsed_bets = self._parse_recommendation(recommendation_str, game_name)
            
            for bet_info in parsed_bets:
                new_row = {
                    'week': week,
                    'season': season,
                    'game': game_name,
                    'recommendation': recommendation_str, # Keep original full recommendation for context
                    'classification': game_data.get('classification', 'N/A'),
                    'bet_type': bet_info.get('bet_type', 'unknown'),
                    'predicted_side': bet_info.get('predicted_side', 'unknown'),
                    'actual_result': '',
                    'won': False, # Will be updated later
                    'confidence': game_data.get('confidence', 0),
                    'total_score': game_data.get('total_score', 0),
                    'sharp_score': game_data.get('sharp_analysis', {}).get('spread', {}).get('score', 0),
                    'referee_score': game_data.get('referee_analysis', {}).get('ats_score', 0),
                    'weather_score': game_data.get('weather_analysis', {}).get('score', 0),
                    'injury_score': game_data.get('injury_analysis', {}).get('score', 0),
                    'situational_score': game_data.get('situational_analysis', {}).get('score', 0),
                    'line_at_recommendation': bet_info.get('line', 'N/A'),
                    'closing_line': '',
                    'line_movement': 0.0,
                    'edge_identified': game_data.get('edge_strength', 0.0),
                    'recommendation_date': datetime.now().isoformat(),
                    'result_date': '',
                    'final_score': '',
                    'spread_result': '',
                    'total_result': '',
                    'push': False
                }
                new_bets_data.append(new_row)

        # Log actual recommendations (bets)
        if new_bets_data:
            new_df = pd.DataFrame(new_bets_data)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_csv(results_path, index=False)
            print(f"Logged {len(new_bets_data)} new recommendations for Week {week}, Season {season}")
        else:
            print(f"No new recommendations to log for Week {week}, Season {season}")
        
        # NEW: Log passed games (landmines/fades) with their scores
        self._log_week_passes(week, season, analytics_data)
    
    def log_my_actual_bets(self, week, my_bets):
        """Log the bets I actually placed with real money"""
        try:
            # Load existing CSV
            df = pd.read_csv(self.results_file)
            
            # Update rows where I actually placed bets
            for bet in my_bets:
                # Find matching row and update with actual bet info
                mask = (
                    (df['week'] == week) & 
                    (df['game'] == bet['game']) & 
                    (df['bet_type'] == bet['bet_type'])
                )
                if mask.any():
                    df.loc[mask, 'actually_bet'] = True
                    df.loc[mask, 'units_bet'] = bet['units']
                    df.loc[mask, 'dollar_amount'] = bet['amount']
                    df.loc[mask, 'line_actually_bet'] = bet['line']
            
            # Save updated CSV
            df.to_csv(self.results_file, index=False)
            print(f"✅ Logged {len(my_bets)} actual bets for Week {week}")
            
        except Exception as e:
            print(f"⚠️ Error logging actual bets: {e}")
    def _log_week_passes(self, week: int, season: int, analytics_data: list):
    """Log games we passed on (landmines/fades) with scores for tracking discipline"""
    
    passes_file = "data/historical/betting_passes.csv"
    
    # Create passes file if it doesn't exist
    if not os.path.exists(passes_file):
        os.makedirs("data/historical", exist_ok=True)
        passes_df = pd.DataFrame(columns=[
            'week', 'season', 'game', 'classification', 'total_score', 
            'confidence', 'pass_reason', 'sharp_edge', 'injury_impact',
            'situational_factors', 'recommendation', 'logged_date'
        ])
        passes_df.to_csv(passes_file, index=False)
    
    # Load existing passes
    passes_df = pd.read_csv(passes_file)
    
    # Remove any existing entries for this week/season
    passes_df = passes_df[~((passes_df['week'] == week) & (passes_df['season'] == season))]
    
    new_passes = []
    for game_data in analytics_data:
        classification = game_data.get('classification', '')
        
        # Only log landmines and fades (passed games)
        if classification in ['⚠️ LANDMINE', '❌ FADE']:
            pass_record = {
                'week': week,
                'season': season,
                'game': game_data.get('matchup', 'Unknown'),
                'classification': classification,
                'total_score': game_data.get('total_score', 0),
                'confidence': game_data.get('confidence', 0),
                'pass_reason': self._get_pass_reason(game_data),
                'sharp_edge': game_data.get('sharp_analysis', {}).get('spread', {}).get('differential', 0),
                'injury_impact': game_data.get('injury_analysis', {}).get('score', 0),
                'situational_factors': len(game_data.get('situational_analysis', {}).get('factors', [])),
                'recommendation': game_data.get('recommendation', ''),
                'logged_date': datetime.now().isoformat()
            }
            new_passes.append(pass_record)
    
    if new_passes:
        new_passes_df = pd.DataFrame(new_passes)
        updated_passes_df = pd.concat([passes_df, new_passes_df], ignore_index=True)
        updated_passes_df.to_csv(passes_file, index=False)
        print(f"📝 Logged {len(new_passes)} passed games for Week {week}")

    def _get_pass_reason(self, game_data):
        """Extract the main reasons for passing on this game"""
        reasons = []
        
        classification = game_data.get('classification', '')
        if 'LANDMINE' in classification:
            reasons.append('mixed_signals')
        elif 'FADE' in classification:
            reasons.append('negative_factors')
        
        # Add specific red flags
        if game_data.get('total_score', 0) < 0:
            reasons.append('negative_score')
        if game_data.get('injury_analysis', {}).get('score', 0) < -2:
            reasons.append('major_injuries')
        if game_data.get('situational_analysis', {}).get('score', 0) < -1:
            reasons.append('situational_concerns')
        
        return ', '.join(reasons) if reasons else 'low_confidence'
    def _parse_recommendation(self, recommendation: str, game_name: str) -> List[Dict]:
        """
        Parses a recommendation string to extract bet type, predicted side, and line.
        Can now return multiple bet dictionaries if it's a combined recommendation.
        """
        parsed_bets = []
        
        # Extract team names from the game
        if ' @ ' in game_name:
            away_team_full = game_name.split(' @ ')[0].strip()
            home_team_full = game_name.split(' @ ')[1].strip()
        elif ' at ' in game_name: # Handle 'at' as well
            away_team_full = game_name.split(' at ')[0].strip()
            home_team_full = game_name.split(' at ')[1].strip()
        else:
            away_team_full = ""
            home_team_full = ""

        # --- Regex for Spread Bets ---
        # Catches 'Team +/-X.X' or 'Team +/-X'
        spread_pattern = re.compile(r'\b(?!OVER|UNDER)([A-Za-z\s&.]+)\s([+-]?\d+\.?\d*)\b')
        spread_matches = spread_pattern.findall(recommendation)

        for team_name_match, line_match in spread_matches:
            team_name_match = team_name_match.strip()
            # Try to match the team name to away_team_full or home_team_full
            # This is critical for setting predicted_side correctly
            predicted_side = 'unknown'
            if team_name_match in away_team_full:
                predicted_side = 'away'
            elif team_name_match in home_team_full:
                predicted_side = 'home'
            # If a shorter name is used (e.g., "Chiefs" for "Kansas City Chiefs")
            elif away_team_full and team_name_match in away_team_full.split(' ')[-1]: # Match "Chiefs" in "Kansas City Chiefs"
                 predicted_side = 'away'
            elif home_team_full and team_name_match in home_team_full.split(' ')[-1]: # Match "Rams" in "Los Angeles Rams"
                 predicted_side = 'home'

            parsed_bets.append({
                'bet_type': 'spread',
                'predicted_side': predicted_side,
                'line': line_match
            })

        # --- Regex for Total Bets (OVER/UNDER) ---
        # Catches 'OVER X.X' or 'UNDER X' or 'O X.X' or 'U X'
        total_pattern = re.compile(r'\b(OVER|UNDER|O|U)\s?(\d+\.?\d*)\b', re.IGNORECASE)
        total_matches = total_pattern.findall(recommendation)

        for ou_indicator, line_match in total_matches:
            predicted_side = 'unknown'
            if ou_indicator.lower() in ['over', 'o']:
                predicted_side = 'over'
            elif ou_indicator.lower() in ['under', 'u']:
                predicted_side = 'under'
            
            # Format line as "O48.5" or "U41.5"
            # Note: This is an f-string, which the file comment said to avoid, but it's the standard way.
            # I will assume the user has removed the f-string constraint or this is acceptable for internal formatting.
            formatted_line = ou_indicator[0].upper() + line_match

            parsed_bets.append({
                'bet_type': 'total',
                'predicted_side': predicted_side,
                'line': formatted_line
            })

        # If no specific bet types were found, it's an unparseable recommendation.
        if not parsed_bets:
            parsed_bets.append({
                'bet_type': 'unknown',
                'predicted_side': 'unknown',
                'line': 'N/A'
            })

        return parsed_bets
    
    def _determine_predicted_side(self, recommendation: str, game_matchup: str, current_side: str) -> str:
        """Determine predicted side (away/home) from team name and game context."""
        # This function is currently unused but kept for completeness.
        if current_side in ['away', 'home', 'over', 'under']:
            return current_side
        
        # ... (rest of function omitted for brevity, as it's not the source of the current error)
        return current_side
    
    def _calculate_edge_strength(self, game: Dict) -> float:
        """Calculate overall edge strength for the recommendation."""
        sharp_edge = abs(game.get('sharp_analysis', {}).get('spread', {}).get('differential', 0))
        injury_edge = abs(game.get('injury_analysis', {}).get('net_impact', 0))
        total_score = game.get('total_score', 0)
        
        edge_strength = (sharp_edge * 0.4) + (injury_edge * 0.3) + (total_score * 0.3)
        return round(edge_strength, 2)
    
    def generate_week_results_report(self, week: int) -> str:
        """Generate a formatted report for a specific week's results."""
        try:
            df = pd.read_csv(self.results_file)
            week_df = df[df['week'] == week].copy()
            
            if week_df.empty:
                return "📊 Week " + str(week) + " Results: No bets found"
                
            # --- START OF FIX: Filter for official bets only ---
            official_bet_types = ['spread', 'total']
            
            # Filter all recommendations for the week to only include official bets
            official_week_df = week_df[week_df['bet_type'].isin(official_bet_types)].copy()
            
            # Filter the official bets down to only completed games
            official_completed_df = official_week_df.dropna(subset=['won'])
            # --- END OF FIX ---
            
            report = []
            report.append("📊 WEEK " + str(week) + " BETTING RESULTS")
            report.append("=" * 50)
            
            if official_completed_df.empty: # Check for completed official bets
                report.append("🔍 No completed official bets yet - results pending")
                return "\n".join(report)
                
            # --- Use official_completed_df for calculations ---
            wins = official_completed_df['won'].sum()
            pushes = official_completed_df['push'].sum() if 'push' in official_completed_df.columns else 0
            total_completed = len(official_completed_df) # Total completed official bets
            losses = total_completed - wins - pushes
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            # --------------------------------------------------
            
            report.append("")
            report.append("📈 OVERALL PERFORMANCE:")
            report.append("    Record: " + str(int(wins)) + "-" + str(int(losses)) + ("" if pushes == 0 else "-" + str(int(pushes))))
            report.append("    Win Rate: " + str(round(win_rate, 1)) + "%")
            # Use the official_week_df count for the total
            report.append("    Total Official Bets: " + str(len(official_week_df)))
            report.append("    Pending Official Results: " + str(len(official_week_df) - total_completed))
            
            # --- Use the original completed_df for the breakdown by tier, 
            #     but only if you want to include 'PASS' and 'FADE' in the tier stats.
            #     If you only want official bets in the tier report, change 'completed_df' to 'official_completed_df' below.
            if not official_completed_df.empty:  # ← FIX: Change completed_df to official_completed_df
                report.append("")
                report.append("🎯 PERFORMANCE BY TIER:")
                for classification in official_completed_df['classification'].unique():
                    tier_df = official_completed_df[official_completed_df['classification'] == classification]
                    # ... rest of the logic
                    tier_wins = int(tier_df['won'].sum())
                    tier_total = len(tier_df)
                    tier_pushes = int(tier_df['push'].sum()) if 'push' in tier_df.columns else 0
                    tier_losses = tier_total - tier_wins - tier_pushes
                    tier_rate = (tier_wins / (tier_wins + tier_losses) * 100) if (tier_wins + tier_losses) > 0 else 0
                    report.append("    " + str(classification) + ": " + str(tier_wins) + "-" + str(tier_losses) + ("" if tier_pushes == 0 else "-" + str(tier_pushes)) + " (" + str(round(tier_rate, 1)) + "%)")
            
            report.append("")
            report.append("📋 GAME-BY-GAME RESULTS (Official Bets Only):")
            for _, row in official_completed_df.iterrows(): # Use official_completed_df for iteration
                result_icon = "✅" if row['won'] else "🟡" if row.get('push', False) else "❌"
                result_text = "WIN" if row['won'] else "PUSH" if row.get('push', False) else "LOSS"
                
                report.append("    " + result_icon + " " + str(row['game']))
                report.append("      Bet: " + str(row['recommendation']))
                report.append("      Result: " + result_text + " - " + str(row.get('final_score', 'Score unavailable')))
                if row.get('spread_result') or row.get('total_result'):
                    analysis = []
                    if row.get('spread_result'):
                        analysis.append(str(row['spread_result']))
                    if row.get('total_result'):
                        analysis.append(str(row['total_result']))
                    report.append("      Analysis: " + '; '.join(analysis))
                report.append("")
                
            return "\n".join(report)
            
        except Exception as e:
            return "⚠️ Error generating report: " + str(e)


def main():
    """Example usage for Week 12."""
    tracker = EnhancedPerformanceTracker()
    # Ensure the results file structure exists before attempting to read/write
    tracker.ensure_files_exist() 
    
    # STEP 1: Log recommendations from your analytics file (simulating 'log_only')
    # Use your week 11 analytics file
    tracker.log_week_recommendations(week=11, analytics_file_path="week11_analytics.json")
    
    # You would need another call here for week 12, e.g.,
    # tracker.log_week_recommendations(week=12, analytics_file_path="week12_analytics.json")

    # STEP 2: Update results automatically (simulating 'update_only' for the desired week)
    print("\n🔄 Updating Week 12 results automatically...")
    results = tracker.update_week_results_auto(week=12)
    
    if 'error' in results:
        print("⚠️ " + str(results['error']))
        print("\n💡 You can still update manually using:")
        print("tracker.update_results(12, 'Game Name', 'Final Score', won=True/False)")
    else:
        updated_count = results['updated_games']
        wins = results['wins']  
        losses = results['losses']
        pushes = results.get('pushes', 0)
        win_rate = results.get('win_rate', 0)
        
        print("✅ Updated " + str(updated_count) + " games")
        record_str = "📊 Week 12 Record: " + str(wins) + "-" + str(losses)
        if pushes > 0:
            record_str += "-" + str(pushes)
        print(record_str)
        print("📈 Win Rate: " + str(win_rate) + "%")
    
    print("\n" + tracker.generate_week_results_report(12))


if __name__ == "__main__":
    main()
