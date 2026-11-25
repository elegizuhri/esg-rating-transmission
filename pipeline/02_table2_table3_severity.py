# =====================================================================================
# 02_table2_table3_severity.py  (v25 — BITEMPORALLY CORRECTED)
# Table 2 (severity levels: count + binding), Table 3 (early vs late), Appendix Table A2.
#
# CORRECTIONS baked in (vs the earlier version):
#  1. VALID-TIME controversy counts: a controversy field counts in year t only if
#     START_DATE <= Dec31(t) <= END_DATE. The earlier "latest START_DATE" as-of (a)
#     ignored END_DATE and (b) summed co-dated fields before the as-of, which jointly
#     mis-measured the per-severity counts (notably around the Aug-2020 reissue).
#  2. ULTIMATE-PARENT clustering: SE clustered by PARENT_ULTIMATE_ISSUERID (subsidiaries
#     inherit a parent's rating and are not independent).  Parents-only = robustness.
#  3. BINDING treatment: per Key Issue, the single highest-severity controversy (MSCI's
#     single-highest-deduction rule); binding count at level s = # issues whose max = s.
#  The IAS outcome and the TOTAL_NUMBER_CONTROVERSIES field chain continuously and are
#  unaffected; only the per-severity decomposition changes.
# =====================================================================================
import duckdb, pandas as pd, numpy as np, glob, warnings
warnings.filterwarnings('ignore')
con=duckdb.connect(); con.sql("PRAGMA memory_limit='3GB'"); con.sql("PRAGMA temp_directory='tmp'"); con.sql('PRAGMA threads=4'); con.sql('PRAGMA disable_progress_bar')
SS='jul/HIST_SUMMARY_SCORES_20260731.parquet'; CF='jul/HIST_CONTROVERSIES_20260731.parquet'
REF=glob.glob('mref/HIST_MASTER_ISSUER_REFERENCE*')[0]
yl='['+','.join(str(y) for y in range(2016,2027))+']'

