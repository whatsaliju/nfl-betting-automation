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
import sys
import re
import hashlib
from datetime import datetime, timezone
from collections import defaultdict
# >>> NEW IMPORTS FOR CONCURRENCY <<<
from concurrent.futures import ThreadPoolExecutor
from functools import partial, lru_cache
# >>> END NEW IMPORTS <<<
from data.schedule_rest_2025 import SCHEDULE_REST_DATA_2025
sys.path.append(os.path.dirname(__file__))
import performance_tracker
from playoff_stats_enhancement import PlayoffStatsAnalyzer
try:
    from analyzers.nfl_common import (
        FULL_NAME_TO_TLA,
        TEAM_MAP,
        canonical_team,
        home_spread_from_line,
        normalize_matchup_key,
        normalize_season_type,
        nflverse_game_types,
    )
except ImportError:
    from nfl_common import (
        FULL_NAME_TO_TLA,
        TEAM_MAP,
        canonical_team,
        home_spread_from_line,
        normalize_matchup_key,
        normalize_season_type,
        nflverse_game_types,
    )

DEBUG_ANALYZER = os.getenv("DEBUG_ANALYZER") == "1"


def debug_log(message):
    if DEBUG_ANALYZER:
        print(message)

# ================================================================
# CONFIGURATION AND WEIGHTS (NEW)
# ================================================================

DEFAULT_MODEL_CONFIG = {
    'model_version': '2026.1',
    'factor_weights': {
        'sharp_consensus_score': 1.5,
        'referee_ats_score': 0.7,
        'referee_ou_score': 0.7,
        'weather_score': 0.5,
        'injury_score': 1.2,
        'situational_score': 1.0,
        'statistical_score': 1.8,
        'game_theory_score': 0.0,
        'schedule_score': 0.8
    },
    'selector': {
        'spread_threshold_strong_signal': 3,
        'spread_threshold_default': 4,
        'total_threshold': 4,
        'targeted_score': 4,
        'strong_score': 6,
        'require_sharp_spread_edge': True,
        'block_spread_on_team_rating_conflict': True,
        'injury_spread_mode': 'context'
    },
    'source_quality': {
        'max_age_days': 4,
        'critical_sources': ['queries', 'action_markets', 'referee_trends'],
        'supporting_sources': ['action_injuries', 'action_weather', 'rotowire'],
        'strict_sources': False,
        'block_picks_on_unsafe': True
    }
}

def load_model_config():
    path = os.getenv("NFL_MODEL_CONFIG", "config/model_config.json")
    config = dict(DEFAULT_MODEL_CONFIG)
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                loaded = json.load(f)
            config.update({k: v for k, v in loaded.items() if k != "factor_weights"})
            weights = dict(DEFAULT_MODEL_CONFIG["factor_weights"])
            weights.update(loaded.get("factor_weights", {}))
            config["factor_weights"] = weights
            selector = dict(DEFAULT_MODEL_CONFIG["selector"])
            selector.update(loaded.get("selector", {}))
            config["selector"] = selector
            source_quality = dict(DEFAULT_MODEL_CONFIG["source_quality"])
            source_quality.update(loaded.get("source_quality", {}))
            config["source_quality"] = source_quality
    except Exception as e:
        print(f"⚠️ Could not load model config {path}: {e}")
    return config

MODEL_CONFIG = load_model_config()
MODEL_VERSION = MODEL_CONFIG.get('model_version', 'unknown')

# Define weights for each factor's score contribution to the total_score.
FACTOR_WEIGHTS = MODEL_CONFIG.get('factor_weights', {
    'sharp_consensus_score': 1.5,   # High influence
    'referee_ats_score': 0.7,
    'referee_ou_score': 0.7,
    'weather_score': 0.5,           # Low influence, often secondary
    'injury_score': 1.2,
    'situational_score': 1.0,
    'statistical_score': 1.8,       # Highest influence
    'game_theory_score': 0.0,
    'schedule_score': 0.8
})
SELECTOR_CONFIG = MODEL_CONFIG.get('selector', DEFAULT_MODEL_CONFIG['selector'])
SOURCE_QUALITY_CONFIG = MODEL_CONFIG.get('source_quality', DEFAULT_MODEL_CONFIG['source_quality'])

# Define conflict penalties and caps (Now externalized)
ANALYSIS_CONFIG = {
    # Penalty when strong Statistical Signal opposes Consensus
    'CONFLICT_PENALTY_SPREAD': -2.0, 
    
    # Penalty when Sharp Total conflicts with Referee O/U
    'CONFLICT_PENALTY_TOTAL': -3.0,
    
    # Max confidence level to assign a game with Total Conflict
    'CONFIDENCE_CAP_TOTAL_CONFLICT': 4 
}

NFLVERSE_SCHEDULES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

# ================================================================
# CONSTANTS
# ================================================================

# --- DATA CONSTANT: SCHEDULE REST DATA ---
# This dictionary holds the rest days for all teams entering each week of the 2025 NFL season.
# NEW FORMAT: {Week: {Team_TLA: Rest_Days}}
# This format allows the calculate_schedule_score function to look up rest days directly by TLA.
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
def get_week_number(week):
        """Convert week to numeric for comparisons"""
        playoff_weeks = {
            'WC': 19,      # Wild Card = Week 19
            'DIV': 20,     # Divisional = Week 20  
            'CONF': 21,    # Conference = Week 21
            'SB': 22       # Super Bowl = Week 22
        }
    
        if isinstance(week, str) and week in playoff_weeks:
            return playoff_weeks[week]
        return int(week)
# ================================================================
# UTILITY FUNCTIONS
# ================================================================
# --- UTILITY FUNCTION: CALCULATE SCHEDULE SCORE ---
def calculate_schedule_score(week, home_tla, away_tla):
    """
    Calculates schedule score with robust error handling for all weeks
    """
    try:
        # Import with error details
        from data.schedule_rest_2025 import SCHEDULE_REST_DATA_2025
        
        week_key = f"W{week}" if isinstance(week, int) else week
        rest_data = SCHEDULE_REST_DATA_2025.get(week_key, {})
        
        if not rest_data:
            # This will help debug if specific weeks are missing
            available_weeks = list(SCHEDULE_REST_DATA_2025.keys())
            return 0, f"Week {week_key} not found. Available: {available_weeks[:5]}..."
        
        home_rest = rest_data.get(home_tla, 7)
        away_rest = rest_data.get(away_tla, 7)
        
        rest_differential = home_rest - away_rest
        
        score = 0
        factors = []
        
        if rest_differential > 2:
            score = 2
            factors.append(f"HOME rest advantage (+{rest_differential} days)")
        elif rest_differential < -2:
            score = -2
            factors.append(f"AWAY rest advantage (+{abs(rest_differential)} days)")
        elif rest_differential != 0:
            score = 1 if rest_differential > 0 else -1
            factors.append(f"Minor rest edge ({abs(rest_differential)} days)")
        else:
            factors.append("Neutral schedule situation (standard rest)")
        
        description = " | ".join(factors)
        
        return score, description
        
    except ImportError as e:
        return 0, f"Schedule import failed: {e}"
    except Exception as e:
        return 0, f"Schedule error: {e}"
        
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


def exact_file_or_latest(env_name, prefix):
    if env_name in os.environ:
        return os.environ.get(env_name) or None
    return find_latest(prefix)


def parse_date_from_text(text):
    if not text:
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2})", str(text))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_datetime_from_text(text):
    if not text:
        return None
    raw = str(text).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        parsed_date = parse_date_from_text(raw)
        if parsed_date:
            return datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    return None


def file_week_from_name(path):
    if not path:
        return None
    match = re.search(r"week(\d+)", os.path.basename(str(path)).lower())
    return int(match.group(1)) if match else None


def latest_date_from_column(df, column):
    if df.empty or column not in df.columns:
        return None
    parsed = pd.to_datetime(df[column], errors="coerce")
    if parsed.dropna().empty:
        return None
    return parsed.max().date()


def source_quality(name, path, df, week=None, target_date=None, required=False):
    info = {
        "name": name,
        "path": path or "",
        "rows": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        "status": "OK",
        "warnings": [],
        "critical_warnings": []
    }
    if not path:
        info["warnings"].append("missing file path")
    elif not os.path.exists(path):
        info["critical_warnings"].append("file does not exist")
    if required and info["rows"] == 0:
        info["critical_warnings"].append("required source has no rows")

    filename_date = parse_date_from_text(path)
    if filename_date:
        info["filename_date"] = filename_date.isoformat()

    fetched_date = latest_date_from_column(df, "Fetched") or latest_date_from_column(df, "fetched")
    if fetched_date:
        info["fetched_date"] = fetched_date.isoformat()

    source_date = fetched_date or filename_date
    if source_date and target_date:
        max_age_days = int(os.getenv("DATA_QUALITY_MAX_AGE_DAYS", str(SOURCE_QUALITY_CONFIG.get("max_age_days", 4))))
        age_days = (target_date - source_date).days
        info["age_days"] = age_days
        if age_days > max_age_days:
            info["warnings"].append(f"source is {age_days} days older than target date")
        if age_days < -1:
            info["critical_warnings"].append(f"source date is after target date by {abs(age_days)} days")

    embedded_week = file_week_from_name(path)
    if embedded_week is not None:
        info["file_week"] = embedded_week
        if week is not None and embedded_week != week:
            info["critical_warnings"].append(f"file week {embedded_week} does not match analysis week {week}")

    if info["critical_warnings"]:
        info["status"] = "UNSAFE"
    elif info["warnings"]:
        info["status"] = "DEGRADED"

    return info


def build_data_quality_report(week, sources):
    target_date = parse_date_from_text(os.getenv("ANALYZER_TARGET_DATE"))
    critical_sources = set(SOURCE_QUALITY_CONFIG.get("critical_sources", []))
    strict_sources = bool(SOURCE_QUALITY_CONFIG.get("strict_sources", False))
    report = {
        "status": "OK",
        "target_date": target_date.isoformat() if target_date else "",
        "sources": {},
        "warnings": [],
        "critical_warnings": [],
        "degraded_sources": [],
        "unsafe_sources": []
    }
    for name, payload in sources.items():
        info = source_quality(
            name,
            payload.get("path"),
            payload.get("df", pd.DataFrame()),
            week=week,
            target_date=target_date,
            required=payload.get("required", False)
        )
        if info["status"] == "UNSAFE" or (name in critical_sources and (info["warnings"] or info["critical_warnings"])):
            info["status"] = "UNSAFE"
        elif strict_sources and info["warnings"]:
            info["status"] = "UNSAFE"

        report["sources"][name] = info
        report["warnings"].extend([f"{name}: {warning}" for warning in info["warnings"]])
        report["critical_warnings"].extend([f"{name}: {warning}" for warning in info["critical_warnings"]])
        if info["status"] == "UNSAFE":
            report["unsafe_sources"].append(name)
        elif info["status"] == "DEGRADED":
            report["degraded_sources"].append(name)

    if report["unsafe_sources"] or report["critical_warnings"]:
        report["status"] = "UNSAFE"
    elif report["degraded_sources"] or report["warnings"]:
        report["status"] = "DEGRADED"
    return report


def analysis_reference_time():
    reference_time = parse_datetime_from_text(os.getenv("ANALYZER_REFERENCE_TIME"))
    if reference_time:
        return reference_time
    target_time = parse_datetime_from_text(os.getenv("ANALYZER_TARGET_DATE"))
    if target_time:
        return target_time
    return datetime.now(timezone.utc)


def file_fingerprint(path):
    info = {
        "path": path or "",
        "exists": False,
        "size_bytes": None,
        "modified_at": "",
        "sha256": "",
    }
    if not path or not os.path.exists(path):
        return info

    stat = os.stat(path)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    info.update({
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": digest.hexdigest(),
    })
    return info


def manifest_input_files(data_quality):
    sources = data_quality.get("sources", {}) if isinstance(data_quality, dict) else {}
    files = {
        name: file_fingerprint(source.get("path", ""))
        for name, source in sources.items()
    }
    config_path = os.getenv("NFL_MODEL_CONFIG", "config/model_config.json")
    files["model_config"] = file_fingerprint(config_path)
    return files


def build_source_health(run_manifest):
    data_quality = run_manifest.get("data_quality", {})
    sources = data_quality.get("sources", {})
    input_files = run_manifest.get("input_files", {})
    source_rows = []

    for name, source in sources.items():
        fingerprint = input_files.get(name, {})
        source_rows.append({
            "name": name,
            "status": source.get("status", "UNKNOWN"),
            "rows": source.get("rows", 0),
            "path": source.get("path", ""),
            "exists": fingerprint.get("exists", False),
            "size_bytes": fingerprint.get("size_bytes"),
            "modified_at": fingerprint.get("modified_at", ""),
            "sha256": fingerprint.get("sha256", ""),
            "age_days": source.get("age_days"),
            "file_week": source.get("file_week"),
            "filename_date": source.get("filename_date", ""),
            "fetched_date": source.get("fetched_date", ""),
            "warnings": source.get("warnings", []),
            "critical_warnings": source.get("critical_warnings", []),
        })

    return {
        "week": run_manifest.get("week"),
        "model_version": run_manifest.get("model_version", ""),
        "generated_at": run_manifest.get("generated_at", ""),
        "analysis_reference_time": run_manifest.get("analysis_reference_time", ""),
        "analysis_target_date": run_manifest.get("analysis_target_date", ""),
        "status": data_quality.get("status", "UNKNOWN"),
        "unsafe_sources": data_quality.get("unsafe_sources", []),
        "degraded_sources": data_quality.get("degraded_sources", []),
        "warnings": data_quality.get("warnings", []),
        "critical_warnings": data_quality.get("critical_warnings", []),
        "sources": source_rows,
    }


