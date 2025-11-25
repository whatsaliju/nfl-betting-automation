#!/usr/bin/env python3
"""
Universal Weekly Performance Tracker
====================================
Handle any NFL week - past results, current tracking, future prep.
Usage: python weekly_tracker.py [week_number] [action]
"""

import pandas as pd
import json
import os
import requests
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import re
import sys


class UniversalWeeklyTracker:
    """Universal tracker for any NFL week."""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = base_path
        self.results_file = f"{base_path}/historical/betting_results.csv"
        self.analysis_file = f"{base_path}/historical/performance_analysis.json"
        self.ensure_files_exist()
    
    def ensure_files_exist(self):
        """Create tracking files if they don't exist."""
        os.makedirs(f"{self.base_path}/historical", exist_ok=True)
        
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
    
    def process_week(self, week: int, action: str = "auto", 
                    analytics_file: str = None, season: int = 2024) -> Dict:
        """
        Universal week processor.
        
        Actions:
        - 'log': Log recommendations from analytics JSON
        - 'update': Update results with current scores
        - 'auto': Log recommendations (if needed) + update results
        - 'report': Generate report only
        - 'manual': Show manual update instructions
        """
        
        print(f"🏈 PROCESSING NFL WEEK {week} ({action.upper()})")
        print("=" * 50)
        
        results = {'week': week, 'action': action, 'success': True, 'messages': []}
        
        try:
            if action in ['log', 'auto']:
                log_result = self._log_recommendations(week, analytics_file, season)
                results['log_result'] = log_result
                results['messages'].extend(log_result.get('messages', []))
            
            if action in ['update', 'auto']:
                update_result = self._update_results(week, season)
                results['update_result'] = update_result
                results['messages'].extend(update_result.get('messages', []))
            
            if action in ['report', 'auto'] or action not in ['log', 'update', 'manual']:
                report = self._generate_report(week)
                results['report'] = report
                print(f"\n{report}")
            
            if action == 'manual':
                manual_info = self._show_manual_instructions(week)
                results['manual_instructions'] = manual_info
                print(f"\n{manual_info}")
            
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            print(f"⚠️ Error processing Week {week}: {e}")
        
        return results
    
    def _log_recommendations(self, week: int, analytics_file: str, season: int) -> Dict:
        """Log recommendations from analytics JSON file."""
        result = {'success': True, 'messages': []}
        
        try:
            # Check if already logged
            df = pd.read_csv(self.results_file)
            existing = df[(df['week'] == week) & (df['season'] == season)]
            
            if not existing.empty:
                result['messages'].append(f"📋 Week {week} recommendations already logged ({len(existing)} games)")
                return result
            
            # Find analytics file if not provided
            if not analytics_file:
                possible_files = [
                    f"{self.base_path}/week{week}/week{week}_analytics.json",
                    f"week{week}_analytics.json",
                    f"data/week{week}_analytics.json"
                ]
                
                for file_path in possible_files:
                    if os.path.exists(file_path):
                        analytics_file = file_path
                        break
                
                if not analytics_file:
                    result['messages'].append(f"⚠️ No analytics file found for Week {week}")
                    result['messages'].append(f"   Searched: {possible_files}")
                    return result
            
            # Load and process analytics
            with open(analytics_file, 'r') as f:
                games = json.load(f)
            
            new_records = []
            
            for game in games:
                # Skip games without clear recommendations
                if game['classification'] in ['⚠️ LANDMINE', '⌛ FADE', 'FADE', 'LANDMINE']:
                    continue
                
                rec = game['recommendation']
                bet_info = self._parse_recommendation(rec)
                
                if not bet_info:
                    continue
                
                record = {
                    'week': week,
                    'season': season,
                    'game': game['matchup'],
                    'recommendation': rec,
                    'classification': game['classification'],
                    'bet_type': bet_info['bet_type'],
                    'predicted_side': bet_info['predicted_side'],
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
            
            # Save to CSV
            if new_records:
                new_df = pd.DataFrame(new_records)
                existing_df = pd.read_csv(self.results_file)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_csv(self.results_file, index=False)
                
                result['messages'].append(f"✅ Logged {len(new_records)} recommendations for Week {week}")
                result['logged_count'] = len(new_records)
            else:
                result['messages'].append(f"⚠️ No valid recommendations found in {analytics_file}")
        
        except Exception as e:
            result['success'] = False
            result['messages'].append(f"⚠️ Error logging recommendations: {e}")
        
        return result
    
    def _update_results(self, week: int, season: int) -> Dict:
        """Update results with current NFL scores."""
        result = {'success': True, 'messages': []}
        
        try:
            # Load existing bets
            df = pd.read_csv(self.results_file)
            week_bets = df[(df['week'] == week) & (df['season'] == season)].copy()
            
            if week_bets.empty:
                result['messages'].append(f"⚠️ No recommendations found for Week {week}")
                return result
            
            # Check if already updated
            completed_bets = week_bets.dropna(subset=['won'])
            if len(completed_bets) == len(week_bets):
                result['messages'].append(f"📊 Week {week} results already complete")
                result['wins'] = completed_bets['won'].sum()
                result['losses'] = len(completed_bets) - result['wins']
                result['win_rate'] = result['wins'] / len(completed_bets) * 100 if len(completed_bets) > 0 else 0
                return result
            
            # Fetch NFL scores
            scores = self._fetch_nfl_scores(week, season)
            
            if not scores:
                result['messages'].append(f"⚠️ Could not fetch NFL scores for Week {week}")
                return result
            
            # Update results
            updated_count = 0
            wins = losses = pushes = 0
            
            for idx, row in week_bets.iterrows():
                if pd.notna(row['won']):  # Skip if already updated
                    continue
                
                matched_score = self._match_game_to_score(row['game'], scores)
                
                if matched_score:
                    bet_result = self._evaluate_bet(row, matched_score)
                    
                    # Update dataframe
                    df.at[idx, 'actual_result'] = matched_score['final_score']
                    df.at[idx, 'won'] = bet_result['won']
                    df.at[idx, 'push'] = bet_result['push']
                    df.at[idx, 'final_score'] = f"{matched_score['away_score']}-{matched_score['home_score']}"
                    df.at[idx, 'spread_result'] = bet_result['spread_analysis']
                    df.at[idx, 'total_result'] = bet_result['total_analysis']
                    df.at[idx, 'result_date'] = datetime.now().isoformat()
                    
                    updated_count += 1
                    if bet_result['push']:
                        pushes += 1
                    elif bet_result['won']:
                        wins += 1
                    else:
                        losses += 1
            
            # Save updates
            if updated_count > 0:
                df.to_csv(self.results_file, index=False)
                
                result['messages'].append(f"✅ Updated {updated_count} games")
                result['wins'] = wins
                result['losses'] = losses
                result['pushes'] = pushes
                result['win_rate'] = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
                result['messages'].append(f"📊 Week {week} Record: {wins}-{losses}" + (f"-{pushes}" if pushes > 0 else ""))
                result['messages'].append(f"📈 Win Rate: {result['win_rate']:.1f}%")
            else:
                result['messages'].append(f"📋 No new results to update for Week {week}")
        
        except Exception as e:
            result['success'] = False
            result['messages'].append(f"⚠️ Error updating results: {e}")
        
        return result
    
    def _fetch_nfl_scores(self, week: int, season: int) -> Dict[str, Dict]:
        """Fetch NFL scores - try multiple sources."""
        try:
            # Try ESPN API first
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            games = {}
            
            for game in data.get('events', []):
                # Only include completed games
                if game.get('status', {}).get('type', {}).get('completed', False):
                    competitors = game.get('competitions', [{}])[0].get('competitors', [])
                    
                    if len(competitors) >= 2:
                        # ESPN sometimes orders differently, so find home/away
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
                            matchup = f"{away_team} @ {home_team}"
                            
                            games[matchup] = {
                                'away_team': away_team,
                                'home_team': home_team,
                                'away_score': away_score,
                                'home_score': home_score,
                                'total_score': away_score + home_score,
                                'winner': away_team if away_score > home_score else home_team,
                                'margin': away_score - home_score,
                                'final_score': f"{away_team} {away_score}-{home_score} {home_team}"
                            }
            
            return games
            
        except Exception as e:
            print(f"⚠️ Error fetching scores: {e}")
            return {}
    
    def _match_game_to_score(self, bet_game: str, scores: Dict) -> Optional[Dict]:
        """Match betting game to actual NFL scores with fuzzy matching."""
        bet_game_clean = bet_game.lower().replace(' at ', ' @ ').replace(' vs ', ' @ ')
        
        # Exact match first
        for score_game, score_data in scores.items():
            if bet_game_clean == score_game.lower():
                return score_data
        
        # Team name matching with common abbreviations
        team_mappings = {
            'commanders': ['washington', 'was'],
            'football team': ['washington', 'was'],
            'patriots': ['new england', 'ne'],
            'packers': ['green bay', 'gb'],
            '49ers': ['san francisco', 'sf'],
            'rams': ['los angeles rams', 'la rams'],
            'chargers': ['los angeles chargers', 'la chargers']
        }
        
        # Extract teams from bet game
        bet_teams = re.findall(r'(\w+)', bet_game_clean)
        
        for score_game, score_data in scores.items():
            score_away = score_data['away_team'].lower()
            score_home = score_data['home_team'].lower()
            
            matches = 0
            for bet_team in bet_teams:
                # Direct match
                if bet_team in score_away or bet_team in score_home:
                    matches += 1
                # Check mappings
                else:
                    for canonical, aliases in team_mappings.items():
                        if bet_team == canonical or bet_team in aliases:
                            if any(alias in score_away or alias in score_home for alias in [canonical] + aliases):
                                matches += 1
                                break
            
            if matches >= 2:  # Both teams matched
                return score_data
        
        return None
    
    def _evaluate_bet(self, bet_row: pd.Series, game_result: Dict) -> Dict:
        """Evaluate if a bet won - enhanced version."""
        result = {
            'won': False,
            'push': False,
            'analysis': '',
            'spread_analysis': '',
            'total_analysis': ''
        }
        
        recommendation = bet_row.get('recommendation', '')
        away_score = game_result['away_score']
        home_score = game_result['home_score']
        total_score = game_result['total_score']
        margin = away_score - home_score  # Positive if away wins
        
        analysis_parts = []
        bet_won = None
        
        # Parse spreads and totals from recommendation
        spread_matches = re.findall(r'[-+]?\d+\.?5?', recommendation)
        total_matches = re.findall(r'(?:OVER|UNDER)\s+(\d+\.?5?)', recommendation, re.IGNORECASE)
        
        # Evaluate spread bets
        if any(phrase in recommendation.lower() for phrase in ['away on spread', 'home on spread']):
            if spread_matches:
                spread = float(spread_matches[0])
                
                if 'away on spread' in recommendation.lower():
                    # Away team needs to cover
                    actual_spread = margin  # Away score - Home score
                    needed_margin = -spread if spread < 0 else spread
                    covered = actual_spread > needed_margin
                    
                    result['spread_analysis'] = f"Away {'+' if margin >= 0 else ''}{margin} vs line {spread}"
                    
                elif 'home on spread' in recommendation.lower():
                    # Home team needs to cover
                    actual_spread = -margin  # Home advantage perspective
                    needed_margin = -spread if spread > 0 else abs(spread)
                    covered = actual_spread > needed_margin
                    
                    result['spread_analysis'] = f"Home {'+' if -margin >= 0 else ''}{-margin} vs line {-spread}"
                
                # Check for push
                if abs(margin) == abs(spread):
                    result['push'] = True
                    analysis_parts.append(f"PUSH on spread")
                else:
                    bet_won = covered
                    analysis_parts.append(f"{'WON' if covered else 'LOST'} spread bet")
        
        # Evaluate total bets
        if any(phrase in recommendation.lower() for phrase in ['over', 'under']):
            if total_matches:
                total_line = float(total_matches[0])
                
                if 'over' in recommendation.lower():
                    covered = total_score > total_line
                    result['total_analysis'] = f"Total {total_score} vs O{total_line}"
                elif 'under' in recommendation.lower():
                    covered = total_score < total_line
                    result['total_analysis'] = f"Total {total_score} vs U{total_line}"
                
                # Check for push
                if total_score == total_line:
                    result['push'] = True
                    analysis_parts.append(f"PUSH on total")
                else:
                    # For combination bets, both must win
                    if bet_won is not None:
                        bet_won = bet_won and covered
                    else:
                        bet_won = covered
                    analysis_parts.append(f"{'WON' if covered else 'LOST'} total bet")
        
        result['won'] = bet_won if bet_won is not None else False
        result['analysis'] = '; '.join(analysis_parts) if analysis_parts else 'Could not analyze bet'
        
        return result
    
    def _parse_recommendation(self, recommendation: str) -> Dict:
        """Parse recommendation to extract bet details."""
        if not recommendation or any(word in recommendation.upper() for word in ['PASS', 'FADE', 'AVOID']):
            return None
        
        bet_info = {'bet_type': 'unknown', 'predicted_side': 'unknown'}
        
        rec_lower = recommendation.lower()
        
        # Check for combination bets
        if 'spread' in rec_lower and ('over' in rec_lower or 'under' in rec_lower):
            bet_info['bet_type'] = 'combination'
        elif 'away on spread' in rec_lower or 'home on spread' in rec_lower:
            bet_info['bet_type'] = 'spread'
        elif 'over' in rec_lower or 'under' in rec_lower:
            bet_info['bet_type'] = 'total'
        
        # Determine side
        if 'away on spread' in rec_lower:
            bet_info['predicted_side'] = 'away'
        elif 'home on spread' in rec_lower:
            bet_info['predicted_side'] = 'home'
        elif 'over' in rec_lower:
            bet_info['predicted_side'] = 'over'
        elif 'under' in rec_lower:
            bet_info['predicted_side'] = 'under'
        
        return bet_info
    
    def _calculate_edge_strength(self, game: Dict) -> float:
        """Calculate edge strength from game analysis."""
        try:
            sharp_edge = abs(game.get('sharp_analysis', {}).get('spread', {}).get('differential', 0))
            injury_edge = abs(game.get('injury_analysis', {}).get('net_impact', 0))
            total_score = game.get('total_score', 0)
            
            edge_strength = (sharp_edge * 0.4) + (injury_edge * 0.3) + (total_score * 0.3)
            return round(edge_strength, 2)
        except:
            return 0.0
    
    def _generate_report(self, week: int) -> str:
        """Generate comprehensive week report."""
        try:
            df = pd.read_csv(self.results_file)
            week_df = df[df['week'] == week].copy()
            
            if week_df.empty:
                return f"📊 Week {week} Report: No data found"
            
            completed_df = week_df.dropna(subset=['won'])
            
            report = []
            report.append(f"📊 WEEK {week} PERFORMANCE REPORT")
            report.append("=" * 60)
            
            # Overall stats
            if not completed_df.empty:
                wins = completed_df['won'].sum()
                pushes = completed_df['push'].sum() if 'push' in completed_df.columns else 0
                total_completed = len(completed_df)
                losses = total_completed - wins - pushes
                win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                
                report.append(f"\n📈 OVERALL PERFORMANCE:")
                report.append(f"   Record: {wins}-{losses}" + (f"-{pushes}" if pushes > 0 else ""))
                report.append(f"   Win Rate: {win_rate:.1f}%")
                report.append(f"   Pending: {len(week_df) - total_completed}")
                
                # Performance by classification
                report.append(f"\n🎯 PERFORMANCE BY TIER:")
                for classification in completed_df['classification'].unique():
                    tier_df = completed_df[completed_df['classification'] == classification]
                    tier_wins = tier_df['won'].sum()
                    tier_total = len(tier_df)
                    tier_rate = (tier_wins / tier_total * 100) if tier_total > 0 else 0
                    report.append(f"   {classification}: {tier_wins}/{tier_total} ({tier_rate:.1f}%)")
                
                # Game details
                report.append(f"\n📋 DETAILED RESULTS:")
                for _, row in completed_df.iterrows():
                    result_icon = "✅" if row['won'] else "🟡" if row.get('push', False) else "❌"
                    result_text = "WIN" if row['won'] else "PUSH" if row.get('push', False) else "LOSS"
                    
                    report.append(f"   {result_icon} {row['game']} - {result_text}")
                    report.append(f"      {row['recommendation']}")
                    if row.get('final_score'):
                        report.append(f"      Final: {row['final_score']}")
                    if row.get('spread_result') or row.get('total_result'):
                        analysis = []
                        if row.get('spread_result'):
                            analysis.append(row['spread_result'])
                        if row.get('total_result'):
                            analysis.append(row['total_result'])
                        report.append(f"      {'; '.join(analysis)}")
                    report.append("")
            else:
                report.append(f"\n🔍 No completed games yet")
                report.append(f"   Total Recommendations: {len(week_df)}")
                report.append(f"   Awaiting Results...")
            
            return "\n".join(report)
            
        except Exception as e:
            return f"⚠️ Error generating report: {e}"
    
    def _show_manual_instructions(self, week: int) -> str:
        """Show manual update instructions for the week."""
        try:
            df = pd.read_csv(self.results_file)
            week_df = df[df['week'] == week].copy()
            
            if week_df.empty:
                return f"📋 Week {week}: No recommendations found to update"
            
            pending_df = week_df[week_df['won'].isna()]
            
            instructions = []
            instructions.append(f"🔧 MANUAL UPDATE INSTRUCTIONS - WEEK {week}")
            instructions.append("=" * 50)
            instructions.append(f"Use these commands to manually update results:")
            instructions.append("")
            instructions.append("tracker = UniversalWeeklyTracker()")
            instructions.append("")
            
            for _, row in pending_df.iterrows():
                game_clean = row['game'].replace("'", "\\'")
                instructions.append(f"# {row['game']}")
                instructions.append(f"# Bet: {row['recommendation']}")
                instructions.append(f"tracker.manual_update({week}, '{game_clean}', 'FINAL_SCORE', won=True/False)")
                instructions.append("")
            
            instructions.append("Example:")
            instructions.append("tracker.manual_update(12, 'Chiefs @ Bills', 'KC 31-17', won=True)")
            
            return "\n".join(instructions)
            
        except Exception as e:
            return f"⚠️ Error generating manual instructions: {e}"
    
    def manual_update(self, week: int, game: str, final_score: str, won: bool, push: bool = False):
        """Manually update a specific game result."""
        try:
            df = pd.read_csv(self.results_file)
            mask = (df['week'] == week) & (df['game'] == game)
            
            if mask.any():
                df.loc[mask, 'actual_result'] = final_score
                df.loc[mask, 'final_score'] = final_score
                df.loc[mask, 'won'] = won
                df.loc[mask, 'push'] = push
                df.loc[mask, 'result_date'] = datetime.now().isoformat()
                
                df.to_csv(self.results_file, index=False)
                print(f"✅ Updated: {game} - {'WIN' if won else 'PUSH' if push else 'LOSS'}")
            else:
                print(f"⚠️ Game not found: {game}")
                
        except Exception as e:
            print(f"⚠️ Error updating {game}: {e}")


def main():
    """Command line interface for any week operations."""
    parser = argparse.ArgumentParser(description='NFL Weekly Performance Tracker')
    parser.add_argument('week', type=int, help='NFL week number (1-18)')
    parser.add_argument('action', nargs='?', default='auto', 
                       choices=['log', 'update', 'auto', 'report', 'manual'],
                       help='Action to perform (default: auto)')
    parser.add_argument('--analytics', type=str, help='Path to analytics JSON file')
    parser.add_argument('--season', type=int, default=2024, help='NFL season year')
    
    args = parser.parse_args()
    
    tracker = UniversalWeeklyTracker()
    result = tracker.process_week(args.week, args.action, args.analytics, args.season)
    
    # Print summary
    print("\n" + "="*50)
    print("📋 OPERATION SUMMARY:")
    for message in result.get('messages', []):
        print(f"   {message}")
    
    if not result['success']:
        print(f"⚠️ Operation failed: {result.get('error', 'Unknown error')}")
        return 1
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Interactive mode if no arguments
        print("🏈 NFL Weekly Performance Tracker")
        print("=" * 40)
        week = input("Enter week number (1-18): ")
        action = input("Action [auto/log/update/report/manual]: ") or "auto"
        
        try:
            week = int(week)
            tracker = UniversalWeeklyTracker()
            tracker.process_week(week, action)
        except ValueError:
            print("⚠️ Invalid week number")
    else:
        sys.exit(main())
