import duckdb, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
con=duckdb.connect('a.db'); con.sql("PRAGMA memory_limit='2GB'"); con.sql("PRAGMA temp_directory='tmp'"); con.sql('PRAGMA threads=4'); con.sql('PRAGMA disable_progress_bar')
CF='jul/HIST_CONTROVERSIES_20260731.parquet'; SS='jul/HIST_SUMMARY_SCORES_20260731.parquet'
mi=lambda d:(d//10000)*12+((d//100)%100)
# ---- RECLASSIFICATION: per issue, moderate & severe(+vsev) counts over stored dates; at severe increase, what does moderate do? ----
con.sql(f"""CREATE OR REPLACE TABLE mc AS
 WITH raw AS (SELECT ISSUERID, REGEXP_REPLACE(FIELD_ID,'_(VERY_SEVERE|SEVERE|MODERATE)_CONTROVERSIES$','') issue,
    CASE WHEN FIELD_ID LIKE '%MODERATE_CONTROVERSIES' THEN 'mod' ELSE 'sev' END lvl, START_DATE, TRY_CAST(VALUE AS DOUBLE) v,
    ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
    FROM '{CF}' WHERE (FIELD_ID LIKE '%MODERATE_CONTROVERSIES' OR FIELD_ID LIKE '%SEVERE_CONTROVERSIES') AND START_DATE>=20160101),
  agg AS (SELECT ISSUERID,issue,lvl,START_DATE,SUM(v) c FROM raw WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2,3,4),
  w AS (SELECT ISSUERID,issue,START_DATE, MAX(CASE WHEN lvl='mod' THEN c END) modc, MAX(CASE WHEN lvl='sev' THEN c END) sevc FROM agg GROUP BY 1,2,3)
 SELECT ISSUERID,issue,START_DATE, COALESCE(modc,0)-LAG(COALESCE(modc,0)) OVER(PARTITION BY ISSUERID,issue ORDER BY START_DATE) dmod,
    COALESCE(sevc,0)-LAG(COALESCE(sevc,0)) OVER(PARTITION BY ISSUERID,issue ORDER BY START_DATE) dsev FROM w""")
ev=con.sql("SELECT dmod FROM mc WHERE dsev>0").df()
n=len(ev)
print("[RECLASSIFICATION] severe-onset issue-dates: %d | Δmod<0 (reclass) %.0f%% | Δmod=0 (new) %.0f%% | Δmod>0 %.0f%%"%(
  n,100*(ev.dmod<0).mean(),100*(ev.dmod==0).mean(),100*(ev.dmod>0).mean()))
# ---- LEAD: same-issue moderate onset -> next severe onset (months) ----
lead=con.sql(f"""WITH o AS (SELECT ISSUERID, REGEXP_REPLACE(FIELD_ID,'_(VERY_SEVERE|SEVERE|MODERATE)_CONTROVERSIES$','') issue,
    CASE WHEN FIELD_ID LIKE '%MODERATE_CONTROVERSIES' THEN 'mod' ELSE 'sev' END lvl, START_DATE, TRY_CAST(VALUE AS DOUBLE) v,
    ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
    FROM '{CF}' WHERE (FIELD_ID LIKE '%MODERATE_CONTROVERSIES' OR FIELD_ID LIKE '%SEVERE_CONTROVERSIES') AND START_DATE>=20160101),
  a AS (SELECT ISSUERID,issue,lvl,START_DATE,SUM(v) c FROM o WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2,3,4),
  d AS (SELECT ISSUERID,issue,lvl,START_DATE, c-LAG(c) OVER(PARTITION BY ISSUERID,issue,lvl ORDER BY START_DATE) dc FROM a),
  mo AS (SELECT ISSUERID,issue,(START_DATE//10000)*12+((START_DATE//100)%100) m FROM d WHERE lvl='mod' AND dc>0),
  so AS (SELECT ISSUERID,issue,(START_DATE//10000)*12+((START_DATE//100)%100) m FROM d WHERE lvl='sev' AND dc>0),
  pair AS (SELECT mo.ISSUERID,mo.issue,mo.m lm,MIN(so.m) sm FROM mo JOIN so ON so.ISSUERID=mo.ISSUERID AND so.issue=mo.issue AND so.m>mo.m GROUP BY 1,2,3)
  SELECT sm-lm gap FROM pair WHERE sm-lm BETWEEN 1 AND 36""").df()
print("[LEAD] same-issue moderate->severe: median %.0f mean %.1f months | %%>=6mo %.0f | n=%d"%(lead.gap.median(),lead.gap.mean(),100*(lead.gap>=6).mean(),len(lead)))
# ---- HAZARD (discrete-time cloglog): era effect on monthly downgrade hazard after a severe controversy ----
ias=con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{SS}' WHERE FIELD_ID='INDUSTRY_ADJUSTED_SCORE' AND START_DATE>=20160101) SELECT ISSUERID,START_DATE,v,LAG(v) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) pv FROM l WHERE rn=1 AND v IS NOT NULL""").df()
ias['dg']=np.where(ias.v-ias.pv<-1e-9,mi(ias.START_DATE),np.nan); dg=ias.dropna(subset=['dg'])[['ISSUERID','dg']].astype({'dg':int})
sev=con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE FIELD_ID LIKE 'CONTR\\_%\\_N\\_SEVERE' ESCAPE '\\' AND START_DATE>=20160101), pd AS (SELECT ISSUERID,START_DATE,SUM(v) s FROM l WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2) SELECT ISSUERID,START_DATE,s-LAG(s) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) ds FROM pd""").df()
ev2=sev[sev.ds>1e-9].copy(); ev2['ev']=mi(ev2.START_DATE); yr=ev2.START_DATE//10000
ev2['late']=np.where((yr>=2021)&(yr<=2025),1,np.where((yr>=2018)&(yr<=2019),0,-1)); ev2=ev2[ev2.late>=0]
ev2['ev']=ev2['ev'].astype('int64'); dgs=dg.copy(); dgs['dg']=dgs['dg'].astype('int64'); dgs['ev']=dgs['dg']; ev2=ev2.sort_values('ev'); dgs=dgs.sort_values('dg')
ev2=pd.merge_asof(ev2,dgs[['ISSUERID','dg']],by='ISSUERID',left_on='ev',right_on='dg',direction='forward')
DE=mi(20260731); ev2['lag']=ev2.dg-ev2.ev; ev2['cens']=DE-ev2.ev
# person-month expansion to 24 months, discrete-time
rows=[]
for late,lag,cens in zip(ev2.late,ev2.lag.values,ev2.cens.values):
    horizon=int(min(24, lag if not np.isnan(lag) else cens))
    for m in range(1,horizon+1):
        fail=1 if (not np.isnan(lag) and lag==m) else 0
        rows.append((late,m,fail))
        if fail: break
pm=pd.DataFrame(rows,columns=['late','month','fail'])
import statsmodels.api as sm
X=sm.add_constant(pd.get_dummies(pm['month'],prefix='m',drop_first=True).astype(float)); X['late']=pm['late'].astype(float)
mdl=sm.GLM(pm['fail'],X,family=sm.families.Binomial(sm.families.links.CLogLog())).fit()
print("[HAZARD cloglog] late-era coef=%.3f (z=%.1f) -> hazard ratio=%.2f | events early=%d late=%d"%(
  mdl.params['late'],mdl.tvalues['late'],np.exp(mdl.params['late']),(ev2.late==0).sum(),(ev2.late==1).sum()))
