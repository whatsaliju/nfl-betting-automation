# Universal NFL Weekly Tracker

**A comprehensive system to track NFL betting performance for any week, past or present.**

## Quick Start

### Method 1: Simple Python Usage
```python
from universal_weekly_tracker import UniversalWeeklyTracker

tracker = UniversalWeeklyTracker()

# Process any week (auto: log + update + report)
tracker.process_week(week=12, action='auto')
```

### Method 2: Command Line
```bash
# Process Week 12 fully automatically
python universal_weekly_tracker.py 12

# Update Week 11 results only
python universal_weekly_tracker.py 11 update

# Generate Week 10 report
python universal_weekly_tracker.py 10 report
```

### Method 3: Interactive Mode
```bash
python universal_weekly_tracker.py
# Then follow the prompts
```

## Available Actions

| Action | Description | When to Use |
|--------|-------------|-------------|
| `auto` | Log recommendations + update results + report | Most common - handles everything |
| `update` | Fetch NFL scores and update win/loss | When recommendations already logged |
| `report` | Generate performance report | View results without updating |
| `log` | Log recommendations from analytics JSON | New week with fresh analytics |
| `manual` | Show manual update commands | When auto-update fails |

## File Structure Expected

```
data/
├── historical/
│   ├── betting_results.csv          # Your main tracking file
│   └── performance_analysis.json    # Analysis cache
└── week{N}/
    └── week{N}_analytics.json       # Your weekly analytics
```

## Common Use Cases

### 1. Weekly Workflow (New Week)
```python
# Week 13 just finished analysis
tracker.process_week(13, 'log', analytics_file='week13_analytics.json')

# Later, when games finish
tracker.process_week(13, 'update')
```

### 2. Catch Up on Past Weeks
```python
# Process weeks 10-12 all at once
for week in [10, 11, 12]:
    tracker.process_week(week, 'auto')
```

### 3. Manual Updates When Needed
```python
# If auto-update fails, update manually
tracker.manual_update(12, 'Chiefs @ Bills', 'KC 31-17', won=True)
tracker.manual_update(12, 'Lions @ Packers', 'GB 30-17', won=False)
```

### 4. Performance Analysis
```python
# Generate reports for recent weeks
for week in [10, 11, 12]:
    tracker.process_week(week, 'report')
```

## Key Features

### 🤖 **Automatic Score Fetching**
- Pulls live NFL scores from ESPN API
- Matches your bets to actual game results
- Handles team name variations automatically

### 🎯 **Smart Bet Evaluation**
- Parses your recommendations to understand spreads/totals
- Calculates wins/losses/pushes automatically
- Handles combination bets (spread + total)

### 📊 **Comprehensive Reporting**
- Win rates by classification (Blue Chip, Targeted, Lean)
- Game-by-game analysis with reasoning
- Performance trends across weeks

### 🔧 **Flexible Usage**
- Works for any week (past, present, future prep)
- Command line or Python import
- Manual override when auto-update fails

## Troubleshooting

### "No analytics file found"
- Ensure your `week{N}_analytics.json` file is in the right location
- Or specify the path: `tracker.process_week(12, 'log', analytics_file='/path/to/file.json')`

### "Could not fetch NFL scores"
- Games may not be completed yet
- Use manual update: `tracker.process_week(12, 'manual')` for instructions

### "Game not found"
- Team name mismatch between your data and ESPN
- Use manual update with exact game name from your recommendations

## Integration with Your System

This tracker is designed to work with your existing workflow:

1. **GitHub Actions** generate `week{N}_analytics.json`
2. **Universal Tracker** logs recommendations and updates results
3. **Performance analysis** feeds back into future improvements

The system maintains your existing data structure while adding enhanced automation and reporting capabilities.

## Examples

See `weekly_tracker_examples.py` for comprehensive usage examples including:
- Processing multiple weeks
- Season-long analysis
- Interactive mode
- Command line usage
- Manual update workflows
