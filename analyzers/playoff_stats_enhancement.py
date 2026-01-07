#!/usr/bin/env python3
"""
Enhanced Statistical Analysis Module for NFL Wild Card Games
Fixes current calculation errors and adds playoff-specific metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

class PlayoffStatsAnalyzer:
    """
    Enhanced statistical analysis for NFL playoff games
    Focuses on elimination game performance and playoff-specific factors
    """
    
    def __init__(self):
        self.playoff_weight = 0.7  # Weight playoff performance higher
        self.recent_weight = 0.3   # Weight recent regular season performance
        
    def analyze_matchup(self, away_team: str, home_team: str, 
                       team_stats: Dict, historical_data: Dict) -> Dict:
        """
        Main analysis function for Wild Card matchups
        
        Returns:
            Dict with statistical edge, confidence, and key factors
        """
        
        # Core efficiency metrics
        away_eff = self._calculate_team_efficiency(away_team, team_stats, historical_data)
        home_eff = self._calculate_team_efficiency(home_team, team_stats, historical_data)
        
        # Playoff-specific adjustments
        away_playoff_adj = self._get_playoff_adjustment(away_team, historical_data)
        home_playoff_adj = self._get_playoff_adjustment(home_team, historical_data)
        
        # Calculate net edge
        raw_edge = (away_eff + away_playoff_adj) - (home_eff + home_playoff_adj)
        
        # Apply home field advantage (reduced in playoffs)
        home_advantage = self._calculate_home_advantage(home_team, team_stats)
        net_edge = raw_edge - home_advantage
        
        # Confidence scoring
        confidence = self._calculate_confidence(away_team, home_team, team_stats, historical_data)
        
        return {
            'net_edge_points': round(net_edge, 1),
            'confidence': confidence,
            'away_efficiency': away_eff,
            'home_efficiency': home_eff,
            'playoff_factors': {
                'away_adjustment': away_playoff_adj,
                'home_adjustment': home_playoff_adj,
                'home_advantage': home_advantage
            },
            'key_factors': self._identify_key_factors(away_team, home_team, team_stats, historical_data)
        }
    
    def _calculate_team_efficiency(self, team: str, team_stats: Dict, historical_data: Dict) -> float:
        """
        Calculate composite team efficiency using key metrics
        Returns points above/below average per game
        """
        
        # Core offensive metrics (last 8 games + season)
        recent_stats = team_stats.get(team, {}).get('recent_8', {})
        season_stats = team_stats.get(team, {}).get('season', {})
        
        # Offensive efficiency (points per drive, red zone %)
        off_ppd = recent_stats.get('points_per_drive', 0) * self.recent_weight + \
                 season_stats.get('points_per_drive', 0) * (1 - self.recent_weight)
        off_rz = recent_stats.get('red_zone_pct', 0) * self.recent_weight + \
                season_stats.get('red_zone_pct', 0) * (1 - self.recent_weight)
        
        # Defensive efficiency (points allowed per drive, takeaway rate)
        def_ppd = recent_stats.get('def_points_per_drive', 0) * self.recent_weight + \
                 season_stats.get('def_points_per_drive', 0) * (1 - self.recent_weight)
        def_to = recent_stats.get('takeaway_rate', 0) * self.recent_weight + \
                season_stats.get('takeaway_rate', 0) * (1 - self.recent_weight)
        
        # Composite efficiency score
        offensive_score = (off_ppd - 2.3) * 14 + (off_rz - 0.55) * 20  # League averages
        defensive_score = (2.3 - def_ppd) * 14 + (def_to - 0.12) * 25
        
        return offensive_score + defensive_score
    
    def _get_playoff_adjustment(self, team: str, historical_data: Dict) -> float:
        """
        Adjust for playoff-specific performance factors
        """
        playoff_history = historical_data.get(team, {}).get('playoff_record', {})
        
        adjustments = 0.0
        
        # Recent playoff success (last 5 years)
        recent_playoff_wins = playoff_history.get('wins_last_5_years', 0)
        recent_playoff_games = playoff_history.get('games_last_5_years', 0)
        
        if recent_playoff_games > 0:
            win_rate = recent_playoff_wins / recent_playoff_games
            # Bonus/penalty based on playoff experience
            adjustments += (win_rate - 0.5) * 3.0
        
        # Road playoff performance
        road_playoff_record = playoff_history.get('road_record', {})
        if road_playoff_record.get('games', 0) > 0:
            road_win_rate = road_playoff_record.get('wins', 0) / road_playoff_record.get('games', 1)
            adjustments += (road_win_rate - 0.4) * 2.0  # Road playoff games are tough
        
        # Coaching playoff experience
        coach_experience = historical_data.get(team, {}).get('coach_playoff_games', 0)
        if coach_experience > 10:
            adjustments += 1.0
        elif coach_experience < 3:
            adjustments -= 0.5
            
        return adjustments
    
    def _calculate_home_advantage(self, home_team: str, team_stats: Dict) -> float:
        """
        Calculate home field advantage (reduced in playoffs)
        """
        # Standard home advantage is ~2.5 points, reduced in playoffs
        base_advantage = 2.0
        
        # Team-specific home field strength
        home_record = team_stats.get(home_team, {}).get('home_record', {})
        if home_record.get('games', 0) > 0:
            home_win_pct = home_record.get('wins', 0) / home_record.get('games', 1)
            home_margin = home_record.get('avg_margin', 0)
            
            # Adjust base advantage
            advantage_modifier = (home_win_pct - 0.5) + (home_margin / 14)  # Normalize margin
            base_advantage += advantage_modifier * 1.0
            
        return max(0.5, min(4.0, base_advantage))  # Cap between 0.5-4.0 points
    
    def _calculate_confidence(self, away_team: str, home_team: str, 
                            team_stats: Dict, historical_data: Dict) -> float:
        """
        Calculate confidence in the statistical analysis
        """
        confidence_factors = []
        
        # Sample size - recent games played
        away_games = team_stats.get(away_team, {}).get('recent_8', {}).get('games', 0)
        home_games = team_stats.get(home_team, {}).get('recent_8', {}).get('games', 0)
        confidence_factors.append(min(away_games, home_games) / 8.0)
        
        # Data quality - injury impact
        away_injuries = team_stats.get(away_team, {}).get('key_injuries', 0)
        home_injuries = team_stats.get(home_team, {}).get('key_injuries', 0)
        injury_impact = max(away_injuries, home_injuries)
        confidence_factors.append(max(0.3, 1.0 - injury_impact * 0.15))
        
        # Historical data availability
        away_history = len(historical_data.get(away_team, {}).get('playoff_record', {}))
        home_history = len(historical_data.get(home_team, {}).get('playoff_record', {}))
        history_score = min(away_history, home_history) / 10.0
        confidence_factors.append(max(0.5, history_score))
        
        return round(np.mean(confidence_factors) * 10, 1)
    
    def _identify_key_factors(self, away_team: str, home_team: str, 
                            team_stats: Dict, historical_data: Dict) -> List[str]:
        """
        Identify the most significant factors driving the statistical edge
        """
        factors = []
        
        # Efficiency comparison
        away_eff = self._calculate_team_efficiency(away_team, team_stats, historical_data)
        home_eff = self._calculate_team_efficiency(home_team, team_stats, historical_data)
        
        if abs(away_eff - home_eff) > 3.0:
            better_team = away_team if away_eff > home_eff else home_team
            factors.append(f"Significant efficiency edge to {better_team} ({abs(away_eff - home_eff):.1f} pts)")
        
        # Playoff experience
        away_playoff_games = historical_data.get(away_team, {}).get('playoff_record', {}).get('games_last_5_years', 0)
        home_playoff_games = historical_data.get(home_team, {}).get('playoff_record', {}).get('games_last_5_years', 0)
        
        if abs(away_playoff_games - home_playoff_games) >= 3:
            exp_team = away_team if away_playoff_games > home_playoff_games else home_team
            factors.append(f"Playoff experience advantage: {exp_team}")
        
        # Recent form
        away_recent_margin = team_stats.get(away_team, {}).get('recent_8', {}).get('avg_margin', 0)
        home_recent_margin = team_stats.get(home_team, {}).get('recent_8', {}).get('avg_margin', 0)
        
        if abs(away_recent_margin - home_recent_margin) > 7.0:
            hot_team = away_team if away_recent_margin > home_recent_margin else home_team
            factors.append(f"Superior recent form: {hot_team}")
        
        return factors[:3]  # Return top 3 factors


# Example usage and integration
def integrate_with_existing_system(matchup_data: Dict) -> Dict:
    """
    Integration function for your existing betting system
    """
    analyzer = PlayoffStatsAnalyzer()
    
    # Mock data structure - replace with your actual data
    team_stats = {
        'Green Bay Packers': {
            'recent_8': {
                'points_per_drive': 2.4,
                'red_zone_pct': 0.58,
                'def_points_per_drive': 2.1,
                'takeaway_rate': 0.15,
                'games': 8,
                'avg_margin': 3.2
            },
            'season': {
                'points_per_drive': 2.3,
                'red_zone_pct': 0.55,
                'def_points_per_drive': 2.2,
                'takeaway_rate': 0.13
            },
            'home_record': {'wins': 6, 'games': 8, 'avg_margin': 4.1},
            'key_injuries': 1
        },
        'Chicago Bears': {
            'recent_8': {
                'points_per_drive': 2.0,
                'red_zone_pct': 0.48,
                'def_points_per_drive': 2.5,
                'takeaway_rate': 0.11,
                'games': 8,
                'avg_margin': -2.1
            },
            'season': {
                'points_per_drive': 2.1,
                'red_zone_pct': 0.50,
                'def_points_per_drive': 2.4,
                'takeaway_rate': 0.12
            },
            'home_record': {'wins': 4, 'games': 8, 'avg_margin': 1.2},
            'key_injuries': 0
        }
    }
    
    historical_data = {
        'Green Bay Packers': {
            'playoff_record': {
                'wins_last_5_years': 3,
                'games_last_5_years': 5,
                'road_record': {'wins': 1, 'games': 2}
            },
            'coach_playoff_games': 15
        },
        'Chicago Bears': {
            'playoff_record': {
                'wins_last_5_years': 0,
                'games_last_5_years': 1,
                'road_record': {'wins': 0, 'games': 0}
            },
            'coach_playoff_games': 2
        }
    }
    
    # Analyze the matchup
    result = analyzer.analyze_matchup(
        matchup_data['away'], 
        matchup_data['home'], 
        team_stats, 
        historical_data
    )
    
    # Format for your existing system
    if abs(result['net_edge_points']) < 1.5:
        description = "No significant statistical edge"
        score = 0
        factors = []
    elif abs(result['net_edge_points']) < 3.0:
        edge_team = matchup_data['away'] if result['net_edge_points'] > 0 else matchup_data['home']
        description = f"Modest statistical edge to {edge_team} ({abs(result['net_edge_points']):.1f} pts)"
        score = 1 if abs(result['net_edge_points']) < 2.5 else 2
        factors = result['key_factors'][:1]
    else:
        edge_team = matchup_data['away'] if result['net_edge_points'] > 0 else matchup_data['home']
        description = f"Strong statistical edge to {edge_team} ({abs(result['net_edge_points']):.1f} pts)"
        score = 3
        factors = result['key_factors']
    
    return {
        'score': score,
        'factors': factors,
        'description': description,
        'confidence': result['confidence'],
        'raw_analysis': result
    }


if __name__ == "__main__":
    # Test with Packers @ Bears
    test_matchup = {
        'away': 'Green Bay Packers',
        'home': 'Chicago Bears'
    }
    
    result = integrate_with_existing_system(test_matchup)
    print("Enhanced Statistical Analysis Result:")
    print(f"Score: {result['score']}")
    print(f"Description: {result['description']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Key Factors: {result['factors']}")
