#!/usr/bin/env python3
"""
NFL Injury Impact Analyzer
==========================
Processes injury reports and calculates betting line impacts based on
player tiers, injury severity, and team context.
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd


class InjuryAnalyzer:
    """Analyzes injury impacts on betting lines and game analysis."""
    
    def __init__(self):
        """Load injury rules and whitelist from config files."""
        self.rules = self._load_config('config/injury_rules.json')
        self.whitelist = self._load_config('config/injury_whitelist.json')
        self.players_dict = {p['id']: p for p in self.whitelist['injury_whitelist']['players']}
    
    def _load_config(self, filepath: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Warning: {filepath} not found - using defaults")
            return {}
        except json.JSONDecodeError:
            print(f"⚠️  Warning: Invalid JSON in {filepath} - using defaults")
            return {}
    
    def parse_injury_status(self, status_text: str) -> Tuple[str, int, float]:
        """Parse injury status text and return normalized status, confidence, and impact multiplier."""
        if not status_text or pd.isna(status_text):
            return 'healthy', 0, 0.0
        
        status_lower = str(status_text).lower().strip()
        
        # Enhanced status mappings with impact multipliers
        status_mappings = {
            'out': {
                'keywords': ['out', 'ruled out', 'will not play', 'inactive', 'ir', 'injured reserve'],
                'confidence': 100,
                'impact_multiplier': 1.0,  # Full impact
                'description': 'Confirmed out'
            },
            'doubtful': {
                'keywords': ['doubtful', 'unlikely to play', 'long shot', 'not expected'],
                'confidence': 85,
                'impact_multiplier': 0.85,  # 85% of full impact
                'description': 'Very unlikely to play'
            },
            'questionable': {
                'keywords': ['questionable', 'q', 'game-time decision', '50-50', 'limited practice'],
                'confidence': 50,
                'impact_multiplier': 0.5,  # 50% of full impact
                'description': 'Uncertain availability'
            },
            'probable': {
                'keywords': ['probable', 'expected to play', 'should play', 'full practice'],
                'confidence': 15,
                'impact_multiplier': 0.15,  # 15% of full impact
                'description': 'Likely to play with limitations'
            }
        }
        
        # Check each status mapping
        for status, mapping in status_mappings.items():
            for keyword in mapping['keywords']:
                if keyword in status_lower:
                    return (status, 
                           mapping['confidence'], 
                           mapping['impact_multiplier'])
        
        # Default to questionable if we can't parse
        return 'questionable', 50, 0.5
    
    def classify_injury_severity(self, injury_type: str) -> Tuple[str, float]:
        """Classify injury type and return severity level and multiplier."""
        if not injury_type or pd.isna(injury_type):
            return 'unknown', 1.0
        
        injury_lower = str(injury_type).lower().strip()
        
        # Check severity mappings
        severity_rules = self.rules.get('injury_rules', {}).get('injury_severity', {})
        
        for severity, data in severity_rules.items():
            for injury_keyword in data.get('types', []):
                if injury_keyword in injury_lower:
                    return severity, data.get('multiplier', 1.0)
        
        return 'medium_severity', 1.0
    
    def calculate_player_impact(self, player_id: str, injury_status: str, 
                              injury_type: str = '', team_context: Dict = None) -> Dict:
        """Calculate comprehensive injury impact for a specific player."""
        
        # Get player from whitelist
        player = self.players_dict.get(player_id)
        if not player:
            return {
                'player_id': player_id,
                'impact_points': 0.0,
                'confidence': 0,
                'analysis': 'Player not in injury whitelist',
                'betting_recommendation': 'No impact'
            }
        
        # Parse status and severity
        status, status_confidence, status_impact_multiplier = self.parse_injury_status(injury_status)
        severity_level, severity_multiplier = self.classify_injury_severity(injury_type)
        
        # Get base impact from player tier
        tier_impact = self._get_tier_base_impact(player['tier'])
        
        # Get position multiplier
        position_rules = self.rules.get('injury_rules', {}).get('position_impact_rules', {})
        pos_data = position_rules.get(player['pos'], {})
        position_multiplier = pos_data.get('base_multiplier', 1.0)
        
        # Get status impact multiplier
        status_rules = self.rules.get('injury_rules', {}).get('status_mappings', {})
        status_multiplier = status_rules.get(status, {}).get('line_impact_multiplier', 0.5)
        
        # Apply team context modifiers
        context_multiplier = self._calculate_context_multiplier(team_context or {})
        
        # Calculate final impact
        raw_impact = tier_impact * position_multiplier * severity_multiplier * status_impact_multiplier
        final_impact = raw_impact * context_multiplier
        
        # Generate analysis and recommendations
        analysis = self._generate_player_analysis(
            player, status, severity_level, final_impact, status_confidence
        )
        
        betting_rec = self._generate_betting_recommendation(
            final_impact, status_confidence, pos_data
        )
        
        return {
            'player_id': player_id,
            'display_name': player['display_name'],
            'team': player['team'],
            'position': player['pos'],
            'tier': player['tier'],
            'injury_status': status,
            'injury_type': injury_type,
            'impact_points': round(final_impact, 2),
            'confidence': status_confidence,
            'analysis': analysis,
            'betting_recommendation': betting_rec,
            'affects_markets': pos_data.get('props_affected', []),
            'severity_level': severity_level,
            'raw_calculations': {
                'tier_impact': tier_impact,
                'position_multiplier': position_multiplier,
                'severity_multiplier': severity_multiplier,
                'status_multiplier': status_multiplier,
                'context_multiplier': context_multiplier
            }
        }
    
    def _get_tier_base_impact(self, tier: int) -> float:
        """Get base impact points for player tier."""
        tier_impacts = {1: 4.0, 2: 2.0, 3: 1.0}
        return tier_impacts.get(tier, 0.5)
    
    def _calculate_context_multiplier(self, team_context: Dict) -> float:
        """Calculate team context multiplier based on backup quality, scheme, etc."""
        multiplier = 1.0
        
        # Backup quality
        backup_quality = team_context.get('backup_quality', 'average_backup')
        depth_rules = self.rules.get('injury_rules', {}).get('team_context_rules', {}).get('depth_quality', {})
        multiplier *= depth_rules.get(backup_quality, 0.7)
        
        # Scheme dependency
        scheme = team_context.get('scheme_dependency', 'player_dependent')
        scheme_rules = self.rules.get('injury_rules', {}).get('team_context_rules', {}).get('offensive_scheme', {})
        multiplier *= scheme_rules.get(scheme, 1.0)
        
        # Season context
        season_context = team_context.get('season_importance', 'normal')
        season_rules = self.rules.get('injury_rules', {}).get('team_context_rules', {}).get('season_context', {})
        multiplier *= season_rules.get(season_context, 1.0)
        
        return max(0.2, min(2.0, multiplier))  # Cap between 0.2 and 2.0
    
    def _generate_player_analysis(self, player: Dict, status: str, severity: str, 
                                impact: float, confidence: int) -> str:
        """Generate human-readable analysis for player injury."""
        
        name = player['display_name']
        pos = player['pos']
        tier = player['tier']
        
        # Status description
        status_desc = {
            'out': 'will not play',
            'doubtful': 'is unlikely to play', 
            'questionable': 'is a game-time decision',
            'probable': 'is expected to play',
            'healthy': 'is healthy'
        }.get(status, 'has uncertain status')
        
        # Impact description
        if impact >= 2.0:
            impact_desc = "significant line impact expected"
        elif impact >= 1.0:
            impact_desc = "moderate line movement likely"
        elif impact >= 0.5:
            impact_desc = "minor impact on spreads/totals"
        else:
            impact_desc = "minimal betting impact"
        
        # Tier context
        tier_desc = {
            1: "Elite player - team offense/defense built around them",
            2: "High-impact player - noticeable drop-off without them", 
            3: "Quality starter - team has good depth to compensate"
        }.get(tier, "Role player")
        
        return f"{name} ({pos}) {status_desc}. {tier_desc}. {impact_desc.capitalize()} ({impact:.1f} points)."
    
    def _generate_betting_recommendation(self, impact: float, confidence: int, 
                                       position_data: Dict) -> str:
        """Generate specific betting recommendations based on injury impact."""
        
        if impact < 0.3 or confidence < 30:
            return "Monitor only - insufficient impact for betting action"
        
        if impact >= 1.5 and confidence >= 70:
            action = "STRONG PLAY"
        elif impact >= 0.8 and confidence >= 50:
            action = "TARGETED LEAN"
        else:
            action = "MONITOR - potential value if status worsens"
        
        # Add position-specific recommendations
        recommendations = []
        
        if position_data.get('spread_impact', False):
            recommendations.append("affects spread")
        if position_data.get('total_impact', False):
            recommendations.append("impacts total")
        if position_data.get('ml_impact', False):
            recommendations.append("moneyline value")
        
        props = position_data.get('props_affected', [])
        if props:
            recommendations.append(f"avoid {'/'.join(props[:2])} props")
        
        rec_text = " + ".join(recommendations) if recommendations else "general impact"
        
        return f"{action}: {rec_text}"
    
    def analyze_game_injuries(self, away_team: str, home_team: str, 
                            injury_data: List[Dict]) -> Dict:
        """Analyze all injuries for a specific game and generate game-level recommendations."""
        
        away_injuries = []
        home_injuries = []
        
        # Process each injury report
        for injury in injury_data:
            player_analysis = self.calculate_player_impact(
                injury.get('player_id', ''),
                injury.get('status', ''),
                injury.get('injury_type', ''),
                injury.get('team_context', {})
            )
            
            if player_analysis['team'] == away_team:
                away_injuries.append(player_analysis)
            elif player_analysis['team'] == home_team:
                home_injuries.append(player_analysis)
        
        # Calculate net impact
        away_total_impact = sum(inj['impact_points'] for inj in away_injuries)
        home_total_impact = sum(inj['impact_points'] for inj in home_injuries)
        net_impact = home_total_impact - away_total_impact  # Positive favors home
        
        # Generate game analysis
        game_analysis = self._generate_game_injury_analysis(
            away_team, home_team, away_injuries, home_injuries, net_impact
        )
        
        return {
            'away_team': away_team,
            'home_team': home_team,
            'away_injuries': away_injuries,
            'home_injuries': home_injuries,
            'away_total_impact': round(away_total_impact, 2),
            'home_total_impact': round(home_total_impact, 2),
            'net_impact': round(net_impact, 2),
            'game_analysis': game_analysis,
            'betting_recommendations': self._generate_game_betting_recs(net_impact, away_injuries, home_injuries),
            'injury_edge': self._calculate_injury_edge(net_impact)
        }
    
    def _generate_game_injury_analysis(self, away_team: str, home_team: str,
                                     away_injuries: List, home_injuries: List, 
                                     net_impact: float) -> str:
        """Generate narrative analysis for game-level injury impacts."""
        
        analysis_parts = []
        
        # High-impact injuries
        significant_injuries = []
        for injuries, team in [(away_injuries, away_team), (home_injuries, home_team)]:
            for inj in injuries:
                if inj['impact_points'] >= 1.0:
                    significant_injuries.append(f"{inj['display_name']} ({team}): {inj['analysis']}")
        
        if significant_injuries:
            analysis_parts.append("KEY INJURIES: " + " | ".join(significant_injuries[:3]))
        
        # Net impact analysis
        if abs(net_impact) >= 1.5:
            favored_team = home_team if net_impact > 0 else away_team
            analysis_parts.append(f"INJURY EDGE: {abs(net_impact):.1f} points favor {favored_team}")
        elif abs(net_impact) >= 0.5:
            favored_team = home_team if net_impact > 0 else away_team
            analysis_parts.append(f"SLIGHT EDGE: {abs(net_impact):.1f} points lean {favored_team}")
        else:
            analysis_parts.append("INJURY IMPACT: Neutral - no significant advantage either side")
        
        return " | ".join(analysis_parts) if analysis_parts else "No significant injury impacts identified."
    
    def _generate_game_betting_recs(self, net_impact: float, away_injuries: List, 
                                  home_injuries: List) -> List[str]:
        """Generate specific betting recommendations for the game."""
        recommendations = []
        
        # Spread recommendations
        if abs(net_impact) >= 1.5:
            favored_team = "home" if net_impact > 0 else "away"
            recommendations.append(f"SPREAD: Strong lean {favored_team} ({abs(net_impact):.1f} point edge)")
        elif abs(net_impact) >= 0.8:
            favored_team = "home" if net_impact > 0 else "away"
            recommendations.append(f"SPREAD: Slight lean {favored_team} ({abs(net_impact):.1f} point edge)")
        
        # Total recommendations
        total_offensive_impact = 0
        total_defensive_impact = 0
        
        for inj in away_injuries + home_injuries:
            if inj['position'] in ['QB', 'RB', 'WR', 'TE', 'LT', 'C']:
                total_offensive_impact += inj['impact_points']
            elif inj['position'] in ['CB', 'EDGE', 'IDL', 'LB']:
                total_defensive_impact += inj['impact_points']
        
        net_total_impact = total_offensive_impact - total_defensive_impact
        
        if net_total_impact >= 1.0:
            recommendations.append(f"TOTAL: Lean UNDER ({net_total_impact:.1f} offensive impact)")
        elif net_total_impact <= -1.0:
            recommendations.append(f"TOTAL: Lean OVER ({abs(net_total_impact):.1f} defensive impact)")
        
        # Prop recommendations
        high_impact_props = []
        for inj in away_injuries + home_injuries:
            if inj['impact_points'] >= 1.0 and inj['affects_markets']:
                high_impact_props.extend(inj['affects_markets'])
        
        if high_impact_props:
            unique_props = list(set(high_impact_props))[:3]
            recommendations.append(f"PROPS: Avoid {'/'.join(unique_props)}")
        
        return recommendations if recommendations else ["No strong injury-based recommendations"]
    
    def generate_prop_recommendations(self, game_injuries: List[Dict], away_team: str, home_team: str) -> List[str]:
        """Generate specific player prop recommendations based on injuries."""
        prop_recs = []
        
        for injury in game_injuries:
            player_data = self.players_dict.get(injury['player_id'], {})
            if not player_data:
                continue
                
            position = player_data.get('pos', '')
            tier = player_data.get('tier', 3)
            status = injury.get('status', 'questionable').lower()
            display_name = player_data.get('display_name', 'Player')
            
            # QB injury props
            if position == 'QB' and status in ['out', 'doubtful']:
                if tier == 1:  # Elite QB
                    prop_recs.append(f"🚨 AVOID {display_name} passing props - Elite QB out")
                    prop_recs.append(f"📉 TARGET {player_data['team']} UNDER team total")
                    prop_recs.append(f"📈 BOOST opposing defense props")
                
            # WR injury props  
            elif position == 'WR' and status in ['out', 'doubtful']:
                if tier <= 2:  # Elite/Good WR
                    prop_recs.append(f"🚨 AVOID {display_name} receiving props")
                    prop_recs.append(f"📈 TARGET other {player_data['team']} WR props")
                    prop_recs.append(f"📉 FADE {player_data['team']} QB passing yards")
                    
            # RB injury props
            elif position == 'RB' and status in ['out', 'doubtful']:
                if tier <= 3:  # Significant RB
                    prop_recs.append(f"🚨 AVOID {display_name} rushing props")
                    prop_recs.append(f"📈 TARGET backup RB props")
                    
            # Elite pass rusher props
            elif position == 'EDGE' and status in ['out', 'doubtful']:
                if tier <= 2:
                    prop_recs.append(f"📈 TARGET opposing QB props (easier matchup)")
                    prop_recs.append(f"📈 BOOST opposing team total")
        
        return prop_recs[:5]  # Return top 5 recommendations

    
    def _calculate_injury_edge(self, net_impact: float) -> str:
        """Calculate and categorize the injury betting edge."""
        abs_impact = abs(net_impact)
        
        if abs_impact >= 2.0:
            return "STRONG EDGE"
        elif abs_impact >= 1.0:
            return "MODERATE EDGE"
        elif abs_impact >= 0.5:
            return "SLIGHT EDGE"
        else:
            return "NO EDGE"
    
    def process_rotowire_injuries(self, rotowire_file: str) -> List[Dict]:
        """Process RotoWire injury CSV and return structured injury data."""
        try:
            if not os.path.exists(rotowire_file):
                print(f"⚠️  RotoWire file not found: {rotowire_file}")
                return []
            
            df = pd.read_csv(rotowire_file)
            
            if df.empty:
                return []
            
            injuries = []
            for _, row in df.iterrows():
                # Map player name to whitelist ID (simplified matching)
                player_id = self._match_player_to_whitelist(row.get('Player', ''), row.get('Team', ''))
                
                if player_id:
                    injuries.append({
                        'player_id': player_id,
                        'status': row.get('Status', ''),
                        'injury_type': row.get('Injury', ''),
                        'team_context': self._get_team_context(row.get('Team', '')),
                        'source': 'rotowire',
                        'last_updated': datetime.now().isoformat()
                    })
            
            return injuries
            
        except Exception as e:
            print(f"⚠️  Error processing RotoWire injuries: {e}")
            return []
    
    def _match_player_to_whitelist(self, player_name: str, team: str) -> Optional[str]:
        """Match player name and team to whitelist player ID."""
        if not player_name or not team:
            return None
        
        # Simple matching - in production you'd want more sophisticated matching
        name_lower = player_name.lower().strip()
        team_upper = team.upper().strip()
        
        for player_id, player_data in self.players_dict.items():
            if (team_upper == player_data['team'] and 
                name_lower in player_data['name'].lower()):
                return player_id
        
        return None
    
    def _get_team_context(self, team: str) -> Dict:
        """Get team context for injury impact calculations."""
        # This would be expanded with actual team data
        return {
            'backup_quality': 'average_backup',
            'scheme_dependency': 'player_dependent', 
            'season_importance': 'normal'
        }


def main():
    """Test the injury analyzer with sample data."""
    analyzer = InjuryAnalyzer()
    
    # Sample injury data
    sample_injuries = [
        {
            'player_id': 'allen_josh_buf_qb',
            'status': 'Questionable',
            'injury_type': 'shoulder',
            'team_context': {'backup_quality': 'poor_backup'}
        }
    ]
    
    # Test single player analysis
    result = analyzer.calculate_player_impact(
        'allen_josh_buf_qb', 'questionable', 'shoulder'
    )
    
    print("Sample Analysis:")
    print(f"Player: {result['display_name']}")
    print(f"Impact: {result['impact_points']} points")
    print(f"Analysis: {result['analysis']}")
    print(f"Recommendation: {result['betting_recommendation']}")


if __name__ == "__main__":
    main()
