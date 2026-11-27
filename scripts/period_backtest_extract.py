#!/usr/bin/env python3
"""Points per quarter for every regular-season game from nflverse play-by-play.

Usage: period_backtest_extract.py DIR  (DIR holds play_by_play_{season}.csv.gz; writes DIR/quarters.csv)
"""
import csv,gzip,sys,glob
D=sys.argv[1]; out=csv.writer(open(f"{D}/quarters.csv","w")); out.writerow(["game_id","season","q1","q2","q3","q4","ot"])
for f in sorted(glob.glob(f"{D}/pbp_20*.csv.gz")):
    last={}; season={}
    for r in csv.DictReader(gzip.open(f,'rt')):
        if r['season_type']!='REG' or not r['qtr']: continue
        q=min(int(r['qtr']),5); g=r['game_id']; season[g]=r['season']
        last[(g,q)]=(int(float(r['total_away_score'] or 0)),int(float(r['total_home_score'] or 0)))
    for g in season:
        cum=[sum(last.get((g,q),(0,0))) if (g,q) in last else None for q in range(1,6)]
        for i in range(1,4):
            if cum[i] is None: cum[i]=cum[i-1]
        pts=[cum[0]]+[cum[i]-cum[i-1] for i in range(1,4)]+[(cum[4]-cum[3]) if cum[4] is not None else 0]
        out.writerow([g,season[g]]+pts)
    print(f, len(season), flush=True)
