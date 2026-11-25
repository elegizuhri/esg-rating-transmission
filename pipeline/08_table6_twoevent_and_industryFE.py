import duckdb, pandas as pd, numpy as np, statsmodels.api as sm, warnings
warnings.filterwarnings('ignore')
con=duckdb.connect(); con.sql('PRAGMA disable_progress_bar'); con.sql("PRAGMA memory_limit='3GB'"); con.sql("PRAGMA temp_directory='tmp'")
R='/mnt/user-data/uploads/monthly_total_returns__1_.csv'
IR='mref/HIST_MASTER_INSTRUMENT_REFERENCE_none_20260831.parquet'
ISR='mref/HIST_MASTER_ISSUER_REFERENCE_20260831.parquet'
SS='jul/HIST_SUMMARY_SCORES_20260731.parquet'; CF='jul/HIST_CONTROVERSIES_20260731.parquet'
# ---------- (A) INDUSTRY FE for §6.7 ----------
sec=con.sql(f"SELECT DISTINCT ISSUERID, ANY_VALUE(GICS_SECTOR) sector FROM '{ISR}' WHERE GICS_SECTOR IS NOT NULL GROUP BY ISSUERID").df()
D=pd.read_parquet('pricing_panel.parquet').merge(sec,on='ISSUERID',how='left')
def reg(dat,y,xs,fes):
    d=dat.dropna(subset=[y]+xs+fes).copy()
    parts=[d[xs]]
    for fe in fes: parts.append(pd.get_dummies(d[fe].astype(str),prefix=fe[:3],drop_first=True).astype(float))
    X=pd.concat(parts,axis=1)
    r=sm.OLS(d[y],sm.add_constant(X)).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(_grp(d['ISSUERID']))[0]})
    return {x:(round(r.params[x],4),round(r.tvalues[x],2)) for x in xs}, int(r.nobs)
print("=== §6.7 pricing WITH industry (GICS sector) FE added ===")
print(" fwd12 ~ own + nonown  [year+country+sector FE]:", reg(D,'fwd12w',['own','nonown'],['yr','ctry','sector']))
d=D.dropna(subset=['fwd12w','own','nonown','sector']).copy()
X=pd.concat([d[['own','nonown']],pd.get_dummies(d.yr.astype(str),prefix='y',drop_first=True).astype(float),pd.get_dummies(d.ctry,prefix='c',drop_first=True).astype(float),pd.get_dummies(d.sector,prefix='s',drop_first=True).astype(float)],axis=1)
r=sm.OLS(d.fwd12w,sm.add_constant(X)).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(_grp(d.ISSUERID))[0]})
w=r.f_test("own=0, nonown=0"); print("   joint Wald own=nonown=0: F=%.2f p=%.3f | N=%d"%(float(w.fvalue),float(w.pvalue),int(r.nobs)))

