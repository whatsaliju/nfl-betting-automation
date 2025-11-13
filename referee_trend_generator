#!/usr/bin/env python3
"""
Referee Trend Digest Generator
Creates quick referee-only summaries for each matchup.
Format: emoji-friendly, grouped style (Option A)
"""
import pandas as pd

def generate_referee_digest(week):
    try:
        refs = pd.read_csv(f"week{week}_referees.csv")
        queries = pd.read_csv(f"week{week}_queries.csv")
        sdql = pd.read_csv("sdql_results.csv")
        
        # Merge to get game_type and favorite
        data = refs.merge(queries, on=['matchup', 'referee'], how='left')
        
        output_file = f"week{week}_referee_trends.txt"
        
        with open(output_file, "w") as f:
            f.write("="*60 + "\n")
            f.write(f"NFL WEEK {week} - REFEREE TREND DIGEST\n")
            f.write("="*60 + "\n\n")
            
            for _, row in data.iterrows():
                matchup = row['matchup']
                referee = row['referee']
                game_type = row.get('game_type', 'UNKNOWN')
                favorite = row.get('favorite', 'UNKNOWN')
                
                category = f"{favorite} {game_type}".strip()
                
                # Find matching SDQL results by query
                query = row.get('query', '')
                if query:
                    trend = sdql[sdql['query'] == query]
                else:
                    trend = pd.DataFrame()
                
                if trend.empty:
                    f.write(f"🏈 {matchup}\n")
                    f.write(f"🧑‍⚖️ {category} with {referee}\n")
                    f.write(f"⚠️ No historical data available\n\n")
                    continue
                
                t = trend.iloc[0]
                su = t.get("su_record", "N/A")
                su_pct = t.get("su_pct", "N/A")
                ats = t.get("ats_record", "N/A")
                ats_pct = t.get("ats_pct", "N/A")
                ou = t.get("ou_record", "N/A")
                ou_pct = t.get("ou_pct", "N/A")
                
                f.write(f"🏈 {matchup}\n")
                f.write(f"🧑‍⚖️ {category} with {referee}\n")
                f.write(f"📈 SU: {su} ({su_pct})\n")
                f.write(f"📉 ATS: {ats} ({ats_pct})\n")
                f.write(f"🔽 O/U: {ou} ({ou_pct})\n\n")
        
        print(f"✅ Referee digest created: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating referee digest: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    generate_referee_digest(week)