def write_source_health_text(path, source_health):
    with open(path, "w") as f:
        f.write(f"NFL WEEK {source_health.get('week')} - SOURCE HEALTH\n")
        f.write(f"Status: {source_health.get('status', 'UNKNOWN')}\n")
        f.write(f"Model: {source_health.get('model_version', '')}\n")
        f.write(f"Reference Time: {source_health.get('analysis_reference_time', '')}\n")
        f.write("=" * 70 + "\n\n")
        for source in source_health.get("sources", []):
            f.write(f"{source['name']}: {source['status']}\n")
            f.write(f"  Rows: {source.get('rows', 0)} | Exists: {source.get('exists')}\n")
            f.write(f"  Path: {source.get('path', '')}\n")
            if source.get("sha256"):
                f.write(f"  SHA256: {source['sha256']}\n")
            if source.get("age_days") is not None:
                f.write(f"  Age Days: {source['age_days']}\n")
            for warning in source.get("critical_warnings", []):
                f.write(f"  CRITICAL: {warning}\n")
            for warning in source.get("warnings", []):
                f.write(f"  Warning: {warning}\n")
            f.write("\n")


def apply_source_safety_policy(game_analysis, data_quality):
    if (
        data_quality.get("status") == "UNSAFE"
        and SOURCE_QUALITY_CONFIG.get("block_picks_on_unsafe", True)
        and game_analysis.get("pick_metadata", {}).get("market") != "none"
    ):
        game_analysis["source_blocked_recommendation"] = game_analysis.get("recommendation", "")
        game_analysis["source_blocked_pick_metadata"] = game_analysis.get("pick_metadata", {})
        game_analysis["classification"] = "⚠️ PASS"
        game_analysis["classification_label"] = "PASS"
        game_analysis["tier_score"] = 3
        game_analysis["recommendation"] = "⚠️ PASS: Unsafe source quality blocked recommendation"
        game_analysis["pick_metadata"] = {
            "market": "none",
            "reason": "unsafe source quality",
            "blocked_market": game_analysis["source_blocked_pick_metadata"].get("market"),
            "blocked_side": game_analysis["source_blocked_pick_metadata"].get("side"),
            "blocked_score": game_analysis["source_blocked_pick_metadata"].get("score"),
        }
        trace = game_analysis.get("recommendation_trace") or {}
        trace["source_policy"] = {
            "status": data_quality.get("status"),
            "blocked": True,
            "unsafe_sources": data_quality.get("unsafe_sources", []),
            "critical_warnings": data_quality.get("critical_warnings", []),
        }
        trace["final_decision"] = {
            "market": "none",
            "side": None,
            "reason": "unsafe source quality",
            "blocked_previous_market": game_analysis["source_blocked_pick_metadata"].get("market"),
            "blocked_previous_side": game_analysis["source_blocked_pick_metadata"].get("side"),
        }
        game_analysis["recommendation_trace"] = trace
    return game_analysis


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
                        debug_log(f"✅ MATCH FOUND: {player_id}")
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
        Clear and unambiguous messaging.
        """
        
        insights = []
        
        # Determine Spread Action
        abs_spread = abs(sharp_spread_diff)
        if abs_spread >= SharpMoneyAnalyzer.MASSIVE_THRESHOLD:
            if sharp_spread_diff > 0:
                insights.append(f"💰 MASSIVE EDGE: +{sharp_spread_diff:.1f}% sharp money on AWAY team")
            else:
                insights.append(f"⚠️ SHARP CONFLICT: {sharp_spread_diff:.1f}% sharp money on HOME team")
        elif abs_spread >= SharpMoneyAnalyzer.MODERATE_THRESHOLD:
            if sharp_spread_diff > 0:
                insights.append(f"📈 Sharp action: +{sharp_spread_diff:.1f}% on AWAY team")
            else:
                insights.append(f"📉 Sharp action: {sharp_spread_diff:.1f}% on HOME team")
        
        # Determine Total Action
        abs_total = abs(sharp_total_diff)
        if abs_total >= SharpMoneyAnalyzer.MASSIVE_THRESHOLD:
            if sharp_total_diff > 0:
                insights.append(f"💰 MASSIVE TOTAL EDGE: +{sharp_total_diff:.1f}% on OVER")
            else:
                insights.append(f"⚠️ TOTAL CONFLICT: {sharp_total_diff:.1f}% on UNDER")
        elif abs_total >= SharpMoneyAnalyzer.MODERATE_THRESHOLD:
            if sharp_total_diff > 0:
                insights.append(f"📈 Total action: +{sharp_total_diff:.1f}% on OVER")
            else:
                insights.append(f"📊 Total action: {sharp_total_diff:.1f}% on UNDER")
        
        # Check for Sharp Divergence
        if len(insights) == 2:
            spread_dir = "HOME" if sharp_spread_diff < 0 else "AWAY"
            total_dir = "UNDER" if sharp_total_diff < 0 else "OVER"
            
            # Classic divergence patterns
            is_divergence = (spread_dir == 'HOME' and total_dir == 'UNDER') or \
                            (spread_dir == 'AWAY' and total_dir == 'OVER')
            if is_divergence:
                return f"📈 DIVERGENCE: Sharps on {spread_dir} team + {total_dir} - expect {spread_dir.lower()} team in defensive game"
            
            # List both insights
            return "\n".join(insights)
        
        # Return single insight or default
        if insights:
            return insights[0]
        
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
        # Check for and safely access 'ats_pct' attribute (Fixes AttributeError)
        if hasattr(ref_data, 'ats_pct'):
            ats_pct = float(str(ref_data.ats_pct).replace('%', ''))
        else:
            ats_pct = 50.0 # Default if column is missing
    
        # Check for and safely access 'ou_pct' attribute (Fixes AttributeError)
        if hasattr(ref_data, 'ou_pct'):
            ou_pct = float(str(ref_data.ou_pct).replace('%', ''))
        else:
            ou_pct = 50.0 # Default if column is missing
    
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
            # FINAL CORRECTION: Use getattr() for the namedtuple
            'referee': getattr(ref_data, 'referee', 'Unknown')
        }


# ================================================================
# WEATHER ANALYZER (FIXED)
# ================================================================

class WeatherAnalyzer:
    """Analyzes weather impact from action_weather CSV format"""
    
    @staticmethod
    def analyze_from_csv_row(forecast, precip, wind):
        """
        Parse weather from CSV format:
        forecast: "25°F Windy" or "Dome"
        precip: "0 %" 
        wind: "21.56 NNE" or ""
        """
        
        # Handle dome games
        if forecast and 'dome' in forecast.lower():
            return {
                'score': 0, 
                'factors': ['Dome'], 
                'description': 'Dome - no weather impact'
            }
        
        score = 0
        factors = []
        
        # Parse temperature from forecast
        if forecast and '°' in forecast:
            import re
            temp_match = re.search(r'(\d+)°F', forecast)
            if temp_match:
                temp = int(temp_match.group(1))
                if temp <= 25:
                    score += 2  # Major cold impact
                    factors.append(f"Extreme cold ({temp}°F)")
                elif temp <= 35:
                    score += 1  # Moderate cold impact
                    factors.append(f"Cold weather ({temp}°F)")
                elif temp >= 85:
                    score += 1  # Heat impact
                    factors.append(f"Hot weather ({temp}°F)")
        
        # Parse wind speed
        if wind:
            import re
            wind_match = re.search(r'(\d+\.?\d*)', str(wind))
            if wind_match:
                wind_speed = float(wind_match.group(1))
                if wind_speed >= 20:
                    score += 2  # Major wind impact
                    factors.append(f"High wind ({wind_speed:.0f} mph)")
                elif wind_speed >= 15:
                    score += 1  # Moderate wind impact
                    factors.append(f"Windy conditions ({wind_speed:.0f} mph)")
        
        # Check for weather keywords in forecast
        if forecast:
            if 'windy' in forecast.lower():
                if not any('wind' in f.lower() for f in factors):
                    factors.append("Windy conditions")
                    score += 1
        
        # Parse precipitation (though your data shows 0% for all)
        if precip and '%' in str(precip):
            precip_num = float(precip.replace('%', '').strip())
            if precip_num >= 40:
                score += 1
                factors.append(f"Precipitation ({precip_num}%)")
        
        # Generate description
        if factors:
            desc = ', '.join(factors)
        else:
            desc = 'Good conditions'
        
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
            
    def get_correct_tla(self, full_team_name):
        """Convert full team name back to correct TLA using updated TEAM_MAP"""
        for tla, full_name in TEAM_MAP.items():
            if full_name.lower() == full_team_name.lower():  # Exact match now
                return tla
        return full_team_name[:3].upper()  # fallback
    
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
                if injury_str and pd.notna(injury_str) and injury_str.lower() != 'none':
                    # Parse injury string
                    injuries = self.parse_rotowire_injuries(injury_str)
                    
                    # Get team info
                    away_tla = row.get('away', '')
                    home_tla = row.get('home', '')
                    away_full = TEAM_MAP.get(away_tla, away_tla)
                    home_full = TEAM_MAP.get(home_tla, home_tla)
                    away_qb = row.get('away_qb', '').strip()
                    home_qb = row.get('home_qb', '').strip()
                    
                    for inj in injuries:
                        # ENHANCED: Determine which team the injury belongs to
                        player_name = inj['player']

                        # Method 1: Match by QB name
                        if inj['position'] == 'QB':
                            if self._name_matches(player_name, away_qb):
                                inj['team'] = away_full
                                inj['team_tla'] = away_tla
                            elif self._name_matches(player_name, home_qb):
                                inj['team'] = home_full
                                inj['team_tla'] = home_tla
                            else:
                                # Default to away team if can't determine
                                inj['team'] = away_full
                                inj['team_tla'] = away_tla
                        else:
                            # Method 2: For non-QBs, try whitelist matching to determine team
                            away_match = self.enhanced_match_player(player_name, away_full)
                            home_match = self.enhanced_match_player(player_name, home_full)
                            
                            if away_match:
                                inj['team'] = away_full
                                inj['team_tla'] = away_tla
                            elif home_match:
                                inj['team'] = home_full  
                                inj['team_tla'] = home_tla
                            else:
                                # Default to away team if can't determine
                                inj['team'] = away_full
                                inj['team_tla'] = away_tla
                        
                        injury_data.append(inj)
                        
        except Exception as e:
            print(f"⚠️ Error processing RotoWire injuries: {e}")
        
        return injury_data
   
    def _name_matches(self, player_name, reference_name):
        """Check if player name matches reference (like QB name from roster)"""
        if not player_name or not reference_name:
            return False
        
        # Simple matching - you can enhance this
        player_parts = player_name.lower().split()
        ref_parts = reference_name.lower().split()
        
        # Match last name
        if player_parts and ref_parts:
            return player_parts[-1] == ref_parts[-1]
        
        return False    
    
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
    
    # Also update analyze_game_injuries to use the new team assignments:
    def analyze_game_injuries(self, away_team, home_team, injury_data):
        """Comprehensive game-level injury analysis."""
        away_injuries = []
        home_injuries = []
        
        # NEW: Use the specific team assignments from processed data
        for injury in injury_data:
            injury_team = injury.get('team', '')
            if injury_team == away_team:
                away_injuries.append(injury)
            elif injury_team == home_team:
                home_injuries.append(injury)
        
        # Calculate team impacts using the correct team assignments
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

    
    # And finally, update calculate_team_impact to use team_tla for whitelist matching:
    def calculate_team_impact(self, injuries, team_name):
        """Calculate total injury impact for a team."""
        total_impact = 0
        
        for injury in injuries:
            # Use team_tla if available, otherwise fall back to team name
            team_for_matching = injury.get('team_tla', team_name)
            player_id = self.enhanced_match_player(injury['player'], team_for_matching)
            
            if player_id and player_id in self.players_dict:
                player_data = self.players_dict[player_id]
                impact = self.calculate_player_impact(injury, player_data)
                total_impact += impact
                debug_log(f"🏥 INJURY IMPACT: {injury['player']} ({team_for_matching}) = {impact:.1f} points")
        
        return min(total_impact, 10)  # Cap at 10 points

    def enhanced_match_player(self, player_name, team_name):
        """Enhanced player matching with fuzzy name matching for abbreviations"""
        if not self.players_dict:
            return None
        
        name_lower = player_name.lower().strip()
        
        # Team abbreviation mapping (your existing one)
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
        
        # Enhanced matching with multiple strategies
        for player_id, player_data in self.players_dict.items():
            if team_abbrev != player_data['team']:
                continue  # Skip wrong team
                
            player_whitelist_name = player_data['name'].lower()
            
            # Strategy 1: Exact match (existing)
            if name_lower == player_whitelist_name:
                return player_id
                
            # Strategy 2: Simple substring match (existing)
            if name_lower in player_whitelist_name or player_whitelist_name in name_lower:
                return player_id
                
            # Strategy 3: Handle abbreviations (NEW)
            # Example: "A. St. Brown" should match "Amon-Ra St. Brown"
            if self._matches_with_abbreviation(name_lower, player_whitelist_name):
                return player_id
                
            # Strategy 4: Last name + first initial match (NEW)
            # Example: "J. Allen" should match "Josh Allen" 
            if self._matches_last_name_initial(name_lower, player_whitelist_name):
                return player_id
        
        return None
    
    def _matches_with_abbreviation(self, input_name, whitelist_name):
        """Check if abbreviated name matches full name"""
        # Split both names into parts
        input_parts = input_name.replace('.', '').split()
        whitelist_parts = whitelist_name.split()
        
        if len(input_parts) != len(whitelist_parts):
            return False
        
        for i, (inp, wl) in enumerate(zip(input_parts, whitelist_parts)):
            # If input is single character, check if it's first letter of whitelist
            if len(inp) == 1:
                if inp != wl[0]:
                    return False
            else:
                # Full word must match exactly
                if inp != wl:
                    return False
        
        return True
    
    def _matches_last_name_initial(self, input_name, whitelist_name):
        """Check if 'J. Allen' matches 'Josh Allen' pattern"""
        input_parts = input_name.replace('.', '').split()
        whitelist_parts = whitelist_name.split()
        
        if len(input_parts) != 2 or len(whitelist_parts) != 2:
            return False
            
        # First part should be single initial matching first letter of whitelist first name
        if len(input_parts[0]) == 1 and input_parts[0] == whitelist_parts[0][0]:
            # Second part should match last name exactly
            if input_parts[1] == whitelist_parts[1]:
                return True
        
        return False
    
    # Test the matching with your actual data
    def test_enhanced_matching():
        """Test the enhanced matching with real examples"""
        
        # Simulate your whitelist entry
        test_whitelist = {
            "stbrown_amonra_det_wr": {
                "name": "Amon-Ra St. Brown",
                "team": "DET", 
                "pos": "WR"
            },
            "allen_josh_buf_qb": {
                "name": "Josh Allen",
                "team": "BUF",
                "pos": "QB"  
            }
        }
        
        # Test cases from RotoWire format
        test_cases = [
            ("A. St. Brown", "Detroit Lions", "stbrown_amonra_det_wr"),
            ("J. Allen", "Buffalo Bills", "allen_josh_buf_qb"),
            ("Josh Allen", "Buffalo Bills", "allen_josh_buf_qb"),
            ("Amon-Ra St. Brown", "Detroit Lions", "stbrown_amonra_det_wr")
        ]
        
        # Create mock analyzer
        class MockAnalyzer:
            def __init__(self):
                self.players_dict = test_whitelist
                
            def enhanced_match_player(self, player_name, team_name):
                # Your enhanced function logic here
                pass
        
        debug_log("Testing enhanced player matching:")
        for player, team, expected in test_cases:
            debug_log(f"'{player}' + '{team}' -> Expected: {expected}")
    
    if __name__ == "__main__":
        test_enhanced_matching()
    
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
    def match_action_network_injuries(team_name, team_tla, action_injuries_df):
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
                'injury_type': inj.get('injury', 'Unknown'),
                'team': team_name,
                'team_tla': team_tla
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
    def analyze_game_injuries(self, away_team, home_team, injury_data):
        # ... (code for collecting away_injuries / home_injuries lists) ...
        
        # Calculate team impacts using the correct team assignments
        away_impact_score = self.calculate_team_impact(away_injuries, away_team)
        home_impact_score = self.calculate_team_impact(home_injuries, home_team)
        
        # Net impact (positive favors home, negative favors away)
        net_impact = home_impact_score - away_impact_score
        
        # Generate analysis
        game_analysis = self.generate_game_analysis(away_team, home_team, away_impact_score, home_impact_score, net_impact)
        
        # Betting recommendations
        betting_recs = self.generate_betting_recommendations(away_team, home_team, net_impact, away_injuries, home_injuries)
        
        return {
            'away_injuries': away_injuries,
            'home_injuries': home_injuries,
            
            # ✅ FIX 1: Rename/Keep impact scores (and round them)
            'away_impact_score': round(away_impact_score, 2),
            'home_impact_score': round(home_impact_score, 2),
            'net_impact': round(net_impact, 2), # ✅ FIX 2: Round net impact
            
            'injury_edge': 'STRONG EDGE' if abs(net_impact) >= 3 else 'MODERATE EDGE' if abs(net_impact) >= 1 else 'NO EDGE',
            'game_analysis': game_analysis,
            'betting_recommendations': betting_recs
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
        if get_week_number(week) >= 15:  # Late season games where playoff spots are locked
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
    """Current-season team rating model from nflverse results."""
    
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
    def default_season():
        env_season = os.getenv("NFL_SEASON")
        if env_season:
            try:
                return int(env_season)
            except ValueError:
                pass

        now = datetime.now()
        return now.year - 1 if now.month <= 2 else now.year

    @staticmethod
    def default_season_type(week=None):
        return normalize_season_type(os.getenv("NFL_SEASON_TYPE"), week)

    @staticmethod
    @lru_cache(maxsize=16)
    def load_completed_games(season, week, season_type="REG"):
        """Load completed games before the week being analyzed."""
        try:
            season_type = normalize_season_type(season_type, week)
            usecols = [
                'season', 'game_type', 'week',
                'away_team', 'home_team', 'away_score', 'home_score'
            ]
            games = pd.read_csv(NFLVERSE_SCHEDULES_URL, usecols=usecols)
            if season_type == "POST":
                game_mask = (
                    (games['game_type'] == 'REG')
                    | (
                        games['game_type'].isin(nflverse_game_types("POST"))
                        & (games['week'] < week)
                    )
                )
            else:
                game_mask = (
                    games['game_type'].isin(nflverse_game_types("REG"))
                    & (games['week'] < week)
                )
            games = games[
                (games['season'] == season)
                & game_mask
            ].copy()
            games = games.dropna(subset=['away_score', 'home_score'])
            return games
        except Exception as e:
            print(f"⚠️ Statistical model could not load nflverse schedules: {e}")
            return pd.DataFrame()

    @staticmethod
    def team_code(team_name):
        if team_name in TEAM_MAP:
            return team_name
        return FULL_NAME_TO_TLA.get(str(team_name).lower(), str(team_name).upper())

    @staticmethod
    @lru_cache(maxsize=64)
    def build_team_ratings(season, week, season_type="REG"):
        season_type = normalize_season_type(season_type, week)
        games = StatisticalAnalyzer.load_completed_games(season, week, season_type)
        source_season = season
        source_label = f"season {season}, {season_type} pre-Week {week}"

        if games.empty and season_type == "REG" and week <= 4:
            source_season = season - 1
            source_label = f"previous-season prior ({source_season})"
            games = StatisticalAnalyzer.load_completed_games(source_season, 99, "REG")

        if games.empty:
            return {}

        rows = []
        for _, game in games.iterrows():
            away = game['away_team']
            home = game['home_team']
            away_score = float(game['away_score'])
            home_score = float(game['home_score'])

            rows.append({
                'team': away,
                'opponent': home,
                'week': int(game['week']),
                'margin': away_score - home_score,
                'points_for': away_score,
                'points_against': home_score,
            })
            rows.append({
                'team': home,
                'opponent': away,
                'week': int(game['week']),
                'margin': home_score - away_score,
                'points_for': home_score,
                'points_against': away_score,
            })

        team_games = pd.DataFrame(rows)
        base = team_games.groupby('team').agg(
            games=('margin', 'count'),
            avg_margin=('margin', 'mean'),
            avg_points_for=('points_for', 'mean'),
            avg_points_against=('points_against', 'mean'),
        )

        latest_weeks = sorted(team_games['week'].unique())[-4:]
        recent = (
            team_games[team_games['week'].isin(latest_weeks)]
            .groupby('team')['margin']
            .mean()
            .rename('recent_margin')
        )
        base = base.join(recent, how='left')
        base['recent_margin'] = base['recent_margin'].fillna(base['avg_margin'])

        opponent_strength = {}
        for team, group in team_games.groupby('team'):
            opponent_margins = []
            for opponent in group['opponent']:
                if opponent in base.index:
                    opponent_margins.append(base.at[opponent, 'avg_margin'])
            opponent_strength[team] = float(np.mean(opponent_margins)) if opponent_margins else 0.0

        ratings = {}
        for team, row in base.iterrows():
            sos = opponent_strength.get(team, 0.0)
            rating = (
                row['avg_margin'] * 0.60
                + row['recent_margin'] * 0.25
                + sos * 0.15
            )
            ratings[team] = {
                'rating': round(float(rating), 2),
                'games': int(row['games']),
                'avg_margin': round(float(row['avg_margin']), 2),
                'recent_margin': round(float(row['recent_margin']), 2),
                'sos': round(float(sos), 2),
                'avg_points_for': round(float(row['avg_points_for']), 1),
                'avg_points_against': round(float(row['avg_points_against']), 1),
                'source_season': source_season,
                'source_label': source_label,
            }

        return ratings

    @staticmethod
    def parse_home_spread(spread_line):
        """Extract the home team's spread from an Action Network line string."""
        return home_spread_from_line(spread_line)

    @staticmethod
    def calculate_expected_home_margin(away_team, home_team, week, season=None, season_type=None):
        """Estimate home-team margin using actual current-season results."""
        season = season or StatisticalAnalyzer.default_season()
        season_type = normalize_season_type(season_type or StatisticalAnalyzer.default_season_type(week), week)
        ratings = StatisticalAnalyzer.build_team_ratings(season, week, season_type)
        away_tla = StatisticalAnalyzer.team_code(away_team)
        home_tla = StatisticalAnalyzer.team_code(home_team)

        if away_tla not in ratings or home_tla not in ratings:
            return None, {}, {}

        home_field = 1.5
        expected_margin = ratings[home_tla]['rating'] - ratings[away_tla]['rating'] + home_field
        return round(expected_margin, 1), ratings[away_tla], ratings[home_tla]
    
    @staticmethod
    def analyze_line_value(away_team, home_team, spread_line, week):
        """Analyze if the betting line offers value vs. expected margin"""
        factors = []
        score = 0
        
        try:
            season = StatisticalAnalyzer.default_season()
            season_type = StatisticalAnalyzer.default_season_type(week)
            home_spread = StatisticalAnalyzer.parse_home_spread(spread_line)
            if home_spread is None:
                return score, factors

            expected_home_margin, away_rating, home_rating = StatisticalAnalyzer.calculate_expected_home_margin(
                away_team, home_team, week, season=season, season_type=season_type
            )
            if expected_home_margin is None:
                factors.append(f"No current-season team rating yet for {season} {season_type} Week {week}")
                return score, factors

            # Positive edge favors home against the spread; negative favors away.
            value_difference = expected_home_margin + home_spread

            if abs(value_difference) >= 3:
                if value_difference > 0:
                    score += 2
                    factors.append(
                        f"Current-season value on home team ({value_difference:+.1f} pts; "
                        f"projected home margin {expected_home_margin:+.1f})"
                    )
                else:
                    score += 2
                    factors.append(
                        f"Current-season value on away team ({abs(value_difference):.1f} pts; "
                        f"projected home margin {expected_home_margin:+.1f})"
                    )
            elif abs(value_difference) >= 1.5:
                score += 1
                side = "home" if value_difference > 0 else "away"
                factors.append(
                    f"Modest current-season edge on {side} ({abs(value_difference):.1f} pts; "
                    f"projected home margin {expected_home_margin:+.1f})"
                )

            if factors:
                away_tla = StatisticalAnalyzer.team_code(away_team)
                home_tla = StatisticalAnalyzer.team_code(home_team)
                factors.append(
                    f"Ratings: {away_tla} {away_rating.get('rating', 0):+.1f}, "
                    f"{home_tla} {home_rating.get('rating', 0):+.1f} "
                    f"({home_rating.get('source_label', f'season {season}, pre-Week {week}')})"
                )
                
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
        
        # Large sharp edges suggest market inefficiency
        if abs(sharp_edge) >= 10:
            factors.append(f"Market inefficiency detected ({sharp_edge:+.1f}% sharp edge)")
        elif abs(sharp_edge) >= 5:
            factors.append(f"Market mispricing possible ({sharp_edge:+.1f}% edge)")
        
        # Extreme public betting percentages
        if public_pct >= 80 or public_pct <= 20:
            factors.append(f"Extreme public sentiment ({public_pct:.0f}% on one side)")
        
        return 0, factors
    
    @staticmethod
    def detect_steam_moves(sharp_edge, public_pct):
        """Detect potential steam move scenarios"""
        factors = []
        
        # Steam move: Sharp money against public sentiment
        if sharp_edge > 8 and public_pct > 65:
            factors.append("STEAM MOVE: Sharps heavily against public")
        elif sharp_edge < -8 and public_pct < 35:
            factors.append("STEAM MOVE: Sharps heavily against public")
        elif abs(sharp_edge) >= 5 and ((sharp_edge > 0 and public_pct > 60) or (sharp_edge < 0 and public_pct < 40)):
            factors.append("Potential steam move developing")
            
        return 0, factors
    
    @staticmethod
    def analyze_contrarian_value(public_pct, prime_time, team_popularity):
        """Identify contrarian betting opportunities"""
        factors = []
        
        # High public percentage + popular team = contrarian opportunity
        if public_pct >= 70:
            factors.append("High contrarian value (fade the public)")
            
            if prime_time:
                factors.append("Primetime public overreaction")
                
            if team_popularity == "high":
                factors.append("Popular team getting overbet")
        
        # Low public percentage on popular team = potential value
        elif public_pct <= 30 and team_popularity == "high":
            factors.append("Popular team getting underbet")
            
        return 0, factors
    
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
        # Defensive checks for required data
        if not sharp_analysis or 'spread' not in sharp_analysis:
            return ["Sharp analysis data unavailable"]
        
        spread = sharp_analysis.get('spread', {})
        total = sharp_analysis.get('total', {})
        ml = sharp_analysis.get('moneyline', {})
        
        # Check if required keys exist
        required_keys = ['direction', 'differential']
        if not all(key in spread for key in required_keys):
            debug_log(f"🔍 DEBUG: Missing keys in spread: {list(spread.keys())}")
            return ["Sharp spread analysis incomplete"]
        
        if not all(key in total for key in required_keys):
            debug_log(f"🔍 DEBUG: Missing keys in total: {list(total.keys())}")
            return ["Sharp total analysis incomplete"]
        
        if 'direction' not in ml:
            debug_log(f"🔍 DEBUG: Missing keys in moneyline: {list(ml.keys())}")
            return ["Sharp moneyline analysis incomplete"]
        
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
        if abs(spread['differential']) >= 10 and spread.get('bets_pct', 0) > 65:
            if spread['differential'] > 0:
                stories.append("🚨 TRAP ALERT: Public hammering home, sharps quietly on away")
            else:
                stories.append("🚨 TRAP ALERT: Public hammering away, sharps quietly on home")
        
        # Strong edges
        if abs(spread['differential']) >= 15:
            if spread['differential'] > 0:
                stories.append(f"💰 MASSIVE EDGE: +{spread['differential']:.1f}% sharp money on AWAY team")
            else:
                stories.append(f"⚠️ SHARP CONFLICT: {spread['differential']:.1f}% sharp money on HOME team")
        
        if abs(total['differential']) >= 15:
            if total['differential'] > 0:
                stories.append(f"💰 MASSIVE EDGE: +{total['differential']:.1f}% sharp money on OVER")
            else:
                stories.append(f"⚠️ SHARP CONFLICT: {total['differential']:.1f}% sharp money on UNDER")
        
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
                away_injuries = injury_data.get('away_injuries', [])
                away_count = len(away_injuries)
                home_injuries = injury_data.get('home_injuries', [])
                home_count = len(home_injuries) if home_injuries else 0
                narrative.append(f"   Team Impacts: {away_team} ({away_count} injuries) vs {home_team} ({home_count} injuries)")
                
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
    def classify_game(game_analysis):
        """Determine game classification"""
        total = game_analysis['total_score']
        sharp_score = abs(game_analysis['sharp_consensus_score'])
        ref_score = abs(game_analysis['referee_analysis']['ats_score'])
        injury_score = abs(game_analysis['injury_analysis']['score'])
        
        # Blue Chip: Strong alignment across all factors (15+ confidence)
        if total >= 15 and sharp_score >= 2 and (ref_score >= 2 or injury_score >= 3):
            return "🔵 BLUE CHIP", "STRONG PLAY", 15
        
        # Targeted Play: Good edge with supporting factors (7+ confidence)
        if total >= 7 and (sharp_score >= 1 or injury_score >= 2):
            return "🎯 TARGETED PLAY", "SOLID EDGE", 10
            
        # Lean: Modest edge (5-7 confidence)
        if total >= 5:
            return "📊 LEAN", "SLIGHT EDGE", 5
        
        # Trap Game: Public/sharp divergence
        if sharp_score >= 2 and game_analysis.get('public_exposure', 0) >= 65:
            return "🚨 TRAP GAME", "FADE PUBLIC", 4
        
        # Fade: reserved for true negative aggregate risk
        if total <= -2:
            return "❌ FADE", "AVOID", 2
        
        # Landmine: Mixed signals (anything else)
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

        # New BLUE CHIP Logic (Prioritizes Highest Edge):
        if "BLUE CHIP" in cat:
            # Determine which play has the absolute strongest edge (Spread or Total)
            if total_edge >= spread_edge and total_edge > 0:
                primary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num)
                secondary_rec = ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num) if spread_edge >= 10 else None
            else:
                primary_rec = ClassificationEngine.generate_primary_bet(spread_dir, away_team, home_team, spread_num)
                secondary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num) if total_edge >= 10 else None
            
            # If a secondary recommendation is not possible, we check if the other play still has a high enough edge
            if not secondary_rec and total_edge >= 10 and primary_rec != ClassificationEngine.generate_total_bet(total_dir, total_num):
                secondary_rec = ClassificationEngine.generate_total_bet(total_dir, total_num)
        
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