# ---------- (B) TWO-EVENT STUDY: returns around controversy onsets vs downgrades ----------
mi=lambda d:(d//10000)*12+((d//100)%100)
# monthly returns -> market(country x month)-adjusted
con.sql(f"""CREATE OR REPLACE TABLE ret AS SELECT isin, (EXTRACT(year FROM CAST(date AS DATE))*12+EXTRACT(month FROM CAST(date AS DATE))) midx,
  tr_return_pct/100.0 r, ISSUER_CNTRY_DOMICILE ctry FROM read_csv_auto('{R}') WHERE tr_return_pct IS NOT NULL""")
con.sql("CREATE OR REPLACE TABLE cm AS SELECT ctry, midx, AVG(r) mr FROM ret GROUP BY ctry,midx")
con.sql("CREATE OR REPLACE TABLE reta AS SELECT t.isin, t.midx, (t.r - c.mr) ra FROM ret t JOIN cm c ON c.ctry=t.ctry AND c.midx=t.midx")
# map isin->ISSUERID (primary = most return obs)
con.sql("CREATE OR REPLACE TABLE obs AS SELECT isin, COUNT(*) n FROM ret GROUP BY isin")
con.sql(f"""CREATE OR REPLACE TABLE map AS WITH p AS (SELECT DISTINCT ISSUERID,ISIN FROM '{IR}' WHERE ISIN IS NOT NULL AND ISSUERID IS NOT NULL),
  j AS (SELECT p.ISSUERID,p.ISIN,o.n,ROW_NUMBER() OVER(PARTITION BY p.ISSUERID ORDER BY o.n DESC) rk FROM p JOIN obs o ON o.isin=p.ISIN)
  SELECT ISSUERID,ISIN FROM j WHERE rk=1""")
con.sql("CREATE OR REPLACE TABLE fmret AS SELECT m.ISSUERID, r.midx, r.ra FROM reta r JOIN map m ON m.ISIN=r.isin")
# forward 6-month cumulative abnormal return CAR[+1,+6]
con.sql("""CREATE OR REPLACE TABLE car AS SELECT ISSUERID, midx,
   SUM(ra) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 1 FOLLOWING AND 6 FOLLOWING) car6,
   COUNT(*) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 1 FOLLOWING AND 6 FOLLOWING) nf FROM fmret""")
# events: downgrade (letter band drop) and severe onset
ias=con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{SS}' WHERE FIELD_ID='INDUSTRY_ADJUSTED_SCORE' AND START_DATE>=20160101) SELECT ISSUERID, (START_DATE//10000*12+(START_DATE//100%100)) midx, CAST(floor(v/(10.0/7)) AS INT) band, CAST(floor(LAG(v) OVER(PARTITION BY ISSUERID ORDER BY START_DATE)/(10.0/7)) AS INT) pband FROM l WHERE rn=1 AND v IS NOT NULL""").df()
dg=ias[ias.band<ias.pband][['ISSUERID','midx']].drop_duplicates(); dg['downgrade']=1
sev=con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE FIELD_ID LIKE 'CONTR\\_%\\_N\\_SEVERE' ESCAPE '\\' AND START_DATE>=20160101), p AS (SELECT ISSUERID,START_DATE,SUM(v) s FROM l WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2), d AS (SELECT ISSUERID,(START_DATE//10000*12+(START_DATE//100%100)) midx, s-LAG(s) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) ds FROM p) SELECT DISTINCT ISSUERID,midx FROM d WHERE ds>0""").df(); sev['sevonset']=1
C=con.sql("SELECT ISSUERID,midx,car6,nf FROM car WHERE nf>=6").df()
C=C.merge(dg,on=['ISSUERID','midx'],how='left').merge(sev,on=['ISSUERID','midx'],how='left').fillna({'downgrade':0,'sevonset':0})
# prior-12m severe controversy flag (for downgrades: was it controversy-linked?)
sv=sev[['ISSUERID','midx']].copy()
C=C.sort_values(['ISSUERID','midx'])
svset=set(map(tuple, sv.values))
def prior12(r):
    return int(any((r.ISSUERID,r.midx-k) in svset for k in range(0,13)))
# vectorized prior12 via merge_asof-like: mark months within 12 after a sev onset
sv2=sv.rename(columns={'midx':'sm'}); mrg=C[['ISSUERID','midx']].merge(sv2,on='ISSUERID'); mrg=mrg[(mrg.midx-mrg.sm).between(0,12)]
linked=mrg[['ISSUERID','midx']].drop_duplicates(); linked['contr12']=1
C=C.merge(linked,on=['ISSUERID','midx'],how='left').fillna({'contr12':0})
C=C[(C.midx>=2016*12) & (C.midx<=2025*12)]   # window with returns coverage
print("\n=== TWO-EVENT STUDY: 6-month forward CAR (market-adjusted) around events ===")
print(" mean CAR6  no event            : %+.4f (N=%d)"%(C[(C.downgrade==0)&(C.sevonset==0)].car6.mean(), ((C.downgrade==0)&(C.sevonset==0)).sum()))
print(" mean CAR6  severe controversy   : %+.4f (N=%d)"%(C[C.sevonset==1].car6.mean(), (C.sevonset==1).sum()))
print(" mean CAR6  downgrade (all)      : %+.4f (N=%d)"%(C[C.downgrade==1].car6.mean(), (C.downgrade==1).sum()))
print(" mean CAR6  downgrade, controversy-linked (prior12) : %+.4f (N=%d)"%(C[(C.downgrade==1)&(C.contr12==1)].car6.mean(),((C.downgrade==1)&(C.contr12==1)).sum()))
print(" mean CAR6  downgrade, NOT controversy-linked        : %+.4f (N=%d)"%(C[(C.downgrade==1)&(C.contr12==0)].car6.mean(),((C.downgrade==1)&(C.contr12==0)).sum()))
# regression: incremental reaction, firm FE, cluster firm
d=C.copy(); d['dg_linked']=d.downgrade*d.contr12; d['dg_unlinked']=d.downgrade*(1-d.contr12)
fid=pd.factorize(_grp(d.ISSUERID))[0]  # cluster by ultimate parent
def dm(a): m=pd.Series(a).groupby(fid).transform('mean'); return a-m.values
Y=dm(d.car6.values); X=np.column_stack([dm(d[c].values.astype(float)) for c in ['sevonset','dg_linked','dg_unlinked']])
inv=np.linalg.pinv(X.T@X); b=inv@(X.T@Y); r=Y-X@b; sc=X*r[:,None]
import numpy as np
import glob as _g
_ref=pd.read_parquet(_g.glob('mref/HIST_MASTER_ISSUER_REFERENCE*')[0],columns=['ISSUERID','PARENT_ULTIMATE_ISSUERID']).drop_duplicates('ISSUERID')
_PMAP=dict(zip(_ref.ISSUERID,_ref.PARENT_ULTIMATE_ISSUERID))
def _grp(s):
    s=pd.Series(list(s)); return s.map(_PMAP).fillna(s).values
S=np.zeros((fid.max()+1,3))
for j in range(3): S[:,j]=np.bincount(fid,weights=sc[:,j],minlength=fid.max()+1)
V=inv@(S.T@S)@inv; se=np.sqrt(np.diag(V))
for i,nm in enumerate(['sevonset','downgrade(controversy-linked)','downgrade(not linked)']):
    print("   %s: %+.4f (t %+.1f)"%(nm,b[i],b[i]/se[i]))