def asof_total(field, src):
    # continuous-chaining fields (IAS, TOTAL): latest START_DATE <= year-end
    return con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,
        ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
        FROM '{src}' WHERE FIELD_ID='{field}' AND START_DATE>=20150101),
      s AS (SELECT ISSUERID,START_DATE,v FROM l WHERE rn=1 AND v IS NOT NULL),
      g AS (SELECT DISTINCT ISSUERID,y,y*10000+1231 thr FROM s CROSS JOIN (SELECT UNNEST({yl}) y))
      SELECT g.ISSUERID,g.y yr,x.v FROM g ASOF LEFT JOIN s x ON g.ISSUERID=x.ISSUERID AND g.thr>=x.START_DATE WHERE x.v IS NOT NULL""").df()

def validtime_severity():
    # per (issuer, issue, year): valid-time value at year-end for mod/sev/vs (START<=thr<=END)
    return con.sql(f"""
    WITH raw AS (SELECT ISSUERID, REGEXP_REPLACE(FIELD_ID,'_(VERY_SEVERE|SEVERE|MODERATE)_CONTROVERSIES$','') issue,
        CASE WHEN FIELD_ID LIKE '%VERY\\_SEVERE\\_CONTROVERSIES' ESCAPE '\\' THEN 'vs'
             WHEN FIELD_ID LIKE '%\\_MODERATE\\_CONTROVERSIES' ESCAPE '\\' THEN 'mod' ELSE 'sev' END lvl,
        START_DATE, END_DATE, TRY_CAST(VALUE AS DOUBLE) v,
        ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
        FROM '{CF}' WHERE (FIELD_ID LIKE '%\\_MODERATE\\_CONTROVERSIES' ESCAPE '\\'
                        OR FIELD_ID LIKE '%\\_SEVERE\\_CONTROVERSIES' ESCAPE '\\'
                        OR FIELD_ID LIKE '%VERY\\_SEVERE\\_CONTROVERSIES' ESCAPE '\\')),
     r AS (SELECT ISSUERID,issue,lvl,START_DATE,END_DATE,v FROM raw WHERE rn=1 AND v IS NOT NULL),
     grid AS (SELECT DISTINCT ISSUERID,issue,lvl,y,y*10000+1231 thr FROM r CROSS JOIN (SELECT UNNEST({yl}) y)),
     valid AS (SELECT g.ISSUERID,g.issue,g.lvl,g.y,x.v,
                 ROW_NUMBER() OVER(PARTITION BY g.ISSUERID,g.issue,g.lvl,g.y ORDER BY x.START_DATE DESC) rn2
               FROM grid g JOIN r x ON x.ISSUERID=g.ISSUERID AND x.issue=g.issue AND x.lvl=g.lvl
                                    AND x.START_DATE<=g.thr AND x.END_DATE>=g.thr),
     iv AS (SELECT ISSUERID,issue,y, MAX(CASE WHEN lvl='mod' THEN v END) m,
                   MAX(CASE WHEN lvl='sev' THEN v END) s, MAX(CASE WHEN lvl='vs' THEN v END) vv
            FROM valid WHERE rn2=1 GROUP BY 1,2,3)
     SELECT ISSUERID, y yr, SUM(COALESCE(m,0)) c_mod, SUM(COALESCE(s,0)) c_sev, SUM(COALESCE(vv,0)) c_vs,
       SUM(CASE WHEN COALESCE(vv,0)>0 THEN 1 ELSE 0 END) b_vs,
       SUM(CASE WHEN COALESCE(vv,0)=0 AND COALESCE(s,0)>0 THEN 1 ELSE 0 END) b_sev,
       SUM(CASE WHEN COALESCE(vv,0)=0 AND COALESCE(s,0)=0 AND COALESCE(m,0)>0 THEN 1 ELSE 0 END) b_mod
     FROM iv GROUP BY 1,2""").df()

ias=asof_total('INDUSTRY_ADJUSTED_SCORE',SS).rename(columns={'v':'ias'})
tot=asof_total('TOTAL_NUMBER_CONTROVERSIES',CF).rename(columns={'v':'tot'})
was=asof_total('WEIGHTED_AVERAGE_SCORE',SS).rename(columns={'v':'was'})
sev=validtime_severity()
ref=pd.read_parquet(REF,columns=['ISSUERID','PARENT_ULTIMATE_ISSUERID']).drop_duplicates('ISSUERID')
P=ias.merge(tot,on=['ISSUERID','yr'],how='outer').merge(was,on=['ISSUERID','yr'],how='outer').merge(sev,on=['ISSUERID','yr'],how='left').merge(ref,on='ISSUERID',how='left')
P['group']=P['PARENT_ULTIMATE_ISSUERID'].fillna(P['ISSUERID'])
for c in ['tot','c_mod','c_sev','c_vs','b_mod','b_sev','b_vs']: P[c]=P[c].fillna(0)
P['c_minor']=(P['tot']-(P.c_mod+P.c_sev+P.c_vs)).clip(lower=0)          # proper residual
P=P.sort_values(['ISSUERID','yr']); g=P.groupby('ISSUERID'); P['py']=g.yr.shift(1); P['ny1']=g.yr.shift(-1)
for c in ['c_minor','c_mod','c_sev','c_vs','b_mod','b_sev','b_vs','tot']:
    P['d_'+c]=np.where(P.yr-P.py==1, P[c]-g[c].shift(1), np.nan)
P['dias']=np.where(P.yr-P.py==1, P.ias-g.ias.shift(1), np.nan)
P['dwas']=np.where(P.yr-P.py==1, P.was-g.was.shift(1), np.nan)
P['dias_t1']=np.where(P.ny1-P.yr==1, g.ias.shift(-1)-P.ias, np.nan)

def clustered(dat,y,x,cluster):
    d=dat.dropna(subset=[y,x,cluster]).copy()
    if len(d)<30 or d[x].std()==0: return (np.nan,np.nan,len(d))
    d['yr']=d.yr.astype(int); yrs=sorted(d.yr.unique())
    X=np.column_stack([np.ones(len(d))]+[(d.yr==yy).astype(float) for yy in yrs[1:]]+[d[x].values]); Y=d[y].values
    XtXi=np.linalg.inv(X.T@X); b=XtXi@(X.T@Y); e=Y-X@b
    S=pd.DataFrame(X*e[:,None]).groupby(d[cluster].values).sum().values; meat=S.T@S
    N,k=X.shape; G=S.shape[0]; c=(G/(G-1))*((N-1)/(N-k)); se=np.sqrt(np.diag(c*(XtXi@meat@XtXi)))
    return round(b[-1],4), round(b[-1]/se[-1],1), int(N)

F=P[P.yr.isin([2018,2019,2021,2022,2023,2024,2025])]; FP=F[F.PARENT_ULTIMATE_ISSUERID.isna()]
print("=== TABLE 2: severity levels (valid-time; cluster=ultimate parent | parents-only) ===")
for lab,cc,bb in [('Minor/residual','c_minor',None),('Moderate','c_mod','b_mod'),('Severe','c_sev','b_sev'),('Very severe','c_vs','b_vs')]:
    t0=clustered(F,'dias','d_'+cc,'group'); t1=clustered(F,'dias_t1','d_'+cc,'group')
    po=clustered(FP,'dias','d_'+cc,'group')
    bind=clustered(F,'dias','d_'+bb,'group') if bb else (None,)
    print(f"  {lab:14} mean {F[cc].mean():6.3f} | t0 {t0[0]:+.4f}({t0[1]:+.1f})  t+1 {t1[0]:+.4f}({t1[1]:+.1f})  PO_t0 {po[0]:+.4f}({po[1]:+.1f})"
          + (f"  BINDING {bind[0]:+.4f}({bind[1]:+.1f})" if bb else ""))
print("\n=== TABLE 3: early vs late (cluster=ultimate parent) ===")
for nm,ys in [('early',[2018,2019]),('late',[2021,2022,2023,2024,2025]),('full',[2018,2019,2021,2022,2023,2024,2025])]:
    d=P[P.yr.isin(ys)]
    print(f"  [{nm:5}] agg_t0 {clustered(d,'dias','d_tot','group')[:2]}  agg_t1 {clustered(d,'dias_t1','d_tot','group')[:2]}  sev_t0 {clustered(d,'dias','d_c_sev','group')[:2]}  sev_t1 {clustered(d,'dias_t1','d_c_sev','group')[:2]}")
print("\n=== APPENDIX A2: year-by-year severe (cluster=ultimate parent) ===")
for Y in range(2018,2027):
    print(f"  {Y}: sev {clustered(P[P.yr==Y],'dias','d_c_sev','group')[:2]}  agg {clustered(P[P.yr==Y],'dias','d_tot','group')[:2]}")
# save corrected panel + exhibit CSVs for downstream scripts
P.to_parquet('panel_fy_validtime.parquet')
print("\nsaved panel_fy_validtime.parquet ; N(analysis)=",F.dropna(subset=['dias','d_c_sev']).shape[0])