class RecommendationSelector:
    """Choose the bet market that best matches the strongest aligned signals."""

    @staticmethod
    def spread_side_from_stat_factors(factors):
        text = " ".join(factors).lower()
        if "value on home" in text or "edge on home" in text:
            return "HOME"
        if "value on away" in text or "edge on away" in text:
            return "AWAY"
        return "NEUTRAL"

    @staticmethod
    def total_side_from_context(referee_analysis, weather_analysis):
        score = 0
        factors = []

        ou_score = referee_analysis.get('ou_score', 0)
        if ou_score > 0:
            score += ou_score
            factors.append("referee over trend")
        elif ou_score < 0:
            score += ou_score
            factors.append("referee under trend")

        weather_score = weather_analysis.get('score', 0)
        weather_text = " ".join(weather_analysis.get('factors', [])).lower()
        if weather_score >= 2 and any(term in weather_text for term in ['wind', 'cold', 'snow', 'rain']):
            score -= min(weather_score, 3)
            factors.append("weather suppresses scoring")

        return score, factors

    @staticmethod
    def format_spread(side, away_team, home_team, spread_num):
        return ClassificationEngine.generate_primary_bet(side, away_team, home_team, spread_num)

    @staticmethod
    def format_total(side, total_num):
        return ClassificationEngine.generate_total_bet(side, total_num)

    @staticmethod
    def label_for_score(score):
        if score >= SELECTOR_CONFIG.get('strong_score', 6):
            return "✅ STRONG PLAY"
        if score >= SELECTOR_CONFIG.get('targeted_score', 4):
            return "🎯 TARGETED PLAY"
        return "👀 LEAN"

    @staticmethod
    def classification_for_pick(pick_metadata):
        market = pick_metadata.get('market')
        if market in (None, 'none'):
            reason = pick_metadata.get('reason', '')
            if 'fade' in reason:
                return "❌ FADE", "AVOID", 2
            return "⚠️ PASS", "PASS", 3

        score = pick_metadata.get('score', 0)
        if score >= SELECTOR_CONFIG.get('strong_score', 6):
            return "🔵 BLUE CHIP", "STRONG PLAY", 9
        if score >= SELECTOR_CONFIG.get('targeted_score', 4):
            return "🎯 TARGETED PLAY", "SOLID EDGE", 7
        return "📊 LEAN", "SLIGHT EDGE", 5

    @staticmethod
    def pass_metadata(reason, spread_trace=None, total_trace=None, final_reason=None):
        trace = {
            "selector_version": MODEL_VERSION,
            "market_candidates": {
                "spread": spread_trace or {},
                "total": total_trace or {},
            },
            "final_decision": {
                "market": "none",
                "side": None,
                "reason": final_reason or reason,
            }
        }
        return {
            'market': 'none',
            'reason': reason,
            'spread_score': (spread_trace or {}).get('score'),
            'total_score': (total_trace or {}).get('score'),
            'trace': trace,
        }

    @staticmethod
    def play_metadata(market, side, score, reasons, spread_trace, total_trace):
        trace = {
            "selector_version": MODEL_VERSION,
            "market_candidates": {
                "spread": spread_trace,
                "total": total_trace,
            },
            "final_decision": {
                "market": market,
                "side": side,
                "score": score,
                "reason": f"{market} candidate cleared threshold and ranked highest",
            }
        }
        return {
            'market': market,
            'side': side,
            'score': score,
            'reasons': reasons,
            'spread_score': spread_trace.get('score'),
            'total_score': total_trace.get('score'),
            'trace': trace,
        }

    @staticmethod
    def select(classification, game_analysis):
        if "FADE" in classification:
            return "❌ AVOID: Multiple negative factors align", RecommendationSelector.pass_metadata(
                "fade classification",
                final_reason="signal classification was FADE"
            )
        if "LANDMINE" in classification:
            return "⚠️ PASS: Mixed signals, no clear edge identified", RecommendationSelector.pass_metadata(
                "landmine classification",
                final_reason="signal classification was LANDMINE"
            )

        sharp = game_analysis['sharp_analysis']
        away_team = game_analysis.get('away', '')
        home_team = game_analysis.get('home', '')
        spread_num = ClassificationEngine.extract_spread_number(sharp.get('spread', {}).get('line', ''))
        total_num = ClassificationEngine.extract_total_number(sharp.get('total', {}).get('line', ''))

        spread_score = 0
        spread_reasons = []
        spread_signals = []
        spread_conflicts = []
        spread_blockers = []
        spread_side = sharp.get('spread', {}).get('direction', 'NEUTRAL')
        sharp_spread_score = sharp.get('spread', {}).get('score', 0)
        has_sharp_spread_edge = spread_side in {'AWAY', 'HOME'} and sharp_spread_score != 0
        spread_blocked = False
        if spread_side in {'AWAY', 'HOME'}:
            spread_score += abs(sharp_spread_score)
            if sharp_spread_score:
                spread_reasons.append("sharp spread edge")
                spread_signals.append({
                    "source": "sharp",
                    "side": spread_side,
                    "score": sharp_spread_score,
                    "impact": abs(sharp_spread_score),
                    "status": "aligned",
                })
        else:
            spread_blockers.append("no sharp spread side")

        stat_side = RecommendationSelector.spread_side_from_stat_factors(
            game_analysis.get('statistical_analysis', {}).get('factors', [])
        )
        stat_score = game_analysis.get('statistical_analysis', {}).get('score', 0) or 0
        if stat_side in {'AWAY', 'HOME'}:
            if spread_side == 'NEUTRAL':
                spread_side = stat_side
            if stat_side == spread_side:
                spread_score += stat_score
                spread_reasons.append("team-rating edge aligns")
                spread_signals.append({
                    "source": "team_rating",
                    "side": stat_side,
                    "score": stat_score,
                    "impact": stat_score,
                    "status": "aligned",
                })
            else:
                if SELECTOR_CONFIG.get('block_spread_on_team_rating_conflict', True):
                    spread_score = 0
                    spread_blocked = True
                    spread_blockers.append("team-rating conflict")
                else:
                    spread_score -= stat_score
                spread_reasons.append("team-rating edge conflicts")
                spread_conflicts.append({
                    "source": "team_rating",
                    "side": stat_side,
                    "score": stat_score,
                    "status": "conflict",
                })

        injury_score = game_analysis.get('injury_analysis', {}).get('score', 0) or 0
        injury_context_present = False
        if injury_score > 0:
            injury_side = 'HOME'
        elif injury_score < 0:
            injury_side = 'AWAY'
        else:
            injury_side = 'NEUTRAL'
        if injury_side in {'AWAY', 'HOME'}:
            injury_context_present = True
            if spread_side == 'NEUTRAL':
                spread_side = injury_side
            if injury_side == spread_side:
                if SELECTOR_CONFIG.get('injury_spread_mode', 'context') == 'score':
                    spread_score += min(abs(injury_score), 3)
                    spread_reasons.append("injury edge aligns")
                    impact = min(abs(injury_score), 3)
                else:
                    spread_reasons.append("injury context aligns")
                    impact = 0
                spread_signals.append({
                    "source": "injury",
                    "side": injury_side,
                    "score": injury_score,
                    "impact": impact,
                    "status": "aligned",
                })
            else:
                if SELECTOR_CONFIG.get('injury_spread_mode', 'context') == 'score':
                    spread_score -= min(abs(injury_score), 3)
                    spread_reasons.append("injury edge conflicts")
                    impact = -min(abs(injury_score), 3)
                else:
                    spread_reasons.append("injury context conflicts")
                    impact = 0
                spread_conflicts.append({
                    "source": "injury",
                    "side": injury_side,
                    "score": injury_score,
                    "impact": impact,
                    "status": "conflict",
                })

        if spread_blocked or (SELECTOR_CONFIG.get('require_sharp_spread_edge', True) and not has_sharp_spread_edge):
            if SELECTOR_CONFIG.get('require_sharp_spread_edge', True) and not has_sharp_spread_edge:
                spread_blockers.append("sharp spread edge required")
            spread_score = 0

        total_score = 0
        total_reasons = []
        total_signals = []
        total_conflicts = []
        total_blockers = []
        total_side = sharp.get('total', {}).get('direction', 'NEUTRAL')
        sharp_total_score = sharp.get('total', {}).get('score', 0)
        if total_side in {'OVER', 'UNDER'}:
            total_score += abs(sharp_total_score)
            if sharp_total_score:
                total_reasons.append("sharp total edge")
                total_signals.append({
                    "source": "sharp",
                    "side": total_side,
                    "score": sharp_total_score,
                    "impact": abs(sharp_total_score),
                    "status": "aligned",
                })
        else:
            total_blockers.append("no sharp total side")

        context_total_score, context_reasons = RecommendationSelector.total_side_from_context(
            game_analysis.get('referee_analysis', {}),
            game_analysis.get('weather_analysis', {})
        )
        context_side = 'OVER' if context_total_score > 0 else 'UNDER' if context_total_score < 0 else 'NEUTRAL'
        if context_side in {'OVER', 'UNDER'}:
            if total_side == 'NEUTRAL':
                total_side = context_side
            if context_side == total_side:
                impact = min(abs(context_total_score), 4)
                total_score += impact
                total_reasons.extend(context_reasons)
                total_signals.append({
                    "source": "ref_weather_context",
                    "side": context_side,
                    "score": context_total_score,
                    "impact": impact,
                    "status": "aligned",
                    "reasons": context_reasons,
                })
            else:
                impact = -min(abs(context_total_score), 4)
                total_score += impact
                total_reasons.append("ref/weather total context conflicts")
                total_conflicts.append({
                    "source": "ref_weather_context",
                    "side": context_side,
                    "score": context_total_score,
                    "impact": impact,
                    "status": "conflict",
                    "reasons": context_reasons,
                })

        if "BLUE CHIP" in classification or "TARGETED" in classification:
            spread_threshold = SELECTOR_CONFIG.get('spread_threshold_strong_signal', 3)
        else:
            spread_threshold = SELECTOR_CONFIG.get('spread_threshold_default', 4)
        spread_threshold_adjustments = []
        injury_threshold_bump = SELECTOR_CONFIG.get('injury_context_threshold_bump', 0)
        if injury_context_present and injury_threshold_bump:
            spread_threshold += injury_threshold_bump
            spread_threshold_adjustments.append({
                "reason": "injury context present",
                "delta": injury_threshold_bump,
            })
        total_threshold = SELECTOR_CONFIG.get('total_threshold', 4)

        spread_trace = {
            "market": "spread",
            "side": spread_side,
            "score": spread_score,
            "threshold": spread_threshold,
            "threshold_adjustments": spread_threshold_adjustments,
            "cleared_threshold": spread_score >= spread_threshold and spread_side in {'AWAY', 'HOME'},
            "requires_sharp_edge": SELECTOR_CONFIG.get('require_sharp_spread_edge', True),
            "has_sharp_edge": has_sharp_spread_edge,
            "blocked": spread_blocked or bool(spread_blockers),
            "blockers": sorted(set(spread_blockers)),
            "signals": spread_signals,
            "conflicts": spread_conflicts,
            "reasons": spread_reasons,
        }
        total_trace = {
            "market": "total",
            "side": total_side,
            "score": total_score,
            "threshold": total_threshold,
            "cleared_threshold": total_score >= total_threshold and total_side in {'OVER', 'UNDER'},
            "blocked": bool(total_blockers) and total_score == 0,
            "blockers": sorted(set(total_blockers)) if total_score == 0 else [],
            "signals": total_signals,
            "conflicts": total_conflicts,
            "reasons": total_reasons,
        }

        if spread_score < spread_threshold and total_score < total_threshold:
            return "⚠️ PASS: Edge score did not isolate a playable market", RecommendationSelector.pass_metadata(
                "no market cleared threshold",
                spread_trace,
                total_trace,
            )

        if total_score >= total_threshold and total_score > spread_score and total_side in {'OVER', 'UNDER'}:
            label = RecommendationSelector.label_for_score(total_score)
            rec = RecommendationSelector.format_total(total_side, total_num)
            return f"{label}: {rec}", RecommendationSelector.play_metadata(
                'total',
                total_side,
                total_score,
                total_reasons,
                spread_trace,
                total_trace,
            )

        if spread_score >= spread_threshold and spread_side in {'AWAY', 'HOME'}:
            label = RecommendationSelector.label_for_score(spread_score)
            rec = RecommendationSelector.format_spread(spread_side, away_team, home_team, spread_num)
            caution = " (proceed with caution)" if label == "👀 LEAN" else ""
            return f"{label}: {rec}{caution}", RecommendationSelector.play_metadata(
                'spread',
                spread_side,
                spread_score,
                spread_reasons,
                spread_trace,
                total_trace,
            )

        return "⚠️ PASS: No playable spread or total isolated", RecommendationSelector.pass_metadata(
            "no formatted candidate",
            spread_trace,
            total_trace,
        )

