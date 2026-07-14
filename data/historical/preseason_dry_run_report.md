# Preseason Dry Run Readiness

- Season: 2026
- Season type: PRE
- Week: 1
- Artifact slug: `PRE1`
- Status: **PASS**

| Check | Status | Detail |
|---|---|---|
| season type normalization | PASS | PRE resolves to PRE |
| nflverse game type | PASS | PRE maps to nflverse PRE games |
| ESPN season type | PASS | PRE maps to ESPN seasontype=1 |
| ESPN week | PASS | PRE Week 1 maps to ESPN week 1 |
| builder ESPN params | PASS | {"dates": 2026, "seasontype": 1, "week": 1} |
| master builder season type | PASS | builder uses PRE |
| preseason artifact slug | PASS | week 1 writes as weekPRE1_master |
| feed sort isolation | PASS | preseason master files sort before regular-season master files |
| enhanced workflow PRE env | PASS | /Users/lijuv/nfl-betting-automation/.github/workflows/4.5_enhanced_pro_workflow.yml |
| preseason dry-run workflow | PASS | /Users/lijuv/nfl-betting-automation/.github/workflows/12_preseason_dry_run.yml |
| contract compile hook | PASS | /Users/lijuv/nfl-betting-automation/.github/workflows/0_engine_contracts.yml |
| command center readiness copy | PASS | /Users/lijuv/nfl-betting-automation/site/src/components/CommandCenterView.tsx |
| survivor planning artifact | PASS | /Users/lijuv/nfl-betting-automation/site/src/data/survivorRecommendations2026.json |
| weekly betting card artifact | PASS | /Users/lijuv/nfl-betting-automation/data/historical/weekly_betting_card.json |

## Next Live Command

`python3 builders/build_week_master_table.py --season 2026 --week 1 --season-type PRE`
