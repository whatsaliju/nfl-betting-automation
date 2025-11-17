#!/usr/bin/env python3
"""
Test script to verify injury system integration
"""

import sys
sys.path.append('analyzers')

from injury_analyzer import InjuryAnalyzer

def test_injury_analyzer():
    """Test the injury analyzer with sample data."""
    
    print("🏥 Testing Injury Analyzer...")
    
    # Initialize analyzer
    analyzer = InjuryAnalyzer()
    
    # Test 1: Single player analysis
    print("\n📊 Test 1: Josh Allen shoulder injury")
    result = analyzer.calculate_player_impact(
        'allen_josh_buf_qb', 
        'questionable', 
        'shoulder',
        {'backup_quality': 'poor_backup'}
    )
    
    print(f"Player: {result['display_name']}")
    print(f"Impact: {result['impact_points']} points")
    print(f"Confidence: {result['confidence']}%")
    print(f"Analysis: {result['analysis']}")
    print(f"Recommendation: {result['betting_recommendation']}")
    
    # Test 2: Game-level analysis
    print("\n📊 Test 2: Game analysis")
    sample_injuries = [
        {
            'player_id': 'allen_josh_buf_qb',
            'status': 'questionable',
            'injury_type': 'shoulder',
            'team_context': {'backup_quality': 'poor_backup'}
        },
        {
            'player_id': 'chase_jamarr_cin_wr',
            'status': 'probable',
            'injury_type': 'ankle',
            'team_context': {}
        }
    ]
    
    game_result = analyzer.analyze_game_injuries('Cincinnati Bengals', 'Buffalo Bills', sample_injuries)
    
    print(f"Game: {game_result['away_team']} @ {game_result['home_team']}")
    print(f"Analysis: {game_result['game_analysis']}")
    print(f"Net Impact: {game_result['net_impact']} points")
    print(f"Recommendations: {game_result['betting_recommendations']}")
    
    print("\n✅ Injury analyzer test complete!")

if __name__ == "__main__":
    test_injury_analyzer()