def canonical(team_raw: str) -> str:
    return canonical_team(team_raw)

def normalize_matchup(s: str) -> str:
    return normalize_matchup_key(s)

def analyze_injuries_with_team_mapping(away_team, home_team, action_injuries_df, rotowire_data=None):
    # 1. First, define the TLAs for the current game from the input team names
    away_tla = canonical(away_team)
    home_tla = canonical(home_team)
    
    away_injuries = []
    home_injuries = []
     
    if not action_injuries_df.empty:
        for _, injury in action_injuries_df.iterrows():
            team_name = injury['team']  # e.g. "Baltimore Ravens"
            
            # 2. Get the TLA of the injury record's team for comparison
            injury_tla = canonical(team_name)
            
            # 3. Use direct TLA comparison instead of 'in' substring search
            if injury_tla == away_tla:
                away_injuries.append({
                    'player': injury['player'],
                    'position': injury['pos'],
                    'status': injury['status'],
                    'team': team_name,
                    'team_tla': away_tla
                })
                debug_log(f"✅ Found away injury: {injury['player']} ({away_team})")
                
            elif injury_tla == home_tla:
                home_injuries.append({
                    'player': injury['player'],
                    'position': injury['pos'],
                    'status': injury['status'],
                    'team': team_name,
                    'team_tla': home_tla
                })
                debug_log(f"✅ Found home injury: {injury['player']} ({home_team})")

    if rotowire_data is not None and not rotowire_data.empty:
        try:
            rotowire_match = rotowire_data[
                (rotowire_data.get('away_std') == away_tla)
                & (rotowire_data.get('home_std') == home_tla)
            ]
            if not rotowire_match.empty:
                injury_str = rotowire_match.iloc[0].get('injuries', '')
                for injury in InjuryAnalyzer.parse_rotowire_injuries(injury_str):
                    candidate = {
                        'player': injury.get('player', ''),
                        'position': injury.get('position', ''),
                        'status': injury.get('status', ''),
                        'team': '',
                        'team_tla': '',
                        'source': 'rotowire'
                    }

                    analyzer = InjuryAnalyzer()
                    away_match = analyzer.enhanced_match_player(candidate['player'], away_tla)
                    home_match = analyzer.enhanced_match_player(candidate['player'], home_tla)

                    if away_match:
                        candidate['team'] = away_team
                        candidate['team_tla'] = away_tla
                        if not any(
                            existing['player'].lower() == candidate['player'].lower()
                            for existing in away_injuries
                        ):
                            away_injuries.append(candidate)
                    elif home_match:
                        candidate['team'] = home_team
                        candidate['team_tla'] = home_tla
                        if not any(
                            existing['player'].lower() == candidate['player'].lower()
                            for existing in home_injuries
                        ):
                            home_injuries.append(candidate)
        except Exception as e:
            print(f"⚠️ RotoWire injury merge failed for {away_tla}@{home_tla}: {e}")
    
    # ← THIS IS WHERE THE WHITELIST CODE SHOULD GO (OUTSIDE ALL LOOPS)
    debug_log(f"🔍 RAW DATA: {away_team} has {len(away_injuries)} injuries, {home_team} has {len(home_injuries)} injuries")
    
    # Apply whitelist filtering
    analyzer = InjuryAnalyzer()
    
    # Filter to whitelist-only injuries
    whitelist_away = []
    whitelist_home = []
    
    for injury in away_injuries:
        if analyzer.enhanced_match_player(injury['player'], injury['team_tla']):
            whitelist_away.append(injury)
    
    for injury in home_injuries:
        if analyzer.enhanced_match_player(injury['player'], injury['team_tla']):
            whitelist_home.append(injury)
    
    # Calculate impact using whitelist players only
    away_impact = analyzer.calculate_team_impact(whitelist_away, away_team)
    home_impact = analyzer.calculate_team_impact(whitelist_home, home_team)
    
    debug_log(f"🎯 WHITELIST: {away_team} has {len(whitelist_away)} high-impact injuries, {home_team} has {len(whitelist_home)} high-impact injuries")
    
    return {
        'away_injuries': whitelist_away,
        'home_injuries': whitelist_home,
        'away_impact': away_impact,
        'home_impact': home_impact,
        'score': home_impact - away_impact,
        'edge': 'EDGE' if abs(home_impact - away_impact) >= 2 else 'NO EDGE',
        'description': f"Found {len(whitelist_away + whitelist_home)} high-impact injuries",
        'factors': []
    }

