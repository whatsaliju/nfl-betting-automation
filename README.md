# nfl-betting-automation
# 🏈 NFL Betting Automation

Automated NFL betting analysis system that combines referee tendencies, historical trends, sharp money tracking, and injury data to generate weekly betting recommendations.

## 🎯 What It Does

Every Wednesday evening (after referee assignments are posted), this system automatically:

1. **Scrapes referee assignments** from Football Zebras
2. **Fetches current betting lines** from The Odds API
3. **Generates SDQL queries** based on referee + game situation (home/away favorite, division/conference games)
4. **Runs queries through GimmeTheDog** to get historical ATS/SU/O-U trends
5. **Scrapes sharp money data** from Action Network
6. **Collects injury/weather data** from RotoWire
7. **Generates comprehensive reports** with betting recommendations

## 📊 Output Files

Each week generates:
- `week{X}_referees.csv` - Referee assignments for all games
- `week{X}_queries.csv` - SDQL queries with current spreads
- `week{X}_complete_data.csv` - All data merged together
- `week{X}_enhanced_report.txt` - Detailed betting analysis
- `week{X}_ai_summary.txt` - AI-ready summary for Claude analysis
- `sdql_results.csv` - Historical referee trends (ATS records, percentages)

## 🚀 Quick Start

### Running Manually
```bash
# Set environment variables
export GIMMETHEDOG_EMAIL="your_email@example.com"
export GIMMETHEDOG_PASSWORD="your_password"
export ODDS_API_KEY="your_api_key"

# Run for current week (auto-detected)
python3 nfl_weekly_analyzer.py

# Run for specific week
python3 nfl_weekly_analyzer.py --week 11
```

### GitHub Actions (Automated)

The workflow runs automatically every Wednesday at 10 PM UTC (6 PM ET). You can also trigger it manually:

1. Go to **Actions** tab
2. Click **NFL Weekly Analysis**
3. Click **Run workflow**
4. Select week (or leave blank for auto-detect)

## 📥 Getting Results

After the workflow completes:

1. Go to the **Actions** tab
2. Click on the latest workflow run
3. Scroll down to **Artifacts**
4. Download `nfl-analysis-results.zip`
5. Unzip to access all reports and data

## 🔑 Setup Requirements

### GitHub Secrets

Add these to your repository (Settings → Secrets → Actions):

- `GIMMETHEDOG_EMAIL` - Your GimmeTheDog/SDQL login email
- `GIMMETHEDOG_PASSWORD` - Your GimmeTheDog/SDQL password
- `ODDS_API_KEY` - Your API key from [The Odds API](https://the-odds-api.com/)

### Python Dependencies
```bash
pip install -r requirements.txt
```

Main dependencies:
- `selenium` - Web scraping
- `pandas` - Data processing
- `requests` - API calls
- `beautifulsoup4` - HTML parsing
- `webdriver-manager` - Chrome driver management

## 📁 Project Structure
```
nfl-betting-automation/
├── nfl_weekly_analyzer.py          # Main automation pipeline
├── football_zebras_scraper.py      # Scrapes referee assignments
├── query_generator.py              # Generates SDQL queries
├── sdql_test.py                    # Runs queries through GimmeTheDog
├── action_network_scraper.py       # Scrapes sharp money data
├── rotowire_scraper.py             # Scrapes injury/weather data
├── enhanced_report_generator.py    # Creates betting reports
├── generate_ai_summary.py          # Creates AI-ready summary
├── .github/workflows/
│   ├── nfl_weekly_analysis.yml     # Main weekly automation
│   └── test_sdql.yml               # Test SDQL scraper only
└── requirements.txt                # Python dependencies
```

## 🎲 How to Use the Reports

### Enhanced Report (`week{X}_enhanced_report.txt`)

Contains game-by-game analysis with:
- Referee ATS trends (highlighted if >55% or <45%)
- Current betting lines
- Sharp money indicators
- Injury reports
- Weather conditions
- Recommended plays

### AI Summary (`week{X}_ai_summary.txt`)

1. Open the file
2. Copy entire contents
3. Paste into Claude chat
4. Ask: "Analyze these games and provide betting recommendations"

Claude will provide:
- Individual game recommendations with confidence scores
- Unit sizing suggestions
- Top 3 plays with detailed reasoning
- Trap game warnings
- Contrarian opportunities

## 📈 Understanding the Data

### Referee Trends

- **ATS (Against The Spread)**: How often the favorite covers
- **SU (Straight Up)**: How often the favorite wins outright
- **O/U (Over/Under)**: How often games go over the total

**Key thresholds:**
- ≥60% ATS = Strong trend (🔥 STRONG PLAY)
- 55-59% ATS = Solid trend (⭐ SOLID PLAY)
- 45-54% ATS = Neutral
- ≤44% ATS = Fade trend (❌ FADE)

### Game Types

- **HF**: Home Favorite
- **AF**: Away Favorite
- **DIV**: Division game
- **C**: Conference (non-division) game
- **NDIV**: Non-division/non-conference game

### Sharp Money

Difference between % of money and % of bets:
- **≥5% difference**: 🔥 Significant sharp action
- **3-4% difference**: ⚠️ Moderate sharp action
- **<3% difference**: Public and sharp aligned

## 🔧 Troubleshooting

### SDQL Scraper Issues

If queries fail:
```bash
# Test SDQL scraper independently
python3 sdql_test.py
```

Check that:
- ✅ GimmeTheDog credentials are correct
- ✅ Site structure hasn't changed
- ✅ Chrome/ChromeDriver is working

### Referee Scraper Issues

Football Zebras posts assignments Wednesday afternoon/evening. If scraping fails:
- Check [FootballZebras.com/category/assignments](https://www.footballzebras.com/category/assignments/)
- Assignments may not be posted yet
- Run workflow later in the evening

### Odds API Issues

Free tier: 500 requests/month
- Each scrape uses 1 request
- Monitor usage at [The Odds API Dashboard](https://the-odds-api.com/account/)

## ⚙️ Configuration

### Changing Auto-Detection Week

Edit `nfl_weekly_analyzer.py`:
```python
def get_current_nfl_week():
    season_start = datetime(2025, 9, 4)  # Update for new season
    # ...
```

### Adjusting Wait Times

If scrapers are timing out, increase waits in `sdql_test.py`:
```python
time.sleep(15)  # Wait for results to load (increase if needed)
```

## 🤝 Contributing

Found a bug or want to add a feature?
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## ⚠️ Disclaimer

This tool is for **informational and educational purposes only**. 

- Past performance does not guarantee future results
- Gambling involves risk - never bet more than you can afford to lose
- Check local laws regarding sports betting
- The authors are not responsible for any financial losses

**Bet responsibly.**

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Data sources:
- [Football Zebras](https://www.footballzebras.com/) - Referee assignments
- [GimmeTheDog/SDQL](https://www.gimmethedog.com/) - Historical query data
- [The Odds API](https://the-odds-api.com/) - Betting lines
- [Action Network](https://www.actionnetwork.com/) - Sharp money data
- [RotoWire](https://www.rotowire.com/) - Injury and lineup data

## 📧 Support

For issues or questions:
- Open an issue on GitHub
- Check existing issues for solutions

---

**Built with ❤️ for smart NFL betting**
