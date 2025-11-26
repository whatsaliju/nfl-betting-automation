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
    
    def __init__(self):
        self.results_file = "data/historical/betting_results.csv"
        self.analysis_file = "data/historical/performance_analysis.json"
        self.ensure_files_exist()
    
    def ensure_files_exist(self):
        """Create tracking files if they don't exist."""
        os.makedirs("data/historical", exist_ok=True)
        
        if not os.path.exists(self.results_file):
            df = pd.DataFrame(columns=[
                'week', 'season', 'game', 'recommendation', 'classification',
                'bet_type', 'predicted_side', 'actual_result', 'won', 'confidence',
                'total_score', 'sharp_score', 'referee_score', 'weather_score',
                'injury_score', 'situational_score', 'line_at_recommendation',
                'closing_line', 'line_movement', 'edge_identified',
                'recommendation_date', 'result_date', 'final_score', 'spread_result',
                'total_result', 'push'
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

        # --- Handle combination bets if bet_type is 'combination' (advanced, but possible) ---
        # If your engine really generates combined bets that must *both* hit,
        # then the logic above needs to be run for both, and result['won'] = spread_won AND total_won.
        # However, for clearer tracking, it's better to separate these into two rows.
        # For now, if bet_type is 'combination', this code will do nothing, and it won't be evaluated.
        # This is okay if you intend to move to separate rows for each component.
        # If you *don't* separate, then you need to duplicate the logic above and
        # combine the 'won' and 'push' results carefully.
        
        result['analysis'] = '; '.join(analysis_parts) if analysis_parts else 'Could not analyze bet'
        
        return result
    
    def log_week_recommendations(self, week: int, analytics_json_path: str):
        """Log all recommendations for a week from analytics JSON - with duplicate checking."""
        try:
            # Check for existing recommendations first
            df = pd.read_csv(self.results_file)
            existing = df[(df['week'] == week) & (df['season'] == 2025)]
            
            if not existing.empty:
                print("📋 Week " + str(week) + " recommendations already logged (" + str(len(existing)) + " games)")
                print("    Skipping duplicate logging to avoid duplicates")
                return
            
            with open(analytics_json_path, 'r') as f:
                games = json.load(f)
            
            new_records = []
            
            for game in games:
                # Skip games without clear recommendations - handle multiple avoid patterns
                classification = game['classification']
                recommendation = game.get('recommendation', '')
                
                # Skip avoid classifications (handle all variations)
                avoid_classifications = [
                    '⚠️ LANDMINE', '\u26a0\ufe0f LANDMINE', 'LANDMINE',
                    '❌ FADE', '\u274c FADE', 'FADE', 
                    '🚨 TRAP GAME', 'TRAP GAME',
                    '⌛ FADE', '\u23f3 FADE',
                    'AVOID'
                ]
                
                if classification in avoid_classifications:
                    continue
                
                # Also skip if recommendation contains avoid words
                if any(word in recommendation.upper() for word in ['PASS:', 'AVOID:', 'FADE', 'TRAP']):
                    continue
                
                rec = game['recommendation']
                bet_info = self._parse_recommendation(rec)
                
                if not bet_info:
                    continue
                
                record = {
                    'week': week,
                    'season': 2025,
                    'game': game['matchup'],
                    'recommendation': rec,
                    'classification': game['classification'],
                    'bet_type': bet_info['bet_type'],
                    'predicted_side': self._determine_predicted_side(rec, game['matchup'], bet_info['predicted_side']),
                    'actual_result': None,
                    'won': None,
                    'confidence': game.get('confidence', 0),
                    'total_score': game.get('total_score', 0),
                    'sharp_score': game.get('sharp_consensus_score', 0),
                    'referee_score': game.get('referee_analysis', {}).get('ats_score', 0),
                    'weather_score': game.get('weather_analysis', {}).get('score', 0),
                    'injury_score': game.get('injury_analysis', {}).get('score', 0),
                    'situational_score': game.get('situational_analysis', {}).get('score', 0),
                    'line_at_recommendation': bet_info.get('line', 'Unknown'),
                    'closing_line': None,
                    'line_movement': None,
                    'edge_identified': self._calculate_edge_strength(game),
                    'recommendation_date': datetime.now().isoformat(),
                    'result_date': None,
                    'final_score': None,
                    'spread_result': None,
                    'total_result': None,
                    'push': None
                }
                
                new_records.append(record)
            
            if new_records:
                df = pd.DataFrame(new_records)
                existing_df = pd.read_csv(self.results_file)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df.to_csv(self.results_file, index=False)
                
                print("✅ Logged " + str(len(new_records)) + " recommendations for Week " + str(week))
            
        except Exception as e:
            print("⚠️ Error logging recommendations: " + str(e))
    
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
            formatted_line = f"{ou_indicator[0].upper()}{line_match}"

            parsed_bets.append({
                'bet_type': 'total',
                'predicted_side': predicted_side,
                'line': formatted_line
            })

        # If no specific bet types were found, it's an unparseable recommendation.
        # This catch-all can be removed if you ensure all recommendations are parsable.
        if not parsed_bets:
            parsed_bets.append({
                'bet_type': 'unknown',
                'predicted_side': 'unknown',
                'line': 'N/A'
            })

        return parsed_bets
    
    def _determine_predicted_side(self, recommendation: str, game_matchup: str, current_side: str) -> str:
        """Determine predicted side (away/home) from team name and game context."""
        # If already properly set, return it
        if current_side in ['away', 'home', 'over', 'under']:
            return current_side
        
        # For team+spread format, determine away/home from game context
        if current_side == 'team_spread':
            spread_match = re.search(r'([A-Za-z\s]+)\s*([-+]?\d+\.?5?)', recommendation)
            if spread_match:
                team_mentioned = spread_match.group(1).strip()
                
                # Handle both 'at' and '@' formats
                if ' @ ' in game_matchup:
                    away_team = game_matchup.split(' @ ')[0]
                    home_team = game_matchup.split(' @ ')[1]
                elif ' at ' in game_matchup:
                    away_team = game_matchup.split(' at ')[0]
                    home_team = game_matchup.split(' at ')[1]
                else:
                    return current_side
                
                # More flexible team name matching
                team_mentioned_words = team_mentioned.lower().split()
                away_team_words = away_team.lower().split()
                home_team_words = home_team.lower().split()
                
                # Check if any word from mentioned team appears in away team
                away_match = any(word in away_team_words for word in team_mentioned_words)
                # Check if any word from mentioned team appears in home team  
                home_match = any(word in home_team_words for word in team_mentioned_words)
                
                if away_match and not home_match:
                    return 'away'
                elif home_match and not away_match:
                    return 'home'
        
        return current_side  # Return original if can't determine
    
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
            
            completed_df = week_df.dropna(subset=['won'])
            
            report = []
            report.append("📊 WEEK " + str(week) + " BETTING RESULTS")
            report.append("=" * 50)
            
            if completed_df.empty:
                report.append("🔍 No completed games yet - results pending")
                return "\n".join(report)
            
            wins = completed_df['won'].sum()
            pushes = completed_df['push'].sum() if 'push' in completed_df.columns else 0
            total_completed = len(completed_df)
            losses = total_completed - wins - pushes
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            report.append("")
            report.append("📈 OVERALL PERFORMANCE:")
            report.append("   Record: " + str(int(wins)) + "-" + str(int(losses)) + ("" if pushes == 0 else "-" + str(int(pushes))))
            report.append("   Win Rate: " + str(round(win_rate, 1)) + "%")
            report.append("   Total Recommendations: " + str(len(week_df)))
            report.append("   Pending Results: " + str(len(week_df) - total_completed))
            
            if not completed_df.empty:
                report.append("")
                report.append("🎯 PERFORMANCE BY TIER:")
                for classification in completed_df['classification'].unique():
                    tier_df = completed_df[completed_df['classification'] == classification]
                    tier_wins = int(tier_df['won'].sum())
                    tier_total = len(tier_df)
                    tier_rate = (tier_wins / tier_total * 100) if tier_total > 0 else 0
                    report.append("   " + str(classification) + ": " + str(tier_wins) + "/" + str(tier_total) + " (" + str(round(tier_rate, 1)) + "%)")
            
            report.append("")
            report.append("📋 GAME-BY-GAME RESULTS:")
            for _, row in completed_df.iterrows():
                result_icon = "✅" if row['won'] else "🟡" if row.get('push', False) else "❌"
                result_text = "WIN" if row['won'] else "PUSH" if row.get('push', False) else "LOSS"
                
                report.append("   " + result_icon + " " + str(row['game']))
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
    
    print("🔄 Updating Week 12 results automatically...")
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
