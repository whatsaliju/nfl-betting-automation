#!/usr/bin/env python3
"""
NFL Betting Performance Tracker
==============================
Tracks recommendation success, calculates ROI, and identifies 
which analysis components provide the most edge.
"""

import pandas as pd
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np


class PerformanceTracker:
    """Tracks betting performance and system effectiveness."""
    
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
                'recommendation_date', 'result_date'
            ])
            df.to_csv(self.results_file, index=False)
    
    def log_week_recommendations(self, week: int, analytics_json_path: str):
        """Log all recommendations for a week from analytics JSON."""
        try:
            with open(analytics_json_path, 'r') as f:
                games = json.load(f)
            
            new_records = []
            
            for game in games:
                # Skip games without clear recommendations
                if game['classification'] in ['⚠️ LANDMINE', '❌ FADE']:
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
                    'actual_result': None,  # To be filled later
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
                    'result_date': None
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
        
        if 'AWAY on spread' in recommendation:
            bet_info = {'bet_type': 'spread', 'predicted_side': 'away'}
        elif 'HOME on spread' in recommendation:
            bet_info = {'bet_type': 'spread', 'predicted_side': 'home'}
        elif 'OVER on total' in recommendation:
            bet_info = {'bet_type': 'total', 'predicted_side': 'over'}
        elif 'UNDER on total' in recommendation:
            bet_info = {'bet_type': 'total', 'predicted_side': 'under'}
        
        return bet_info
    
    def _calculate_edge_strength(self, game: Dict) -> float:
        """Calculate overall edge strength for the recommendation."""
        sharp_edge = abs(game.get('sharp_analysis', {}).get('spread', {}).get('differential', 0))
        injury_edge = abs(game.get('injury_analysis', {}).get('net_impact', 0))
        total_score = game.get('total_score', 0)
        
        # Weighted edge calculation
        edge_strength = (sharp_edge * 0.4) + (injury_edge * 0.3) + (total_score * 0.3)
        return round(edge_strength, 2)
    
    def update_results(self, week: int, game: str, actual_result: str, 
                      closing_line: str = None, won: bool = None):
        """Update actual results for a specific game."""
        try:
            df = pd.read_csv(self.results_file)
            
            # Find the record
            mask = (df['week'] == week) & (df['game'] == game)
            
            if mask.any():
                df.loc[mask, 'actual_result'] = actual_result
                df.loc[mask, 'result_date'] = datetime.now().isoformat()
                
                if closing_line:
                    df.loc[mask, 'closing_line'] = closing_line
                
                if won is not None:
                    df.loc[mask, 'won'] = won
                
                df.to_csv(self.results_file, index=False)
                print(f"✅ Updated results for {game}")
            else:
                print(f"⚠️ Game not found: {game}")
                
        except Exception as e:
            print(f"⚠️ Error updating results: {e}")
    
    def analyze_performance(self, weeks_back: int = 4) -> Dict:
        """Analyze performance over recent weeks."""
        try:
            df = pd.read_csv(self.results_file)
            
            if df.empty:
                return {'message': 'No data available for analysis'}
            
            # Filter recent weeks
            recent_weeks = df['week'].max() - weeks_back + 1
            recent_df = df[df['week'] >= recent_weeks]
            
            analysis = {}
            
            # Overall performance
            total_bets = len(recent_df)
            completed_bets = recent_df.dropna(subset=['won'])
            
            if not completed_bets.empty:
                win_rate = completed_bets['won'].mean()
                analysis['overall'] = {
                    'total_recommendations': total_bets,
                    'completed_bets': len(completed_bets),
                    'win_rate': round(win_rate * 100, 1),
                    'pending_results': total_bets - len(completed_bets)
                }
            
            # Performance by classification
            analysis['by_classification'] = {}
            for classification in recent_df['classification'].unique():
                class_df = completed_bets[completed_bets['classification'] == classification]
                if not class_df.empty:
                    analysis['by_classification'][classification] = {
                        'count': len(class_df),
                        'win_rate': round(class_df['won'].mean() * 100, 1),
                        'avg_confidence': round(class_df['confidence'].mean(), 1)
                    }
            
            # Performance by score components
            analysis['score_component_analysis'] = self._analyze_score_components(completed_bets)
            
            # Best performing recommendations
            if not completed_bets.empty:
                winners = completed_bets[completed_bets['won'] == True]
                losers = completed_bets[completed_bets['won'] == False]
                
                analysis['insights'] = {
                    'avg_total_score_winners': round(winners['total_score'].mean(), 1) if not winners.empty else 0,
                    'avg_total_score_losers': round(losers['total_score'].mean(), 1) if not losers.empty else 0,
                    'best_performing_factor': self._identify_best_factor(completed_bets),
                    'most_reliable_classification': self._most_reliable_classification(completed_bets)
                }
            
            # Save analysis
            with open(self.analysis_file, 'w') as f:
                json.dump({
                    'last_updated': datetime.now().isoformat(),
                    'analysis_period': f"Weeks {recent_weeks}-{df['week'].max()}",
                    'data': analysis
                }, f, indent=2)
            
            return analysis
            
        except Exception as e:
            print(f"⚠️ Error analyzing performance: {e}")
            return {'error': str(e)}
    
    def _analyze_score_components(self, df: pd.DataFrame) -> Dict:
        """Analyze which scoring components correlate with wins."""
        if df.empty:
            return {}
        
        components = ['sharp_score', 'referee_score', 'weather_score', 
                     'injury_score', 'situational_score']
        
        analysis = {}
        winners = df[df['won'] == True]
        losers = df[df['won'] == False]
        
        for component in components:
            if component in df.columns:
                win_avg = winners[component].mean() if not winners.empty else 0
                loss_avg = losers[component].mean() if not losers.empty else 0
                
                analysis[component] = {
                    'winners_avg': round(win_avg, 2),
                    'losers_avg': round(loss_avg, 2),
                    'difference': round(win_avg - loss_avg, 2),
                    'correlation_strength': 'Strong' if abs(win_avg - loss_avg) > 2 else 'Moderate' if abs(win_avg - loss_avg) > 1 else 'Weak'
                }
        
        return analysis
    
    def _identify_best_factor(self, df: pd.DataFrame) -> str:
        """Identify which factor shows strongest correlation with wins."""
        if df.empty:
            return "Insufficient data"
        
        components = ['sharp_score', 'referee_score', 'weather_score', 
                     'injury_score', 'situational_score']
        
        best_factor = "sharp_score"
        best_correlation = 0
        
        winners = df[df['won'] == True]
        losers = df[df['won'] == False]
        
        for component in components:
            if component in df.columns and not winners.empty and not losers.empty:
                win_avg = winners[component].mean()
                loss_avg = losers[component].mean()
                correlation = abs(win_avg - loss_avg)
                
                if correlation > best_correlation:
                    best_correlation = correlation
                    best_factor = component
        
        return best_factor.replace('_', ' ').title()
    
    def _most_reliable_classification(self, df: pd.DataFrame) -> str:
        """Find classification with highest win rate."""
        if df.empty:
            return "Insufficient data"
        
        class_performance = {}
        for classification in df['classification'].unique():
            class_df = df[df['classification'] == classification]
            if len(class_df) >= 3:  # Minimum 3 bets for reliability
                win_rate = class_df['won'].mean()
                class_performance[classification] = win_rate
        
        if class_performance:
            best_class = max(class_performance.items(), key=lambda x: x[1])
            return f"{best_class[0]} ({best_class[1]*100:.1f}% win rate)"
        
        return "Insufficient data"
    
    def generate_performance_report(self, weeks_back: int = 4) -> str:
        """Generate a formatted performance report."""
        analysis = self.analyze_performance(weeks_back)
        
        if 'error' in analysis or 'message' in analysis:
            return "📊 Performance Report: No data available yet"
        
        report = []
        report.append("📊 NFL BETTING PERFORMANCE REPORT")
        report.append("=" * 50)
        
        # Overall performance
        if 'overall' in analysis:
            overall = analysis['overall']
            report.append(f"\n📈 OVERALL PERFORMANCE:")
            report.append(f"   Total Recommendations: {overall['total_recommendations']}")
            report.append(f"   Completed Bets: {overall['completed_bets']}")
            report.append(f"   Win Rate: {overall['win_rate']}%")
            report.append(f"   Pending Results: {overall['pending_results']}")
        
        # By classification
        if 'by_classification' in analysis:
            report.append(f"\n🎯 PERFORMANCE BY TIER:")
            for tier, stats in analysis['by_classification'].items():
                report.append(f"   {tier}: {stats['win_rate']}% ({stats['count']} bets)")
        
        # Key insights
        if 'insights' in analysis:
            insights = analysis['insights']
            report.append(f"\n🔍 KEY INSIGHTS:")
            report.append(f"   Winning Bets Avg Score: {insights['avg_total_score_winners']}")
            report.append(f"   Losing Bets Avg Score: {insights['avg_total_score_losers']}")
            report.append(f"   Best Performing Factor: {insights['best_performing_factor']}")
            report.append(f"   Most Reliable Tier: {insights['most_reliable_classification']}")
        
        # Component analysis
        if 'score_component_analysis' in analysis:
            report.append(f"\n🧮 COMPONENT ANALYSIS:")
            for component, stats in analysis['score_component_analysis'].items():
                if stats['correlation_strength'] != 'Weak':
                    component_name = component.replace('_', ' ').title()
                    report.append(f"   {component_name}: {stats['correlation_strength']} correlation")
                    report.append(f"      Winners avg: {stats['winners_avg']}, Losers avg: {stats['losers_avg']}")
        
        return "\n".join(report)


def main():
    """Example usage and testing."""
    tracker = PerformanceTracker()
    
    # Test logging (would normally be called after each week's analysis)
    # tracker.log_week_recommendations(11, "data/week11/week11_analytics.json")
    
    # Test performance analysis
    report = tracker.generate_performance_report()
    print(report)
    
    # Example of updating results
    # tracker.update_results(11, "Commanders @ Dolphins", "WAS covered spread", won=True)


if __name__ == "__main__":
    main()