# ================================================================
# SINGLE GAME ANALYSIS (REFRACTORED FOR PARALLELISM)
# ================================================================
def analyze_single_game(row, week, action, action_injuries, rotowire, referee_trends, weather=None):
    """
    Core deterministic single-game analysis.
    Input row → output dict
    """

    # ======================================================
    # STEP 0 — RAW INPUT
    # ======================================================
    # REPLACE the debug lines with this:
    debug_log(f"🔍 COLUMNS: {list(row.keys()) if hasattr(row, 'keys') else 'NO KEYS'}")
    debug_log(f"🔍 RAW ROW: {dict(row) if hasattr(row, 'items') else str(row)}")
    away_raw = getattr(row, 'away', '').strip()
    home_raw = getattr(row, 'home', '').strip()
    matchup_raw = getattr(row, 'matchup', '').strip()

    # ======================================================
    # STEP 1 — CANONICAL TEAMS
    # ======================================================
    away_tla = canonical(away_raw)
    home_tla = canonical(home_raw)

    away_full = TEAM_MAP.get(away_tla, away_tla)
    home_full = TEAM_MAP.get(home_tla, home_tla)

    # stable matchup key (NO lowercase, NO spaces)
    matchup_key = f"{away_tla}@{home_tla}"

    # ======================================================
    # STEP 2 — ACTION MATCHING (CANONICAL, STABLE)
    # ======================================================
    normalized_matchup = f"{away_tla}@{home_tla}"
    action_row = None
    
    if not action.empty:
        action_row = action[action['normalized_matchup'] == normalized_matchup]

    # ======================================================
    # STEP 3 — SHARP MONEY
    # ======================================================
    sharp_analysis = {
        'spread': {
            'differential': 0, 
            'score': 0, 
            'direction': 'NEUTRAL', 
            'bets_pct': 0, 
            'money_pct': 0, 
            'line': '', 
            'description': 'No data'
        },
        'total': {
            'differential': 0, 
            'score': 0, 
            'direction': 'NEUTRAL', 
            'bets_pct': 0, 
            'money_pct': 0, 
            'line': '', 
            'description': 'No data'
        },
        'moneyline': {
            'differential': 0, 
            'score': 0, 
            'direction': 'NEUTRAL', 
            'bets_pct': 0, 
            'money_pct': 0, 
            'line': '', 
            'description': 'No data'
        }
    }
    
    if action_row is not None and not action_row.empty:
        spread_data = action_row[action_row['Market'].str.contains("Spread", case=False)]
        total_data  = action_row[action_row['Market'].str.contains("Total", case=False)]
        ml_data     = action_row[action_row['Market'].str.contains("Money", case=False)]
        
        # Only update if we actually find data
        if not spread_data.empty:
            sharp_analysis['spread'] = SharpMoneyAnalyzer.analyze_market(spread_data, "Spread")
        if not total_data.empty:
            sharp_analysis['total'] = SharpMoneyAnalyzer.analyze_market(total_data, "Total")
        if not ml_data.empty:
            sharp_analysis['moneyline'] = SharpMoneyAnalyzer.analyze_market(ml_data, "Moneyline")
    # ======================================================
    # STEP 3.5 — SHARP STORIES (add after sharp analysis)
    # ======================================================
    sharp_stories = NarrativeEngine.generate_sharp_story(sharp_analysis)

    # ======================================================
    # STEP 4 — WEATHER (FIXED PATTERN)
    # ======================================================
    weather_analysis = {'score': 0, 'description': 'Good conditions', 'factors': []}
    
    # Load weather data from separate CSV file
    try:
        import os
        from datetime import datetime, timedelta
        
        # Try multiple dates around today (games could be today, tomorrow, or within a week)
        base_date = datetime.now()
        possible_files = []
        
        for days_offset in [3, 2, 1, 0, -1, -2, -3, -4, -5, -6, -7]:  # Try past week through next few days
            date_obj = base_date + timedelta(days=days_offset)
            possible_files.extend([
                f'data/action_weather_{date_obj.strftime("%Y-%m-%d")}_.csv',  # ✅ Added trailing underscore!
                f'data/action_weather_{date_obj.strftime("%Y-%m-%d")}.csv',   # Also try without
                f'data/action_weather_{date_obj.strftime("%m-%d-%Y")}_.csv',
                f'data/action_weather_{date_obj.strftime("%Y%m%d")}_.csv',
            ])
        
        # Also try generic names
        possible_files.extend([
            'data/action_weather.csv',
            'action_weather.csv'
        ])
        
        weather_df = weather if weather is not None and not weather.empty else None
        found_file = os.getenv("ACTION_WEATHER_FILE") if weather_df is not None else None
        
        # FIRST: Find and load the weather file if one was not provided by workflow/env
        if weather_df is None:
            for weather_file in possible_files:
                if os.path.exists(weather_file):
                    weather_df = pd.read_csv(weather_file)
                    found_file = weather_file
                    debug_log(f"✅ Found weather data: {weather_file} ({len(weather_df)} games)")
                    break
        
        # SECOND: Process the weather data if found
        if weather_df is not None and not weather_df.empty:
            # Create a mapping from weather CSV names to your TLA codes
            weather_to_tla = {
                'Rams': 'LAR', 'Seahawks': 'SEA',
                'Eagles': 'PHI', 'Commanders': 'WAS', 
                'Packers': 'GB', 'Bears': 'CHI',
                'Chiefs': 'KC', 'Titans': 'TEN',
                'Vikings': 'MIN', 'Giants': 'NYG',
                'Buccaneers': 'TB', 'Panthers': 'CAR',
                'Bills': 'BUF', 'Browns': 'CLE',
                'Bengals': 'CIN', 'Dolphins': 'MIA',
                'Jaguars': 'JAX', 'Broncos': 'DEN',
                'Patriots': 'NE', 'Ravens': 'BAL',
                'Jets': 'NYJ', 'Saints': 'NO',
                'Chargers': 'LAC', 'Cowboys': 'DAL',
                'Falcons': 'ATL', 'Cardinals': 'ARI',
                'Steelers': 'PIT', 'Lions': 'DET',
                'Raiders': 'LV', 'Texans': 'HOU',
                '49ers': 'SF', 'Colts': 'IND'
            }
            
            # Find matching game by converting weather team names to TLA codes
            weather_row = None
            for _, row in weather_df.iterrows():
                weather_away_tla = weather_to_tla.get(row['away'], '')
                weather_home_tla = weather_to_tla.get(row['home'], '')
                
                if (weather_away_tla == away_tla and weather_home_tla == home_tla):
                    weather_row = row
                    break
            
            if weather_row is not None:
                forecast = weather_row.get("forecast", "")
                precip = weather_row.get("precip", "")
                wind = weather_row.get("wind", "")
                
                weather_analysis = WeatherAnalyzer.analyze_from_csv_row(
                    forecast=forecast,
                    precip=precip, 
                    wind=wind
                )
                debug_log(f"🌦️ Weather for {away_tla}@{home_tla}: {weather_analysis['description']}")
            else:
                debug_log(f"❌ No weather match found for {away_tla}@{home_tla}")
        else:
            debug_log("❌ No weather file found")
                
    except Exception as e:
        print(f"⚠️ Weather analysis failed: {e}")
        weather_analysis = {'score': 0, 'description': 'Good conditions', 'factors': []}
    # ======================================================
    # STEP 5 — REFEREE
    # ======================================================
    referee_analysis = {
        'ats_score': 0, 
        'ou_score': 0, 
        'factors': [], 
        'ats_pct': 50.0, 
        'ou_pct': 50.0, 
        'referee': 'Data unavailable',
        'ats_tendency': 'NEUTRAL',
        'ou_tendency': 'NEUTRAL TOTAL'
    }
    try:
        referee_file = f"data/week{week}/week{week}_referees.csv"
        if os.path.exists(referee_file) and referee_trends is not None and not referee_trends.empty:
            referee_assignments = pd.read_csv(referee_file)
            
            away_full_name = TEAM_MAP.get(away_tla, away_tla)
            home_full_name = TEAM_MAP.get(home_tla, home_tla)

            away_nickname = away_full_name.split()[-1].lower()
            home_nickname = home_full_name.split()[-1].lower()

            referee_assignments['away_team_lower'] = referee_assignments['away_team'].astype(str).str.lower()
            referee_assignments['home_team_lower'] = referee_assignments['home_team'].astype(str).str.lower()
            
            match_condition_forward = (
                referee_assignments['away_team_lower'].str.contains(away_nickname, na=False)
            ) & (
                referee_assignments['home_team_lower'].str.contains(home_nickname, na=False)
            )

            game_match = referee_assignments[match_condition_forward]
            
            if game_match.empty:
                match_condition_reverse = (
                    referee_assignments['away_team_lower'].str.contains(home_nickname, na=False)
                ) & (
                    referee_assignments['home_team_lower'].str.contains(away_nickname, na=False)
                )
                game_match = referee_assignments[match_condition_reverse]

            if not game_match.empty:
                referee_name = game_match['referee'].iloc[0]
                
                # Find this referee's trend row from the historical referee context data.
                ref_row = referee_trends[referee_trends['query'].str.contains(referee_name, case=False, na=False)]
                
                if not ref_row.empty:
                    referee_analysis = RefereeAnalyzer.analyze(ref_row.iloc[0])
                    referee_analysis['referee'] = referee_name
                    if 'factors' not in referee_analysis:
                        referee_analysis['factors'] = []
                else:
                    referee_analysis = {
                        'ats_score': 0, 'ou_score': 0, 'factors': [], 
                        'ats_pct': 50.0, 'ou_pct': 50.0, 
                        'referee': referee_name, # Successfully found name, but no trend row
                        'ats_tendency':'NEUTRAL',
                        'ou_tendency': 'NEUTRAL TOTAL' 
                    }
            else:
                referee_analysis = {
                    'ats_score': 0, 'ou_score': 0, 'factors': [], 
                    'ats_pct': 50.0, 'ou_pct': 50.0, 
                    'referee': 'Game not found',
                    'ats_tendency': 'NEUTRAL',
                    'ou_tendency': 'NEUTRAL TOTAL' 
                }
        else:
            referee_analysis = {
                'ats_score': 0, 'ou_score': 0, 'factors': [], 
                'ats_pct': 50.0, 'ou_pct': 50.0, 
                'referee': 'Data unavailable',
                'ats_tendency': 'NEUTRAL', 
                'ou_tendency': 'NEUTRAL TOTAL' 
            }
    except Exception as e:
        referee_analysis = {
            'ats_score': 0, 'ou_score': 0, 'factors': [], 
            'ats_pct': 50.0, 'ou_pct': 50.0, 
            'referee': f'Error: {str(e)}',
            'ats_tendency': 'NEUTRAL', 
            'ou_tendency': 'NEUTRAL TOTAL' 
        }
    
    # STEP 6 — INJURIES (FIXED)
    try:
        injury_analysis = analyze_injuries_with_team_mapping(away_full, home_full, action_injuries, rotowire)
        if not injury_analysis.get('description'):
            injury_analysis['description'] = 'No significant injury impacts identified'
    except Exception as e:
        injury_analysis = {
            'score': 0,
            'edge': 'NO EDGE',
            'analysis': f"injury analyzer fail: {e}",
            'description': f"injury analyzer fail: {e}",
            'factors': [],
            'away_impact': [],  # ← Adding this missing field
            'home_impact': []   # ← Adding this missing field
        }
    # STEP 7 — SITUATIONAL
    situational_analysis = SituationalAnalyzer.analyze({
        'away': away_full,
        'home': home_full,
        'weather_analysis': weather_analysis,
        'spread_line': sharp_analysis['spread'].get('line', ""),
        'public_exposure': sharp_analysis['spread'].get('bets_pct', 50),
    }, week)
    
    # STEP 8 — ENHANCED STATISTICAL ANALYSIS
    # STEP 8 — ENHANCED STATISTICAL ANALYSIS (COMPLETE 2025 PLAYOFF DATA)
    try:
        def get_real_2025_team_stats(team_name):
            """Complete real 2025 NFL team statistics from SDQL queries"""
            
            # Complete Wild Card + Bye teams with real 2025 data
            nfl_2025_stats = {
                # Wild Card Teams (Complete)
                'Green Bay Packers': {
                    'ppg': 23.0, 'papg': 21.2, 'total_ypg': 357.8, 'total_yapg': 322.5, 'to_diff_per_game': 0.0
                },
                'Chicago Bears': {
                    'ppg': 25.9, 'papg': 24.4, 'total_ypg': 380.7, 'total_yapg': 368.0, 'to_diff_per_game': -1.3
                },
                'Los Angeles Rams': {
                    'ppg': 30.5, 'papg': 20.4, 'total_ypg': 405.2, 'total_yapg': 350.2, 'to_diff_per_game': -0.6
                },
                'Carolina Panthers': {
                    'ppg': 18.3, 'papg': 22.4, 'total_ypg': 312.2, 'total_yapg': 339.8, 'to_diff_per_game': 0.2
                },
                'San Francisco 49ers': {
                    'ppg': 25.7, 'papg': 21.8, 'total_ypg': 364.7, 'total_yapg': 354.1, 'to_diff_per_game': 0.4
                },
                'Philadelphia Eagles': {
                    'ppg': 22.3, 'papg': 19.1, 'total_ypg': 320.5, 'total_yapg': 333.5, 'to_diff_per_game': -0.3
                },
                'Houston Texans': {
                    'ppg': 23.8, 'papg': 17.4, 'total_ypg': 343.3, 'total_yapg': 293.7, 'to_diff_per_game': -1.0
                },
                'Pittsburgh Steelers': {
                    'ppg': 23.4, 'papg': 22.8, 'total_ypg': 311.9, 'total_yapg': 375.5, 'to_diff_per_game': -0.7
                },
                'Buffalo Bills': {
                    'ppg': 28.3, 'papg': 21.5, 'total_ypg': 392.2, 'total_yapg': 313.4, 'to_diff_per_game': -0.1  # 159.6+232.6, 136.2+177.1, 1.1-1.2
                },
                'Jacksonville Jaguars': {
                    'ppg': 27.9, 'papg': 19.8, 'total_ypg': 349.8, 'total_yapg': 323.7, 'to_diff_per_game': -0.7  # 115.1+234.7, 85.6+238.1, 1.1-1.8
                },
                'Los Angeles Chargers': {
                    'ppg': 21.6, 'papg': 20.0, 'total_ypg': 360.2, 'total_yapg': 304.0, 'to_diff_per_game': -0.2  # 121.6+238.6, 105.4+198.3, 1.2-1.4
                },
                'New England Patriots': {
                    'ppg': 28.8, 'papg': 18.8, 'total_ypg': 394.2, 'total_yapg': 311.6, 'to_diff_per_game': -0.2  # 128.9+265.3, 101.7+210.9, 0.9-1.1
                },
                # Bye Week Teams (Next Round)
                'Denver Broncos': {
                    'ppg': 23.6, 'papg': 18.3, 'total_ypg': 355.6, 'total_yapg': 308.0, 'to_diff_per_game': 0.2  # 118.7+236.9, 91.1+216.9, 1.0-0.8
                },
                'Seattle Seahawks': {
                    'ppg': 28.4, 'papg': 17.2, 'total_ypg': 362.3, 'total_yapg': 304.8, 'to_diff_per_game': 0.1  # 123.3+239.0, 91.9+212.9, 1.6-1.5
                }
            }
            
            return nfl_2025_stats.get(team_name, {
                'ppg': 22.5, 'papg': 22.5, 'total_ypg': 340.0, 'total_yapg': 340.0, 'to_diff_per_game': 0.0
            })
    
        def calculate_realistic_statistical_edge(away_stats, home_stats):
            """Calculate realistic statistical edge from real 2025 performance"""
            
            # Net scoring differential (offense - defense)
            away_net_scoring = away_stats['ppg'] - away_stats['papg']
            home_net_scoring = home_stats['ppg'] - home_stats['papg']
            
            # Yardage efficiency differential (converted to point equivalent)
            away_yard_eff = (away_stats['total_ypg'] - away_stats['total_yapg']) / 20.0  # ~20 yards per point
            home_yard_eff = (home_stats['total_ypg'] - home_stats['total_yapg']) / 20.0
            
            # Turnover impact (4 points per turnover differential)
            away_to_impact = away_stats['to_diff_per_game'] * 4.0
            home_to_impact = home_stats['to_diff_per_game'] * 4.0
            
            # Combined efficiency scores
            away_total_eff = away_net_scoring + away_yard_eff + away_to_impact
            home_total_eff = home_net_scoring + home_yard_eff + home_to_impact
            
            # Home field advantage (reduced for playoffs)
            home_advantage = 2.0
            
            # Net statistical edge (capped at realistic ±5.0 points)
            raw_edge = away_total_eff - (home_total_eff + home_advantage)
            return max(-5.0, min(5.0, raw_edge))
        
        # Get real team data
        away_stats = get_real_2025_team_stats(away_full)
        home_stats = get_real_2025_team_stats(home_full)
        
        # Calculate realistic statistical edge
        net_edge = calculate_realistic_statistical_edge(away_stats, home_stats)
        
        # Convert to analysis format
        if abs(net_edge) < 1.0:
            stat_score = 0
            description = 'No significant statistical edge'
        elif abs(net_edge) < 2.5:
            edge_team = away_full if net_edge > 0 else home_full
            stat_score = 1 if net_edge > 0 else -1
            description = f"Statistical edge to {edge_team} ({abs(net_edge):.1f} pts)"
        else:
            edge_team = away_full if net_edge > 0 else home_full
            stat_score = 2 if abs(net_edge) < 4.0 else 3
            stat_score = stat_score if net_edge > 0 else -stat_score
            description = f"Strong statistical edge to {edge_team} ({abs(net_edge):.1f} pts)"
        
        statistical_analysis = {
            'score': stat_score,
            'factors': [description] if stat_score != 0 else [],
            'description': description
        }
        
    except Exception as e:
        print(f"⚠️ Enhanced stats failed: {e}")
        statistical_analysis = {
            'score': 0,
            'factors': [],
            'description': 'Statistical analysis unavailable'
        }
    # STEP 9 — GAME THEORY
    game_theory_analysis = GameTheoryAnalyzer.analyze({
        'away': away_full,
        'home': home_full,
        'sharp_analysis': sharp_analysis,
        'public_exposure': sharp_analysis['spread'].get('bets_pct', 50),
    })
    
    # STEP 10 — SCHEDULE REST
    schedule_score, schedule_desc = calculate_schedule_score(week, home_tla, away_tla)
    schedule_analysis = {
        'score': schedule_score,
        'factors': [schedule_desc] if schedule_desc != "No significant scheduling factors" else [],
        'description': schedule_desc
    }

    # ======================================================
    # STEP 11 — SCORE
    # ======================================================
    # Directional factors use sign to indicate side/market, not quality. The
    # aggregate score measures edge strength; the selector decides the market.
    total_score = round(
        (
        FACTOR_WEIGHTS['sharp_consensus_score'] * abs(sharp_analysis['spread'].get('score', 0))
        + FACTOR_WEIGHTS['weather_score']       * max(weather_analysis.get('score', 0), 0)
        + FACTOR_WEIGHTS['referee_ats_score']   * abs(referee_analysis.get('ats_score', 0))
        + FACTOR_WEIGHTS['referee_ou_score']    * abs(referee_analysis.get('ou_score', 0))
        + FACTOR_WEIGHTS['injury_score']        * abs(injury_analysis.get('score', 0))
        + FACTOR_WEIGHTS['situational_score']   * situational_analysis.get('score', 0)
        + FACTOR_WEIGHTS['statistical_score']   * statistical_analysis['score']
        + FACTOR_WEIGHTS['game_theory_score']   * game_theory_analysis.get('score', 0)
        + FACTOR_WEIGHTS['schedule_score']      * abs(schedule_analysis['score'])
    ),
    1
    )
    signal_classification, signal_recommendation_label, signal_tier_score = ClassificationEngine.classify_game({
        'total_score': total_score,
        'sharp_consensus_score': sharp_analysis['spread'].get('score', 0),
        'referee_analysis': referee_analysis,
        'injury_analysis': injury_analysis,
        'public_exposure': sharp_analysis['spread'].get('bets_pct', 50),
    })
    
    recommendation, pick_metadata = RecommendationSelector.select(
        signal_classification,
        {
            'away': away_full,
            'home': home_full,
            'sharp_analysis': sharp_analysis,
            'referee_analysis': referee_analysis,
            'weather_analysis': weather_analysis,
            'injury_analysis': injury_analysis,
            'statistical_analysis': statistical_analysis,
            'public_exposure': sharp_analysis['spread'].get('bets_pct', 50)
        }
    )
    classification, recommendation_label, tier_score = RecommendationSelector.classification_for_pick(pick_metadata)
    recommendation_trace = pick_metadata.get('trace', {})

    return {
        'matchup': f"{away_full} @ {home_full}",
        'matchup_key': matchup_key,
        'away': away_full,
        'home': home_full,
        'away_tla': away_tla,
        'home_tla': home_tla,
        'classification': classification,
        'classification_label': recommendation_label,
        'signal_classification': signal_classification,
        'signal_classification_label': signal_recommendation_label,
        'signal_tier_score': signal_tier_score,
        'recommendation': recommendation,
        'pick_metadata': pick_metadata,
        'recommendation_trace': recommendation_trace,
        'model_version': MODEL_VERSION,
        'tier_score': tier_score,
        'total_score': total_score,
        'confidence': round(abs(total_score),1),
        'sharp_analysis': sharp_analysis,
        'weather_analysis': weather_analysis,
        'referee_analysis': referee_analysis,
        'injury_analysis': injury_analysis,
        'situational_analysis': situational_analysis,
        'statistical_analysis': statistical_analysis,
        'game_theory_analysis': game_theory_analysis,
        'schedule_analysis': schedule_analysis,
        'sharp_stories': sharp_stories,
    }

