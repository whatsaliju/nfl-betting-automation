def generate_ai_summary(week):
    print(f"\n🤖 Generating AI analysis summary for Week {week}...\n")

    try:
        # =====================================================
        # LOAD REQUIRED FILES
        # =====================================================
        referees = safe_load_csv(f'week{week}_referees.csv')
        queries   = safe_load_csv(f'week{week}_queries.csv')
        sdql      = safe_load_csv('sdql_results.csv')

        if queries.empty:
            print("❌ No queries found. Cannot generate summary.")
            return None

        # =====================================================
        # ACTION NETWORK SHARP DATA
        # =====================================================
        action_file = find_latest("action_all_markets")
        if action_file:
            action = safe_load_csv(action_file, required=False)
            has_action = not action.empty
            print(f"📊 Action Network loaded: {action_file}")
        else:
            action = pd.DataFrame()
            has_action = False
            print("⚠️ No Action Network file found.")

        # =====================================================
        # ROTOWIRE INJURIES + WEATHER
        # =====================================================
        injury_file = find_latest("rotowire_lineups")
        if injury_file:
            injuries = safe_load_csv(injury_file, required=False)
            has_injuries = not injuries.empty
            print(f"🩹 RotoWire loaded: {injury_file}")
        else:
            injuries = pd.DataFrame()
            has_injuries = False
            print("⚠️ No RotoWire injury file found.")

        # =====================================================
        # MERGE SDQL INTO QUERIES
        # =====================================================
        final = queries.merge(sdql, on="query", how="left")

        # =====================================================
        # MERGE ACTION NETWORK DATA
        # =====================================================
        if has_action and {'Matchup','Bets %','Money %','Num Bets','Fetched'}.issubset(action.columns):

            final['bets_pct'] = ""
            final['money_pct'] = ""
            final['sharp_edge'] = ""
            final['num_bets'] = ""
            final['fetched'] = ""

            for idx, row in final.iterrows():
                home = row.get('home', '')
                away = row.get('away', '')

                if not home or not away:
                    continue

                # Match by team appearing anywhere in the matchup string
                matches = action[action['Matchup'].str.contains(home, na=False) |
                                 action['Matchup'].str.contains(away, na=False)]

                if not matches.empty:
                    m = matches.iloc[0]

                    try:
                        bets = str(m.get('Bets %','')).replace('%','').strip()
                        money = str(m.get('Money %','')).replace('%','').strip()

                        final.loc[idx, 'bets_pct'] = bets
                        final.loc[idx, 'money_pct'] = money
                        final.loc[idx, 'sharp_edge'] = float(money) - float(bets)

                        final.loc[idx, 'num_bets'] = m.get('Num Bets','')
                        final.loc[idx, 'fetched'] = m.get('Fetched','')

                    except:
                        pass

        # =====================================================
        # MERGE INJURY + WEATHER + GAME TIME
        # =====================================================
        if has_injuries and {'home','away'}.issubset(injuries.columns):

            final['injuries'] = ""
            final['weather'] = ""
            final['game_time'] = ""

            for idx, row in final.iterrows():
                match = injuries[(injuries['home'] == row['home']) &
                                 (injuries['away'] == row['away'])]

                if not match.empty:
                    m = match.iloc[0]
                    final.loc[idx, 'injuries'] = m.get('injuries','')
                    final.loc[idx, 'weather'] = m.get('weather','')
                    final.loc[idx, 'game_time'] = m.get('game_time','')

        # =====================================================
        # OUTPUT FILE
        # =====================================================
        summary_file = f"week{week}_ai_summary.txt"

        with open(summary_file, 'w') as f:

            # -------------------------------------------------
            # HEADER
            # -------------------------------------------------
            f.write("="*80 + "\n")
            f.write(f"NFL WEEK {week} - AI ANALYSIS REQUEST\n")
            f.write(f"Generated: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p ET')}\n")
            f.write("="*80 + "\n\n")

            f.write("INSTRUCTIONS FOR AI:\n")
            f.write(
                "1. Individual game recommendations & confidence\n"
                "2. Unit sizing (0.5–3.0 units)\n"
                "3. Sharp/public analysis\n"
                "4. Injury/weather adjustments\n"
                "5. Trap games & contrarian plays\n"
                "6. Weekly betting portfolio\n\n"
            )

            f.write("="*80 + "\n\n")

            # -------------------------------------------------
            # DATA HEALTH CHECK
            # -------------------------------------------------
            f.write("DATA HEALTH CHECK\n")
            f.write("-"*80 + "\n")
            f.write(f"SDQL Results:        {'✔' if not sdql.empty else '✖'} ({len(sdql)} rows)\n")
            f.write(f"Referees Loaded:     {'✔' if not referees.empty else '✖'}\n")
            f.write(f"Queries Loaded:      {'✔' if not queries.empty else '✖'} ({len(queries)} queries)\n")

            if has_action:
                f.write(f"Action Network:      ✔ ({action_file})\n")
                f.write(f"  Bets % present:    {'✔' if 'Bets %' in action.columns else '✖'}\n")
                f.write(f"  Money % present:   {'✔' if 'Money %' in action.columns else '✖'}\n")
            else:
                f.write("Action Network:      ✖ Missing\n")

            if has_injuries:
                f.write(f"Injuries Loaded:     ✔ ({injury_file})\n")
            else:
                f.write("Injuries Loaded:     ✖ Missing\n")

            f.write("\n" + "="*80 + "\n\n")

            # -------------------------------------------------
            # GAME-BY-GAME BREAKDOWN
            # -------------------------------------------------
            for idx, row in final.iterrows():

                f.write(f"GAME #{idx+1}: {row.get('matchup','')}\n")
                f.write("-"*80 + "\n")

                # Time
                if row.get('game_time'):
                    f.write(f"Time: {row['game_time']}\n")

                # Referee
                f.write(f"\nREFEREE: {row.get('referee','Unknown')}\n")
                f.write(f"  ATS: {row.get('ats_record','')} ({row.get('ats_pct','')})\n")
                f.write(f"  SU:  {row.get('su_record','')} ({row.get('su_pct','')})\n")
                f.write(f"  O/U: {row.get('ou_record','')} ({row.get('ou_pct','')})\n")

                # Betting Lines
                f.write("\nBETTING LINES:\n")
                spread = row.get('spread','')

                try:
                    f.write(f"  Spread: {row['home']} {float(spread):+.1f}\n")
                except:
                    f.write(f"  Spread: {spread}\n")

                if row.get('total'):
                    f.write(f"  Total: {row['total']}\n")

                # -------------------------------------------------
                # PUBLIC BETTING (NEW FULL SECTION)
                # -------------------------------------------------
                f.write("\nPUBLIC BETTING:\n")

                bets = row.get('bets_pct', '')
                money = row.get('money_pct', '')
                diff = row.get('sharp_edge', '')
                nb = row.get('num_bets', '')
                fetch = row.get('fetched','')

                f.write(f"  Bets %:   {bets}%\n" if bets != "" else "  Bets %:   N/A\n")
                f.write(f"  Money %:  {money}%\n" if money != "" else "  Money %:  N/A\n")
                f.write(f"  Diff:     {diff:+.1f}%\n" if diff != "" else "  Diff:     N/A\n")
                f.write(f"  Num Bets: {nb}\n" if nb != "" else "  Num Bets: N/A\n")
                if fetch:
                    f.write(f"  Fetched:  {fetch}\n")

                # Sharp Edge summary
                f.write("\nSHARP MONEY:\n")
                if diff != "":
                    f.write(f"  Sharp Edge: {diff:+.1f}%\n")
                    if abs(diff) >= 5:
                        f.write("  🔥 High sharp discrepancy\n")
                else:
                    f.write("  Not available\n")

                # Injuries
                f.write("\nINJURIES:\n")
                inj = row.get('injuries','')
                f.write(f"  {inj}\n" if inj else "  None\n")

                # Weather
                f.write("\nWEATHER:\n")
                w = row.get('weather','')
                f.write(f"  {w}\n" if w else "  None\n")

                # Context (type + fave)
                f.write("\nCONTEXT:\n")
                f.write(f"  Type: {row.get('game_type','Unknown')}\n")
                f.write(f"  Favorite: {row.get('favorite','Unknown')}\n")

                f.write("\n" + "="*80 + "\n\n")

            # -------------------------------------------------
            # QUICK STATS SUMMARY
            # -------------------------------------------------
            f.write("\nQUICK STATS:\n")

            # Sharp edges >= 5%
            if 'sharp_edge' in final.columns:
                high = final[final['sharp_edge'].abs() >= 5]
                f.write(f"Games with strong sharp edge (>=5%): {len(high)}\n")

            # Weather flags
            weather_count = 0
            for w in final.get('weather', pd.Series([])):
                if isinstance(w,str) and any(k in w.lower() for k in ['rain','snow']):
                    weather_count += 1

            f.write(f"Games with weather concerns: {weather_count}\n")

            # Prime time
            prime = 0
            for t in final.get('game_time', pd.Series([])):
                if isinstance(t,str) and any(k in t.upper() for k in ['THU','MON','8:']):
                    prime += 1

            f.write(f"Prime time games: {prime}\n")

        print(f"✅ AI summary successfully created: {summary_file}")
        return summary_file

    except Exception as e:
        print(f"❌ Unexpected failure in generate_ai_summary: {e}")
        return None
