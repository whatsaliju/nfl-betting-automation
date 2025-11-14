# Workflow Path Update Guide

After running `migrate_repo_structure.py`, you need to update paths in your workflows and scripts.

## Required Changes

### 1. Workflow Files (in `.github/workflows/`)

Update Python script calls to use new paths:

**Before:**
```yaml
python3 football_zebras_scraper.py
```

**After:**
```yaml
python3 scrapers/football_zebras_scraper.py
```

### 2. Update ALL Script Paths

Search and replace in each workflow file:

| Old Path | New Path |
|----------|----------|
| `football_zebras_scraper.py` | `scrapers/football_zebras_scraper.py` |
| `action_network_scraper_cookies.py` | `scrapers/action_network_scraper_cookies.py` |
| `action_network_injuries_weather.py` | `scrapers/action_network_injuries_weather.py` |
| `rotowire_scraper.py` | `scrapers/rotowire_scraper.py` |
| `sdql_test.py` | `scrapers/sdql_test.py` |
| `query_generator.py` | `analyzers/query_generator.py` |
| `query_generator_v2.py` | `analyzers/query_generator_v2.py` |
| `nfl_pro_analyzer.py` | `analyzers/nfl_pro_analyzer.py` |
| `referee_trend_generator.py` | `analyzers/referee_trend_generator.py` |

### 3. Update Cookie File Path

**Before:**
```yaml
echo "$COOKIES" > action_network_cookies.json
```

**After:**
```yaml
echo "$COOKIES" > config/action_network_cookies.json
```

### 4. Update Data File Paths

**Week-specific files:**
```yaml
# Before
week11_referees.csv

# After  
data/week11/week11_referees.csv
```

**Historical files:**
```yaml
# Before
sdql_results.csv

# After
data/historical/sdql_results.csv
```

### 5. Update Import Statements in Scripts

In scripts that import from other scripts:

**Before (in `nfl_pro_analyzer.py`):**
```python
from query_generator import generate_queries
```

**After:**
```python
import sys
sys.path.append('analyzers')
from query_generator import generate_queries
```

OR use relative imports:
```python
from analyzers.query_generator import generate_queries
```

## Workflow-Specific Updates

### Workflow 1: `1_referee_collection.yml`

```yaml
- name: Scrape Referee Assignments
  run: |
    python3 scrapers/football_zebras_scraper.py
    
- name: Generate SDQL Queries
  run: |
    python3 analyzers/query_generator.py ${{ steps.get_week.outputs.week }}
    
- name: Run SDQL Queries
  run: |
    python3 scrapers/sdql_test.py
```

### Workflow 2: `2_initial_market_data.yml`

```yaml
- name: Create Action Network Cookies
  run: echo "$COOKIES" > config/action_network_cookies.json

- name: Scrape Action Network
  run: python3 scrapers/action_network_scraper_cookies.py
  
- name: Scrape RotoWire
  run: python3 scrapers/rotowire_scraper.py
```

### Workflow 3: `3_market_update.yml`

Same as Workflow 2 for scrapers.

### Workflow 4: `4_pro_analysis.yml`

```yaml
- name: Run Pro Analyzer
  run: python3 analyzers/nfl_pro_analyzer.py ${{ steps.get_week.outputs.week }}
```

## Script Internal Path Updates

### In `nfl_pro_analyzer.py`:

```python
# Update file loading paths
queries = safe_load_csv(f"data/week{week}/week{week}_queries.csv", required=True)
sdql = safe_load_csv("data/historical/sdql_results.csv")

# Update output paths
with open(f"data/week{week}/week{week}_executive_summary.txt", "w") as f:
    # ...
```

### In `action_network_scraper_cookies.py`:

```python
# Update cookie file path
with open('config/action_network_cookies.json', 'r') as f:
    cookies = json.load(f)
```

## Testing After Migration

Run each workflow manually to test:

1. ✅ Workflow 1 - Check data/week{X}/ folder created
2. ✅ Workflow 2 - Check market data saved correctly
3. ✅ Workflow 3 - Check line-flip detection still works
4. ✅ Workflow 4 - Check analysis generates and emails

## Quick Test Script

```bash
# Test that all paths exist
python3 -c "
import os
assert os.path.exists('scrapers/football_zebras_scraper.py')
assert os.path.exists('analyzers/nfl_pro_analyzer.py')
assert os.path.exists('data/')
print('✅ All paths exist!')
"
```