# ================================================================
# MAIN ANALYSIS ENGINE
# ================================================================

def analyze_week(week):
    """Main analysis pipeline"""
    season_type = StatisticalAnalyzer.default_season_type(week)
    
    print(f"\n{'='*70}")
    print(f"NFL {season_type} WEEK {week} PROFESSIONAL ANALYSIS ENGINE")
    print(f"{'='*70}\n")
    
    # Load data
    print("📥 Loading data sources...")
    queries = safe_load_csv(f"data/week{week}/week{week}_queries.csv", required=True)
    queries["away_std"] = queries["away"].apply(canonical)
    queries["home_std"] = queries["home"].apply(canonical)
    queries["normalized_matchup"] = queries["matchup"].apply(normalize_matchup)

    referee_trends_file = os.getenv("REFEREE_TRENDS_FILE", "data/historical/sdql_results.csv")
    referee_trends = safe_load_csv(referee_trends_file)

    if queries.empty:
        print("❌ No games found")
        return

    # Load Action Network data
    action_file_path = exact_file_or_latest("ACTION_MARKETS_FILE", "action_all_markets_")
    action = safe_load_csv(action_file_path) if action_file_path else pd.DataFrame()
    action_raw = action.copy()
    # Load Action Network injuries
    action_injuries_path = exact_file_or_latest("ACTION_INJURIES_FILE", "action_injuries_")
    action_injuries = safe_load_csv(action_injuries_path) if action_injuries_path else pd.DataFrame()
    action_injuries_raw = action_injuries.copy()
    if not action_injuries.empty:
        print(f"  ✓ Loaded {len(action_injuries)} injury records from Action Network")
    else:
        print(f"  ⚠️ No Action Network injury data")
    
    # Set up time tracking
    now = analysis_reference_time()
    
    # Standardize game time column
    if not action.empty and "Game Time" in action.columns:
        action["game_time"] = action["Game Time"]
    
    # Detect and remove completed games
    #final_games = set()
    #if not action.empty:
    #    action["normalized_matchup"] = action["Matchup"].apply(normalize_matchup)
    #   action["normalized_matchup"] = action["normalized_matchup"].str.strip()
        
        # Better filtering that catches all completed games
        ##final_games = set(
        #    action[action["game_time"].astype(str).str.contains("Final", na=False)]["normalized_matchup"]
        #)
        
        #if final_games:
        #    print(f"🧹 Detected {len(final_games)} completed games")
            # Remove completed games from Action data
        #   action = action[~action["normalized_matchup"].isin(final_games)].copy()
    
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

    weather_file = exact_file_or_latest("ACTION_WEATHER_FILE", "action_weather_")
    weather = safe_load_csv(weather_file) if weather_file else pd.DataFrame()
    weather_raw = weather.copy()
    if not weather.empty:
        print(f"  ✓ Loaded {len(weather)} weather records from {weather_file}")
    else:
        print(f"  ⚠️ No Action Network weather data")

    # Load supplemental data
    rotowire_file = exact_file_or_latest("ROTOWIRE_FILE", "rotowire_lineups_")
    rotowire = safe_load_csv(rotowire_file) if rotowire_file else pd.DataFrame()
    rotowire_raw = rotowire.copy()
    data_quality = build_data_quality_report(week, {
        "queries": {"path": f"data/week{week}/week{week}_queries.csv", "df": queries, "required": True},
        "referee_trends": {"path": referee_trends_file, "df": referee_trends, "required": False},
        "action_markets": {"path": action_file_path, "df": action_raw, "required": True},
        "action_injuries": {"path": action_injuries_path, "df": action_injuries_raw, "required": False},
        "action_weather": {"path": weather_file, "df": weather_raw, "required": False},
        "rotowire": {"path": rotowire_file, "df": rotowire_raw, "required": False},
    })
    if data_quality["status"] != "OK":
        print(f"⚠️ Data quality status: {data_quality['status']}")
        for warning in data_quality["critical_warnings"] + data_quality["warnings"]:
            print(f"  - {warning}")

    # Prepare rotowire data
    if not rotowire.empty:
        rotowire['home_std'] = rotowire['home'].apply(canonical)
        rotowire['away_std'] = rotowire['away'].apply(canonical)
    
    # Merge base data
    final = queries.merge(referee_trends, on='query', how='left') if not referee_trends.empty else queries
    final["normalized_matchup"] = final["matchup"].apply(normalize_matchup)
    
    # Filter out completed games
    #before_filter = len(final)
    #final = final[~final["normalized_matchup"].isin(final_games)].copy()
    #completed_removed = before_filter - len(final)
    #
    # Filter out games that have already started
    #if kickoff_lookup:
    #    time_filtered = []
    #    for _, row in final.iterrows():
    #        kickoff = kickoff_lookup.get(row.get("normalized_matchup", ""))
    #        # Keep games with no kickoff time (safer) or future kickoff times
    #        if kickoff is None or pd.isna(kickoff) or kickoff > now:
    #            time_filtered.append(True)
    #        else:
    #            time_filtered.append(False)
    #    
    #    before_time = len(final)
    #    final = final[time_filtered].copy()
    #    started_removed = before_time - len(final)
    #else:
    #    started_removed = 0
   # 
   # if completed_removed or started_removed:
   #     print(f"🧹 Filtered out {completed_removed} completed + {started_removed} started games")

    # Process each game IN PARALLEL
    games = []
    num_games = len(final)
    print(f"\n🔬 Analyzing {num_games} games in parallel...\n")
    
    # Use partial to 'lock in' the arguments that are constant for all games
    analyzer = partial(
        analyze_single_game, 
        week=week, 
        action=action, 
        action_injuries=action_injuries, 
        rotowire=rotowire,
        referee_trends=referee_trends,
        weather=weather
    )

    # Use ThreadPoolExecutor to run the single-game analysis concurrently
    # Max workers set to 8, which is generally efficient for I/O and processing
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Use .itertuples() to efficiently iterate over rows as namedtuples
        # The executor will handle collecting the results from the threads
        game_analyses = executor.map(analyzer, final.itertuples(index=False))
        
        # Collect and print results as they complete
        for game_analysis in game_analyses:
            game_analysis["season_type"] = season_type
            game_analysis["data_quality"] = data_quality
            game_analysis = apply_source_safety_policy(game_analysis, data_quality)
            games.append(game_analysis)
            # Printing inside the loop provides real-time feedback on completion
            print(f"  ✓ {game_analysis['matchup']}: {game_analysis['classification']} (Score: {game_analysis['total_score']:+.1f})")

    # Sort games by tier (UNCHANGED)
    tier_order = {
        '🔵 BLUE CHIP': 1,
        '🎯 TARGETED PLAY': 2,
        '📊 LEAN': 3,
        '🚨 TRAP GAME': 4,
        '⚠️ PASS': 5,
        '⚠️ LANDMINE': 6,
        '❌ FADE': 7
    }
    games.sort(key=lambda x: (tier_order.get(x['classification'], 99), -x['confidence']))
    
    # Generate outputs (UNCHANGED)
    print(f"\n📝 Generating reports...")
    output_dir = os.getenv("ANALYZER_OUTPUT_DIR")
    generate_outputs(week, games, output_dir=output_dir)
    
    print(f"\n✅ Analysis complete!\n")

    # After generating outputs, log performance tracking (UNCHANGED)
    if os.getenv("SKIP_PERFORMANCE_TRACKING") == "1" or output_dir:
        print("📊 Performance tracking skipped for replay/output-dir run")
    else:
        try:
            from performance_tracker import EnhancedPerformanceTracker
            tracker = EnhancedPerformanceTracker()
            tracker.log_week_recommendations(week, f"data/week{week}/week{week}_analytics.json")
            print(f"📊 Performance tracking logged for Week {week}")
        except Exception as e:
            print(f"⚠️ Performance tracking failed: {e}")
       

