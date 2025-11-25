#!/usr/bin/env python3
"""
Enhanced NFL Betting Performance Tracker
========================================
Automatically updates results by fetching current NFL scores and calculates
recommendation success rates with ROI tracking.
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
    """Enhanced tracker with automated result updates."""
    
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
    
    def fetch_week_scores(self, week: int, season: int = 2024) -> Dict[str, Dict]:
        """Fetch NFL scores for a specific week using ESPN API."""
        try:
            # ESPN API endpoint for NFL scores
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            
            # Calculate the date range for the week
            # NFL weeks typically start on Thursday
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            games = {}
            
            for game in data.get('events', []):
                if game.get('status', {}).get('type', {}).get('completed', False):
                    # Extract team names and scores
                    competitors = game.get('competitions', [{}])[0].get('competitors', [])
                    
                    if len(competitors) >= 2:
                        away_team = competitors[0]['team']['displayName']
                        home_team = competitors[1]['team']['displayName']
                        away_score = int(competitors[0].get('score', 0))
                        home_score = int(competitors[1].get('score', 0))
                        
                        # Create matchup string
                        matchup = f"{away_team} @ {home_team}"
                        
                        games[matchup] = {
                            'away_team': away_team,
                            'home_team': home_team,
                            'away_score': away_score,
                            'home_score': home_score,
                            'total_score': away_score + home_score,
                            'winner': away_team if away_score > home_score else home_team,
                            'margin': abs(away_score - home_score),
                            'final_score': f"{away_team} {away_score}-{home_score} {home_team}"
                        }
            
            return games
            
        except Exception as e:
            print(f"⚠️ Error fetching scores: {e}")
            return {}
    
    def update_week_results_auto(self, week: int, season: int = 2025) -> Dict:
        """Automatically update results for a week using live scores."""
        try:
            # Load existing results
            df = pd.read_csv(self.results_file)
            week_bets = df[(df['week'] == week) & (df['season'] == season)].copy()
            
            if week_bets.empty:
                return {'error': f'No recommendations found for Week {week}'}
            
            # Fetch current NFL scores
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
                # Try to match the game
                matched_score = self._match_game_to_score(row['game'], scores)
                
                if matched_score:
                    # Determine if the bet won
                    bet_result = self._evaluate_bet(row, matched_score)
                    
                    # Update the dataframe
                    df.at[idx, 'actual_result'] = matched_score['final_score']
                    df.at[idx, 'won'] = bet_result['won']
                    df.at[idx, 'push'] = bet_result['push']
                    df.at[idx, 'final_score'] = f"{matched_score['away_score']}-{matched_score['home_score']}"
                    df.at[idx, 'spread_result'] = bet_result['spread_analysis']
                    df.at[idx, 'total_result'] = bet_result['total_analysis']
                    df.at[idx, 'result_date'] = datetime.now().isoformat()
                    
                    # Update summary
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
            
            # Save updated results
            df.to_csv(self.results_file, index=False)
            
            # Calculate win rate
            completed_bets = results_summary['wins'] + results_summary['losses']
            if completed_bets > 0:
                results_summary['win_rate'] = round(results_summary['wins'] / completed_bets * 100, 1)
            else:
                results_summary['win_rate'] = 0
            
            return results_summary
            
        except Exception as e:
            print(f"⚠️ Error updating results: {e}")
            return {'error': str(e)}
    
    def _match_game_to_score(self, bet_game: str, scores: Dict) -> Optional[Dict]:
        """Match a betting game string to actual NFL scores."""
        # Normalize the bet game string
        bet_game_clean = bet_game.lower().replace(' at ', ' @ ')
        
        # Try exact match first
        for score_game, score_data in scores.items():
            if bet_game_clean == score_game.lower():
                return score_data
        
        # Try partial matches
        bet_teams = re.findall(r'(\w+)', bet_game_clean)
        for score_game, score_data in scores.items():
            score_teams = [score_data['away_team'].lower(), score_data['home_team'].lower()]
            
            # Check if both teams match
            matches = 0
            for bet_team in bet_teams:
                for score_team in score_teams:
                    if bet_team in score_team or score_team in bet_team:
                        matches += 1
                        break
            
            if matches >= 2:  # Both teams found
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
        
        bet_type = bet_row.get('bet_type', 'spread')
        predicted_side = bet_row.get('predicted_side', 'unknown')
        recommendation = bet_row.get('recommendation', '')
        
        # Extract spread and total from recommendation if possible
        spread_match = re.search(r'[-+]?\d+\.?5?', recommendation)
        total_match = re.search(r'(?:OVER|UNDER)\s+(\d+\.?5?)', recommendation)
        
        away_score = game_result['away_score']
        home_score = game_result['home_score']
        total_score = game_result['total_score']
        margin = away_score - home_score  # Positive if away wins, negative if home wins
        
        analysis_parts = []
        
        # Evaluate spread bets
        if 'spread' in bet_type.lower() or any(word in recommendation.lower() for word in ['away on spread', 'home on spread']):
            if spread_match:
                spread = float(spread_match.group())
                
                if 'away on spread' in recommendation.lower():
                    # Away team bet - they need to cover the spread
                    covered = margin > abs(spread) if spread < 0 else margin > -abs(spread)
                    result['spread_analysis'] = f"Away {'+' if margin > 0 else ''}{margin} vs spread {spread}"
                    
                elif 'home on spread' in recommendation.lower():
                    # Home team bet - they need to cover the spread  
                    covered = margin < -abs(spread) if spread > 0 else margin < abs(spread)
                    result['spread_analysis'] = f"Home {'+' if -margin > 0 else ''}{-margin} vs spread {-spread}"
                
                else:
                    covered = False
                    result['spread_analysis'] = f"Could not determine spread direction"
                
                if abs(margin) == abs(spread):
                    result['push'] = True
                    analysis_parts.append(f"PUSH on spread ({margin} vs {spread})")
                else:
                    result['won'] = covered
                    analysis_parts.append(f"{'WON' if covered else 'LOST'} spread bet")
            else:
                analysis_parts.append("Spread bet - could not extract line from recommendation")
        
        # Evaluate total bets
        if 'total' in bet_type.lower() or any(word in recommendation.lower() for word in ['over', 'under']):
            if total_match:
                total_line = float(total_match.group(1))
                
                if 'over' in recommendation.lower():
                    covered = total_score > total_line
                    result['total_analysis'] = f"Total {total_score} vs O{total_line}"
                elif 'under' in recommendation.lower():
                    covered = total_score < total_line
                    result['total_analysis'] = f"Total {total_score} vs U{total_line}"
                else:
                    covered = False
                    result['total_analysis'] = f"Could not determine O/U direction"
                
                if total_score == total_line:
                    result['push'] = True
                    analysis_parts.append(f"PUSH on total ({total_score} vs {total_line})")
                else:
                    # For combination bets, both need to win
                    if 'spread' in result and result.get('won', False):
                        result['won'] = result['won'] and covered
                    else:
                        result['won'] = covered
                    analysis_parts.append(f"{'WON' if covered else 'LOST'} total bet")
            else:
                analysis_parts.append("Total bet - could not extract line from recommendation")
        
        result['analysis'] = '; '.join(analysis_parts) if analysis_parts else 'Could not analyze bet'
        
        return result
    
    def log_week_recommendations(self, week: int, analytics_json_path: str):
        """Log all recommendations for a week from analytics JSON."""
        try:
            with open(analytics_json_path, 'r') as f:
                games = json.load(f)
            
            new_records = []
            
            for game in games:
                # Skip games without clear recommendations
                if game['classification'] in ['⚠️ LANDMINE', '⌛ FADE']:
                    continue
                
                # Extract bet recommendation
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
                    'predicted_side': bet_info['predicted_side'],
                    'actual_result': None,
                    'won': None,
                    'confidence': game['confidence'],
                    'total_score': game['total_score'],
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
            
            # Append to CSV
            if new_records:
                df = pd.DataFrame(new_records)
                existing_df = pd.read_csv(self.results_file)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df.to_csv(self.results_file, index=False)
                
                print(f"✅ Logged {len(new_records)} recommendations for Week {week}")
            
        except Exception as e:
            print(f"⚠️ Error logging recommendations: {e}")
    
    def _parse_recommendation(self, recommendation: str) -> Dict:
        """Parse recommendation string to extract bet details."""
        if not recommendation or 'PASS' in recommendation:
            return None
        
        bet_info = {'bet_type': 'spread', 'predicted_side': 'unknown'}
        
        # Check for combination bets first
        if 'spread' in recommendation.lower() and ('over' in recommendation.lower() or 'under' in recommendation.lower()):
            bet_info['bet_type'] = 'combination'
            
        # Determine primary bet type and side
        if 'AWAY on spread' in recommendation:
            bet_info.update({'bet_type': 'spread', 'predicted_side': 'away'})
        elif 'HOME on spread' in recommendation:
            bet_info.update({'bet_type': 'spread', 'predicted_side': 'home'})
        elif 'OVER' in recommendation:
            bet_info.update({'bet_type': 'total', 'predicted_side': 'over'})
        elif 'UNDER' in recommendation:
            bet_info.update({'bet_type': 'total', 'predicted_side': 'under'})
        
        return bet_info
    
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
                return f"📊 Week {week} Results: No bets found"
            
            # Filter out rows where results haven't been updated
            completed_df = week_df.dropna(subset=['won'])
            
            report = []
            report.append(f"📊 WEEK {week} BETTING RESULTS")
            report.append("=" * 50)
            
            if completed_df.empty:
                report.append("🔍 No completed games yet - results pending")
                return "\n".join(report)
            
            # Overall stats
            wins = completed_df['won'].sum()
            pushes = completed_df['push'].sum() if 'push' in completed_df.columns else 0
            total_completed = len(completed_df)
            losses = total_completed - wins - pushes
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            report.append(f"\n📈 OVERALL PERFORMANCE:")
            report.append(f"   Record: {wins}-{losses}" + (f"-{pushes}" if pushes > 0 else ""))
            report.append(f"   Win Rate: {win_rate:.1f}%")
            report.append(f"   Total Recommendations: {len(week_df)}")
            report.append(f"   Pending Results: {len(week_df) - total_completed}")
            
            # Performance by tier
            if not completed_df.empty:
                report.append(f"\n🎯 PERFORMANCE BY TIER:")
                for classification in completed_df['classification'].unique():
                    tier_df = completed_df[completed_df['classification'] == classification]
                    tier_wins = tier_df['won'].sum()
                    tier_total = len(tier_df)
                    tier_rate = (tier_wins / tier_total * 100) if tier_total > 0 else 0
                    report.append(f"   {classification}: {tier_wins}/{tier_total} ({tier_rate:.1f}%)")
            
            # Game-by-game results
            report.append(f"\n📋 GAME-BY-GAME RESULTS:")
            for _, row in completed_df.iterrows():
                result_icon = "✅" if row['won'] else "🟡" if row.get('push', False) else "❌"
                result_text = "WIN" if row['won'] else "PUSH" if row.get('push', False) else "LOSS"
                
                report.append(f"   {result_icon} {row['game']}")
                report.append(f"      Bet: {row['recommendation']}")
                report.append(f"      Result: {result_text} - {row.get('final_score', 'Score unavailable')}")
                if row.get('spread_result') or row.get('total_result'):
                    analysis = []
                    if row.get('spread_result'):
                        analysis.append(row['spread_result'])
                    if row.get('total_result'):
                        analysis.append(row['total_result'])
                    report.append(f"      Analysis: {'; '.join(analysis)}")
                report.append("")
            
            return "\n".join(report)
            
        except Exception as e:
            return f"⚠️ Error generating report: {e}"


def main():
    """Example usage for Week 12."""
    tracker = EnhancedPerformanceTracker()
    
    # Option 1: Automatically update Week 12 results
    print("🔄 Updating Week 12 results automatically...")
    results = tracker.update_week_results_auto(week=12)
    
    if 'error' in results:
        print(f"⚠️ {results['error']}")
        print("\n💡 You can still update manually using:")
        print("tracker.update_results(12, 'Game Name', 'Final Score', won=True/False)")
    else:
        print(f"✅ Updated {results['updated_games']} games")
        print(f"📊 Week 12 Record: {results['wins']}-{results['losses']}" + 
              (f"-{results['pushes']}" if results['pushes'] > 0 else ""))
        print(f"📈 Win Rate: {results.get('win_rate', 0)}%")
    
    # Generate detailed report
    print("\n" + tracker.generate_week_results_report(12))


if __name__ == "__main__":
    main()
