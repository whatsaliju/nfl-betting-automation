# graders/grade_week_results.py
import pandas as pd
import requests
from datetime import datetime

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def grade_week(season, week):
    path = f"data/historical/week{week}_master.csv"
    df = pd.read_csv(path)

    # Only grade once
    df["graded"] = df.get("graded", False)

    # pull scores (reuse logic you already trust)
    scores = fetch_scores(season, week)

    for idx, row in df.iterrows():
        if row["graded"]:
            continue

        if not row.get("final_recommendation"):
            df.at[idx, "result"] = "NO BET"
            df.at[idx, "graded"] = True
            continue

        # evaluate spread / total here
        result, margin = evaluate_bet(row, scores)

        df.at[idx, "result"] = result
        df.at[idx, "cover_margin"] = margin
        df.at[idx, "graded"] = True
        df.at[idx, "graded_at"] = datetime.utcnow().isoformat()

    df.to_csv(path, index=False)
