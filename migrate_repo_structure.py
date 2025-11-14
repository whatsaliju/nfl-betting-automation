#!/usr/bin/env python3
"""
Repository Restructuring Migration Script
==========================================
Reorganizes the NFL betting automation repo into a clean folder structure.

Run this ONCE to migrate existing files to new structure.
"""

import os
import shutil
import glob
from pathlib import Path

# Define new structure
STRUCTURE = {
    'scrapers': [
        'football_zebras_scraper.py',
        'action_network_scraper_cookies.py',
        'action_network_injuries_weather.py',
        'rotowire_scraper.py',
        'sdql_test.py'
    ],
    'analyzers': [
        'query_generator.py',
        'query_generator_v2.py',
        'nfl_pro_analyzer.py',
        'nfl_weekly_analyzer.py',
        'referee_trend_generator.py',
        'enhanced_report_generator.py',
        'generate_ai_summary.py'
    ],
    'config': [
        'action_network_cookies.json'
    ],
    'data': []  # Will organize week-specific data
}

def create_folder_structure():
    """Create the new folder structure"""
    print("📁 Creating folder structure...")
    
    folders = [
        'scrapers',
        'analyzers',
        'config',
        'data',
        'data/historical'
    ]
    
    for folder in folders:
        Path(folder).mkdir(exist_ok=True)
        print(f"  ✓ Created {folder}/")
    
    print()

def move_scripts():
    """Move Python scripts to appropriate folders"""
    print("📦 Moving scripts...")
    
    for folder, files in STRUCTURE.items():
        if folder == 'data':
            continue
            
        for file in files:
            if os.path.exists(file):
                dest = f"{folder}/{file}"
                shutil.move(file, dest)
                print(f"  ✓ {file} → {dest}")
            else:
                print(f"  ⚠️  {file} not found (skipping)")
    
    print()

def organize_week_data():
    """Organize week-specific data files into week folders"""
    print("📊 Organizing week data...")
    
    # Find all week files
    week_files = glob.glob('week*_*')
    
    # Group by week number
    weeks = {}
    for file in week_files:
        try:
            week_num = file.split('week')[1].split('_')[0]
            if week_num not in weeks:
                weeks[week_num] = []
            weeks[week_num].append(file)
        except:
            continue
    
    # Move files to week folders
    for week, files in weeks.items():
        week_folder = f"data/week{week}"
        Path(week_folder).mkdir(exist_ok=True)
        
        for file in files:
            dest = f"{week_folder}/{file}"
            shutil.move(file, dest)
            print(f"  ✓ {file} → {dest}")
    
    print()

def organize_market_data():
    """Move market data CSVs to data folder"""
    print("📈 Organizing market data...")
    
    patterns = [
        'action_all_markets_*.csv',
        'action_injuries_*.csv',
        'action_weather_*.csv',
        'rotowire_lineups_*.csv'
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        for file in files:
            # Extract date from filename
            try:
                date_part = file.split('_')[-1].replace('.csv', '')
                dest = f"data/market_data_{date_part}.csv"
                shutil.copy(file, dest)  # Copy not move, in case still needed
                print(f"  ✓ {file} → {dest}")
            except:
                continue
    
    print()

def move_historical_data():
    """Move historical/persistent data"""
    print("📚 Moving historical data...")
    
    historical_files = [
        'sdql_results.csv',
        'betting_history.csv'
    ]
    
    for file in historical_files:
        if os.path.exists(file):
            dest = f"data/historical/{file}"
            shutil.move(file, dest)
            print(f"  ✓ {file} → {dest}")
    
    print()

def create_readme():
    """Create README for new structure"""
    print("📝 Creating README...")
    
    readme_content = """# NFL Betting Automation

Automated NFL betting analysis system with sharp money tracking, referee trends, and line movement detection.

## 📁 Repository Structure

```
├── scrapers/           # Data collection scripts
├── analyzers/          # Analysis and report generation
├── config/             # Configuration files (cookies, etc.)
├── data/              # All data outputs
│   ├── week{X}/       # Week-specific data
│   └── historical/    # Historical tracking data
└── .github/workflows/ # GitHub Actions workflows
```

## 🚀 Quick Start

**Run Analysis for Current Week:**
```bash
# Workflows run automatically on schedule
# Or manually trigger via GitHub Actions
```

## 📊 Workflows

1. **Referee Collection** - Wed 6 PM ET
2. **Initial Market Data** - After workflow 1
3. **Market Update** - Thu/Sat/Sun (manual)
4. **Pro Analysis** - After workflows 2 & 3

## 📧 Output

Analysis reports emailed automatically with:
- Executive Summary (top plays)
- Pro Analysis (full narratives)
- Sharp money intelligence
- Line movement alerts

## 🔧 Configuration

Add these secrets in GitHub Settings:
- `GIMMETHEDOG_EMAIL` / `GIMMETHEDOG_PASSWORD`
- `ODDS_API_KEY`
- `ACTION_NETWORK_COOKIES`
- `GMAIL_USERNAME` / `GMAIL_APP_PASSWORD`
"""
    
    with open('README.md', 'w') as f:
        f.write(readme_content)
    
    print("  ✓ Created README.md")
    print()

def create_gitignore():
    """Create/update .gitignore"""
    print("🔒 Updating .gitignore...")
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv

# Data files (optional - keep if you want data in repo)
# data/
# *.csv

# Config
config/action_network_cookies.json

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("  ✓ Updated .gitignore")
    print()

def main():
    print("="*70)
    print("NFL BETTING AUTOMATION - REPOSITORY RESTRUCTURING")
    print("="*70)
    print()
    
    # Confirm
    response = input("This will reorganize your repository. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Migration cancelled")
        return
    
    print()
    
    # Execute migration
    create_folder_structure()
    move_scripts()
    organize_week_data()
    organize_market_data()
    move_historical_data()
    create_readme()
    create_gitignore()
    
    print("="*70)
    print("✅ MIGRATION COMPLETE!")
    print("="*70)
    print()
    print("📋 Next Steps:")
    print("1. Update workflow files with new paths (see update guide)")
    print("2. Test each workflow to ensure paths are correct")
    print("3. Commit the new structure to GitHub")
    print()
    print("⚠️  NOTE: You'll need to update import paths in workflows!")
    print()

if __name__ == "__main__":
    main()
