#!/usr/bin/env python3
"""
Referee Trend Digest Generator
Creates quick referee-only summaries for each matchup.
"""
import pandas as pd

def generate_referee_digest(week):
    try:
        refs = pd.read_csv(f"week{week}_referees.csv")
        queries = pd.read_csv(f"week{week}_queries.csv")
        sdql = pd.read_csv("sdql_results.csv")
        
        # Merge to get game_type and favorite
        data = refs.merge(queries, on=['matchup', 'referee'], how='left')

        os.makedirs(f'data/week{week}', exist_ok=True)        
        output_file = f"data/week{week}/week{week}_referee_trends.txt"
        
        with open(output_file, "w") as f:
            f.write("="*60 + "\n")
            f.write(f"NFL WEEK {week} - REFEREE TREND DIGEST\n")
            f.write(f"Historical data: Regular season games 2018-present\n")
            f.write("="*60 + "\n\n")
            
            for _, row in data.iterrows():
                matchup = row['matchup']
                referee = row['referee']
                game_type = row.get('game_type', 'UNKNOWN')
                favorite = row.get('favorite', 'UNKNOWN')
                spread = row.get('spread', 0)
                away = row.get('away', '')
                home = row.get('home', '')
                
                # Determine game type description
                if game_type == 'DIV':
                    type_desc = "Divisional"
                elif game_type == 'C':
                    type_desc = "Conference"
                elif game_type == 'NDIV':
                    type_desc = "Non-division"
                else:
                    type_desc = "Unknown"
                
                # Determine favorite position and team
                if favorite == 'HF':
                    fav_desc = "HOME favorites"
                    fav_team = home
                elif favorite == 'AF':
                    fav_desc = "AWAY favorites"
                    fav_team = away
                else:
                    fav_desc = "Unknown"
                    fav_team = ""
                
                # Find matching SDQL results by query
                query = row.get('query', '')
                if query:
                    trend = sdql[sdql['query'] == query]
                else:
                    trend = pd.DataFrame()
                
                # Write matchup and spread
                f.write(f"{matchup}\n")
                if spread != 0:
                    f.write(f"Line: {fav_team} {spread:+.1f}\n")
                
                if trend.empty:
                    f.write(f"{type_desc} {fav_desc} with {referee} as lead official:\n")
                    f.write(f"No historical data available\n\n")
                    continue
                
                t = trend.iloc[0]
                su = t.get("su_record", "N/A")
                su_pct = t.get("su_pct", "N/A")
                ats = t.get("ats_record", "N/A")
                ats_pct = t.get("ats_pct", "N/A")
                ou = t.get("ou_record", "N/A")
                ou_pct = t.get("ou_pct", "N/A")
                
                f.write(f"{type_desc} {fav_desc} with {referee} as lead official:\n")
                f.write(f"SU: {su} ({su_pct})\n")
                f.write(f"ATS: {ats} ({ats_pct})\n")
                f.write(f"OU: {ou} ({ou_pct})\n\n")
        
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
