# NFL Betting Automation

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