def generate_outputs(week, games, output_dir=None):
    """Generate all output files"""
    season_type = StatisticalAnalyzer.default_season_type(week)
    
    # Create week directory
    week_dir = output_dir or f"data/week{week}"
    os.makedirs(week_dir, exist_ok=True)
    
    print(f"📝 Generating reports for {len(games)} games...")
    data_quality = games[0].get('data_quality', {}) if games else {}
    run_manifest = {
        "week": week,
        "season_type": season_type,
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_reference_time": analysis_reference_time().isoformat(),
        "analysis_target_date": os.getenv("ANALYZER_TARGET_DATE", ""),
        "output_dir": week_dir,
        "game_count": len(games),
        "play_count": sum(1 for game in games if game.get("pick_metadata", {}).get("market") not in (None, "none")),
        "pass_count": sum(1 for game in games if game.get("pick_metadata", {}).get("market") in (None, "none")),
        "data_quality": data_quality,
        "input_files": manifest_input_files(data_quality),
        "config": {
            "factor_weights": FACTOR_WEIGHTS,
            "selector": SELECTOR_CONFIG,
            "source_quality": SOURCE_QUALITY_CONFIG,
        },
        "environment": {
            "NFL_SEASON": os.getenv("NFL_SEASON", ""),
            "NFL_SEASON_TYPE": season_type,
            "NFL_MODEL_CONFIG": os.getenv("NFL_MODEL_CONFIG", "config/model_config.json"),
            "ACTION_MARKETS_FILE": os.getenv("ACTION_MARKETS_FILE", ""),
            "ACTION_INJURIES_FILE": os.getenv("ACTION_INJURIES_FILE", ""),
            "ACTION_WEATHER_FILE": os.getenv("ACTION_WEATHER_FILE", ""),
            "ROTOWIRE_FILE": os.getenv("ROTOWIRE_FILE", ""),
            "REFEREE_TRENDS_FILE": os.getenv("REFEREE_TRENDS_FILE", ""),
        }
    }
    source_health = build_source_health(run_manifest)
    
    # Executive Summary
    with open(f"{week_dir}/week{week}_executive_summary.txt", "w") as f:
        f.write(f"NFL {season_type} WEEK {week} - EXECUTIVE SUMMARY\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
        f.write("="*70 + "\n\n")
        if games and games[0].get('data_quality', {}).get('status') != "OK":
            dq = games[0]['data_quality']
            f.write(f"DATA QUALITY: {dq.get('status', 'UNKNOWN')}\n")
            f.write("-"*70 + "\n")
            if dq.get('unsafe_sources'):
                f.write(f"  Unsafe Sources: {', '.join(dq['unsafe_sources'])}\n")
            if dq.get('degraded_sources'):
                f.write(f"  Degraded Sources: {', '.join(dq['degraded_sources'])}\n")
            for warning in dq.get('critical_warnings', []) + dq.get('warnings', []):
                f.write(f"  - {warning}\n")
            f.write("\n")
        
        # Group by tier
        tiers = defaultdict(list)
        for game in games:
            tiers[game['classification']].append(game)
        
        # Updated to match actual classifications + enhanced details
        for tier_name in ['🔵 BLUE CHIP', '🎯 TARGETED PLAY', '📊 LEAN', '⚠️ PASS', '⚠️ LANDMINE', '❌ FADE']:
            if tier_name in tiers:
                f.write(f"{tier_name}\n")
                f.write("-"*70 + "\n")
                for game in tiers[tier_name]:
                    f.write(f"{game['matchup']}\n")
                    f.write(f"  → {game['recommendation']}\n")
                    
                    # Enhanced details from pro analysis
                    if game['sharp_stories']:
                        f.write(f"  → {game['sharp_stories'][0]}\n")
                    
                    # Add referee context
                    if game.get('referee_analysis'):
                        ref = game['referee_analysis']
                        f.write(f"  → Referee: {ref.get('referee', 'Unknown')} ({ref.get('ats_pct', 'N/A')}% ATS, {ref.get('ats_tendency', 'N/A')})\n")
                    
                    # Add key statistical or injury info
                    if game.get('statistical_analysis', {}).get('factors'):
                        stat = game['statistical_analysis']['factors'][0]
                        f.write(f"  → {stat}\n")
                    elif game.get('injury_analysis', {}).get('description'):
                        injury = game['injury_analysis']['description']
                        f.write(f"  → Injury Impact: {injury}\n")
                    
                    # Add score for quick reference  
                    f.write(f"  → Score: {game.get('total_score', 'N/A')} | Confidence: {game.get('confidence', 'N/A')}\n")
                    pick_meta = game.get('pick_metadata', {})
                    if pick_meta.get('market') and pick_meta.get('market') != 'none':
                        reasons = ', '.join(pick_meta.get('reasons', [])[:2])
                        f.write(f"  → Pick Basis: {pick_meta.get('market').title()} ({reasons})\n")
                    f.write("\n")
    
    # Full Analysis
    with open(f"{week_dir}/week{week}_pro_analysis.txt", "w") as f:
        f.write(f"NFL {season_type} WEEK {week} - PROFESSIONAL ANALYSIS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
        f.write("="*70 + "\n\n")
        
        for game in games:
            f.write(NarrativeEngine.generate_game_narrative(game))
            f.write("\n\n" + "="*70 + "\n\n")
    
    # Analytics CSV
    data_rows = []
    audit_rows = []
    for game in games:
        pick_meta = game.get('pick_metadata', {})
        trace = game.get('recommendation_trace', {})
        spread_trace = (trace.get('market_candidates') or {}).get('spread') or {}
        total_trace = (trace.get('market_candidates') or {}).get('total') or {}
        final_trace = trace.get('final_decision') or {}
        audit_rows.append({
            'matchup': game['matchup'],
            'season_type': season_type,
            'classification': game['classification'],
            'signal_classification': game.get('signal_classification', ''),
            'data_quality_status': game.get('data_quality', {}).get('status', ''),
            'unsafe_sources': ', '.join(game.get('data_quality', {}).get('unsafe_sources', [])),
            'degraded_sources': ', '.join(game.get('data_quality', {}).get('degraded_sources', [])),
            'recommendation': game.get('recommendation', ''),
            'pick_market': pick_meta.get('market', ''),
            'pick_side': pick_meta.get('side', ''),
            'selector_score': pick_meta.get('score', ''),
            'source_blocked_market': pick_meta.get('blocked_market', ''),
            'source_blocked_side': pick_meta.get('blocked_side', ''),
            'source_blocked_score': pick_meta.get('blocked_score', ''),
            'source_blocked_recommendation': game.get('source_blocked_recommendation', ''),
            'spread_candidate_score': pick_meta.get('spread_score', ''),
            'total_candidate_score': pick_meta.get('total_score', ''),
            'pass_reason': pick_meta.get('reason', ''),
            'selector_reasons': '; '.join(pick_meta.get('reasons', [])),
            'trace_final_market': final_trace.get('market', ''),
            'trace_final_side': final_trace.get('side', ''),
            'trace_final_reason': final_trace.get('reason', ''),
            'trace_spread_side': spread_trace.get('side', ''),
            'trace_spread_threshold': spread_trace.get('threshold', ''),
            'trace_spread_cleared': spread_trace.get('cleared_threshold', ''),
            'trace_spread_blockers': '; '.join(spread_trace.get('blockers', [])),
            'trace_spread_signals': '; '.join(
                f"{signal.get('source')}:{signal.get('side')}:{signal.get('impact')}"
                for signal in spread_trace.get('signals', [])
            ),
            'trace_spread_conflicts': '; '.join(
                f"{signal.get('source')}:{signal.get('side')}:{signal.get('impact')}"
                for signal in spread_trace.get('conflicts', [])
            ),
            'trace_total_side': total_trace.get('side', ''),
            'trace_total_threshold': total_trace.get('threshold', ''),
            'trace_total_cleared': total_trace.get('cleared_threshold', ''),
            'trace_total_blockers': '; '.join(total_trace.get('blockers', [])),
            'trace_total_signals': '; '.join(
                f"{signal.get('source')}:{signal.get('side')}:{signal.get('impact')}"
                for signal in total_trace.get('signals', [])
            ),
            'trace_total_conflicts': '; '.join(
                f"{signal.get('source')}:{signal.get('side')}:{signal.get('impact')}"
                for signal in total_trace.get('conflicts', [])
            ),
            'aggregate_score': game['total_score'],
            'sharp_spread_direction': game['sharp_analysis'].get('spread', {}).get('direction', ''),
            'sharp_spread_score': game['sharp_analysis'].get('spread', {}).get('score', 0),
            'sharp_total_direction': game['sharp_analysis'].get('total', {}).get('direction', ''),
            'sharp_total_score': game['sharp_analysis'].get('total', {}).get('score', 0),
            'statistical_score': game['statistical_analysis']['score'],
            'injury_score': game['injury_analysis']['score'],
            'referee_ats_score': game['referee_analysis'].get('ats_score', 0),
            'referee_ou_score': game['referee_analysis'].get('ou_score', 0),
            'weather_score': game['weather_analysis']['score'],
            'data_quality_warnings': '; '.join(game.get('data_quality', {}).get('warnings', [])),
            'data_quality_critical_warnings': '; '.join(game.get('data_quality', {}).get('critical_warnings', [])),
        })
        data_rows.append({
            'matchup': game['matchup'],
            'season_type': season_type,
            'model_version': game.get('model_version', MODEL_VERSION),
            'classification': game['classification'],
            'signal_classification': game.get('signal_classification', ''),
            'data_quality_status': game.get('data_quality', {}).get('status', ''),
            'unsafe_sources': ', '.join(game.get('data_quality', {}).get('unsafe_sources', [])),
            'degraded_sources': ', '.join(game.get('data_quality', {}).get('degraded_sources', [])),
            'data_quality_warnings': '; '.join(game.get('data_quality', {}).get('warnings', [])),
            'data_quality_critical_warnings': '; '.join(game.get('data_quality', {}).get('critical_warnings', [])),
            'total_score': game['total_score'],
            'confidence': game['confidence'],
            'pick_market': game.get('pick_metadata', {}).get('market', ''),
            'pick_side': game.get('pick_metadata', {}).get('side', ''),
            'pick_basis': '; '.join(game.get('pick_metadata', {}).get('reasons', [])),
            'recommendation_trace_summary': (
                f"spread {spread_trace.get('side', 'NA')} {spread_trace.get('score', 'NA')}/"
                f"{spread_trace.get('threshold', 'NA')} | total {total_trace.get('side', 'NA')} "
                f"{total_trace.get('score', 'NA')}/{total_trace.get('threshold', 'NA')} | "
                f"final {final_trace.get('market', 'none')} {final_trace.get('side') or ''}"
            ),
            'sharp_spread_diff': game['sharp_analysis'].get('spread', {}).get('differential', 0),
            'sharp_total_diff': game['sharp_analysis'].get('total', {}).get('differential', 0),
            'ref_ats_pct': game['referee_analysis'].get('ats_pct', 50),
            'ref_ou_pct': game['referee_analysis'].get('ou_pct', 50),
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
    
    pd.DataFrame(data_rows).to_csv(f"{week_dir}/week{week}_analytics.csv", index=False)
    pd.DataFrame(audit_rows).to_csv(f"{week_dir}/week{week}_selector_audit.csv", index=False)
    
    # JSON export
    with open(f"{week_dir}/week{week}_analytics.json", "w") as f:
        json.dump(games, f, indent=2, default=str)
    with open(f"{week_dir}/week{week}_run_manifest.json", "w") as f:
        json.dump(run_manifest, f, indent=2, default=str)
    with open(f"{week_dir}/week{week}_source_health.json", "w") as f:
        json.dump(source_health, f, indent=2, default=str)
    write_source_health_text(f"{week_dir}/week{week}_source_health.txt", source_health)
    
    print(f"  ✓ week{week}_executive_summary.txt")
    print(f"  ✓ week{week}_pro_analysis.txt")
    print(f"  ✓ week{week}_analytics.csv")
    print(f"  ✓ week{week}_selector_audit.csv")
    print(f"  ✓ week{week}_analytics.json")
    print(f"  ✓ week{week}_run_manifest.json")
    print(f"  ✓ week{week}_source_health.json")
    print(f"  ✓ week{week}_source_health.txt")


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    import sys
    # Handle both numeric weeks (1-18) and playoff codes (WC, DIV, CONF, SB)
    week_arg = sys.argv[1] if len(sys.argv) > 1 else "11"
    try:
        week = int(week_arg)
    except ValueError:
        week = week_arg  # Keep as string for playoffs
    analyze_week(week)
