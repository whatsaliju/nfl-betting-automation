#!/usr/bin/env python3
"""Quarter/half totals backtest behind the period angles (Nov 27 2026). Run period_backtest_extract.py DIR first.

DIR holds nflverse games.csv and quarters.csv. Grades each period walk-forward 2017-2026 against a line
built from the full-game closing total x the share of points that period got in earlier seasons, by
situation, then checks 2017-21 vs 2022-26. Usage: period_backtest.py DIR
"""
import csv,sys,collections,math
D=sys.argv[1]
G={r['game_id']:r for r in csv.DictReader(open(f"{D}/games.csv"))}
rows=[]
for r in csv.DictReader(open(f"{D}/quarters.csv")):
    g=G.get(r['game_id'])
    if not g or not g['total_line'] or not g['home_score']: continue
    q=[int(r[k]) for k in ('q1','q2','q3','q4')]; ot=int(r['ot'])
    T=float(g['total_line']); sp=float(g['spread_line'] or 0)
    h=int((g['gametime'] or '13:00')[:2]); wd=g['weekday']
    rows.append(dict(s=int(r['season']),w=int(g['week']),T=T,sp=abs(sp),q=q,h1=q[0]+q[1],h2=q[2]+q[3]+ot,
        dome=g['roof'] in('dome','closed'),wind=float(g['wind'] or 0) if g['roof'] in('outdoors','open') else 0,
        temp=float(g['temp'] or 60) if g['roof'] in('outdoors','open') else 70,
        prime=(h>=19) or wd in('Monday','Thursday'),div=g['div_game']=='1'))
PER=['Q1','Q2','Q3','Q4','1H','2H']
def pts(r,p): return {'Q1':r['q'][0],'Q2':r['q'][1],'Q3':r['q'][2],'Q4':r['q'][3],'1H':r['h1'],'2H':r['h2']}[p]
rh=lambda x: math.floor(x)+0.5   # quarter/half lines sit on .5
# walk-forward shares
for S in range(2017,2027):
    tr=[x for x in rows if x['s']<S]; tt=sum(x['T'] for x in tr)
    sh={p:sum(pts(x,p) for x in tr)/sum(x['h1']+x['h2'] for x in tr)*sum(x['h1']+x['h2'] for x in tr)/tt for p in PER}
    for r in (x for x in rows if x['s']==S):
        for p in PER:
            exp=sh[p]*r['T']; line=rh(exp); a=pts(r,p)
            r.setdefault('res',{})[p]=(a-exp, a>line, line)
test=[r for r in rows if r['s']>=2017]
print("games",len(test),"(2017-2026, walk-forward)")
segs={'ALL':lambda r:True,'total<41':lambda r:r['T']<41,'total 41-47':lambda r:41<=r['T']<47.5,'total 48+':lambda r:r['T']>=47.5,
 'spread<=3':lambda r:r['sp']<=3,'spread 3.5-6.5':lambda r:3<r['sp']<7,'spread 7+':lambda r:r['sp']>=7,
 'dome':lambda r:r['dome'],'wind 15+':lambda r:r['wind']>=15,'cold <35F':lambda r:r['temp']<35,'primetime':lambda r:r['prime'],
 'divisional':lambda r:r['div'],'weeks 1-4':lambda r:r['w']<=4,'weeks 14+':lambda r:r['w']>=14}
print(f"{'segment':16s}{'n':>5s} "+" ".join(f"{p:>16s}" for p in PER))
for name,f in segs.items():
    sub=[r for r in test if f(r)]
    cells=[]
    for p in PER:
        o=sum(r['res'][p][1] for r in sub); n=len(sub); m=sum(r['res'][p][0] for r in sub)/n
        ss=collections.defaultdict(lambda:[0,0])
        for r in sub: ss[r['s']][0]+=r['res'][p][1]; ss[r['s']][1]+=1
        up=sum(1 for v in ss.values() if v[0]/v[1]>0.5)
        cells.append(f"{o/n:5.1%}O {m:+5.2f} {up:2d}/10")
    print(f"{name:16s}{len(sub):5d} "+" ".join(f"{c:>16s}" for c in cells))
# typical proxy lines at a 44.5 total
print("lines at 44.5 total:",{p:rh(sum(pts(x,p) for x in rows)/sum(x['T'] for x in rows)*44.5) for p in PER})
print("\n--- split check: 2017-21 vs 2022-26 (points vs expected, over% at proxy) ---")
checks=[('primetime','1H'),('primetime','Q1'),('spread<=3','Q3'),('spread<=3','1H'),('spread 7+','1H'),('spread 7+','Q2'),('spread 7+','Q4'),('wind 15+','1H'),('dome','2H'),('cold <35F','2H'),('spread 3.5-6.5','2H')]
base={p:sum(r['res'][p][0] for r in test)/len(test) for p in PER}
for seg,p in checks:
    out=[]
    for lo,hi in((2017,2021),(2022,2026)):
        sub=[r for r in test if segs[seg](r) and lo<=r['s']<=hi]
        m=sum(r['res'][p][0] for r in sub)/len(sub)-base[p]; o=sum(r['res'][p][1] for r in sub)/len(sub)
        out.append(f"{lo}-{hi%100}: {m:+.2f} vs avg, {o:.1%}O (n={len(sub)})")
    print(f"{seg:15s}{p:3s}  "+"   ".join(out))
