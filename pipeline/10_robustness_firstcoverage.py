# =====================================================================================
# 10_robustness_firstcoverage.py  (v33)
# Robustness checks added after reconciling the supervisor memo with the draft.
# Requires panel_fy_validtime.parquet from 02 and the July-2026 extract (jul/), mref/.
#  A. First covered year: MSCI's key-issue severity fields begin in 2019 for most issuers and
#     TOTAL_NUMBER_CONTROVERSIES in 2017-2019. In a firm's first covered year the change in a
#     zero-filled count equals its whole stock. Flag: year == first START_DATE year of either family.
#  B. Table 2 / Table 3 without first covered years (same estimator as 02, parent-clustered).
#  C. Early-window lag on the original design (TOTAL recorded in both t and t-1).
#  D. Severity x Late regression (memo Section 4) on the canonical sample, parent- and firm-clustered.
#  E. Section 6.5 monthly hazard without events in a firm's first 12 months of case-type coverage.
# Canonical sample note: 02 reads IAS records with START_DATE >= 20150101; firm-years whose
# year-end IAS was last updated before 2015 drop out (414,175 -> 401,885). Clustering drops nothing.
# =====================================================================================
import duckdb, pandas as pd, numpy as np, glob, statsmodels.api as sm, warnings
warnings.filterwarnings('ignore')
SS='jul/HIST_SUMMARY_SCORES_20260731.parquet'; CF='jul/HIST_CONTROVERSIES_20260731.parquet'
REF=glob.glob('mref/HIST_MASTER_ISSUER_REFERENCE*')[0]
con=duckdb.connect(); con.sql('PRAGMA threads=4')
P=pd.read_parquet('panel_fy_validtime.parquet')
fs=con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 fs FROM '{CF}' WHERE regexp_matches(FIELD_ID,'_(MODERATE|SEVERE|VERY_SEVERE)_CONTROVERSIES$') GROUP BY 1").df()
ft=con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 ft FROM '{CF}' WHERE FIELD_ID='TOTAL_NUMBER_CONTROVERSIES' GROUP BY 1").df()
P=P.merge(fs,on='ISSUERID',how='left').merge(ft,on='ISSUERID',how='left'); P['first']=(P.fs==P.yr)|(P.ft==P.yr)

def cl(d,y,xs,c='group'):
    d=d.dropna(subset=[y]+xs).copy(); d['yr']=d.yr.astype(int); yrs=sorted(d.yr.unique())
    X=np.column_stack([np.ones(len(d))]+[(d.yr==yy).astype(float) for yy in yrs[1:]]+[d[x].values for x in xs]); Y=d[y].values
    XtXi=np.linalg.inv(X.T@X); b=XtXi@(X.T@Y); e=Y-X@b
    S=pd.DataFrame(X*e[:,None]).groupby(d[c].values).sum().values; N,k=X.shape; G=S.shape[0]
    se=np.sqrt(np.diag((G/(G-1))*((N-1)/(N-k))*(XtXi@(S.T@S)@XtXi))); k0=len(yrs)
    return {x:(round(float(b[k0+i]),4),round(float(b[k0+i]/se[k0+i]),1)) for i,x in enumerate(xs)}

W=[2018,2019,2021,2022,2023,2024,2025]; F=P[P.yr.isin(W)].dropna(subset=['dias','d_c_sev']).copy(); G=F[~F['first']]
print(f"[A] canonical N={len(F):,}; first-covered firm-years={int(F['first'].sum()):,}", F[F['first']].groupby('yr').size().to_dict())
print("[B] Table 2 t0 (one severity per regression):")
for c in ['c_minor','c_mod','c_sev','c_vs']: print(f"    {c:8} all {cl(F,'dias',['d_'+c])} | excl first {cl(G,'dias',['d_'+c])}")
print("[B] Table 3:")
for nm,ys in [('early',[2018,2019]),('late',[2021,2022,2023,2024,2025])]:
    for lab,D in [('all',F),('excl',G)]:
        d=D[D.yr.isin(ys)]; print(f"    {nm} {lab} N={len(d):,} agg_t0 {cl(d,'dias',['d_tot'])} agg_t1 {cl(d,'dias_t1',['d_tot'])} sev_t0 {cl(d,'dias',['d_c_sev'])} sev_t1 {cl(d,'dias_t1',['d_c_sev'])}")
E=F[F.yr.isin([2018,2019])]
print("[C] early-window lag:")
for lab,D in [('all',E),('TOTAL in both years',E[E.ft<E.yr]),('+ excl severity-first',E[(E.ft<E.yr)&(E.fs!=E.yr)])]:
    print(f"    {lab:24} N={len(D):,} agg t0 {cl(D,'dias',['d_tot'])} t+1 {cl(D,'dias_t1',['d_tot'])} | resid t+1 {cl(D,'dias_t1',['d_c_minor'])}")
print("[D] severity x Late (joint):")
for lab,D in [('all',F),('excl first',G)]:
    D=D.copy(); D['Late']=(D.yr>=2021).astype(float); xs=[]
    for s in ['c_mod','c_sev','c_vs','c_minor']: D['x_'+s]=D['d_'+s]; D['xl_'+s]=D['d_'+s]*D.Late; xs+=['x_'+s,'xl_'+s]
    print(f"    {lab} parent-cl {cl(D,'dias',xs)}"); print(f"    {lab} firm-cl   {cl(D,'dias',xs,'ISSUERID')}")
# ---- E. Section 6.5 ----
mi=lambda d:(d//10000)*12+((d//100)%100); DE=mi(20260731); H=24
ias=con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{SS}' WHERE FIELD_ID='INDUSTRY_ADJUSTED_SCORE' AND START_DATE>=20160101) SELECT ISSUERID,START_DATE,v,LAG(v) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) pv FROM l WHERE rn=1 AND v IS NOT NULL""").df()
ias['dias']=ias.v-ias.pv
sev=con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE FIELD_ID LIKE 'CONTR\\_%\\_N\\_SEVERE' ESCAPE '\\' AND START_DATE>=20160101), pd AS (SELECT ISSUERID,START_DATE,SUM(v) s FROM l WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2) SELECT ISSUERID,START_DATE,s,LAG(s) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) ps, MIN(START_DATE) OVER(PARTITION BY ISSUERID) AS first_d FROM pd""").df()
ev=sev[(sev.s-sev.ps)>1e-9][['ISSUERID','START_DATE','first_d']].copy(); ev['ev']=mi(ev.START_DATE); yr=ev.START_DATE//10000
ev['era']=np.where((yr>=2018)&(yr<=2019),'early',np.where((yr>=2021)&(yr<=2025),'late','other')); ev=ev[ev.era!='other']; ev['since_first']=ev.ev-mi(ev.first_d)
dg=ias[ias.dias<-1e-9][['ISSUERID','START_DATE']].copy(); dg['dg']=mi(dg.START_DATE)
ev=pd.merge_asof(ev.sort_values('ev'),dg[['ISSUERID','dg']].sort_values('dg'),by='ISSUERID',left_on='ev',right_on='dg',direction='forward')
ev['lag']=ev.dg-ev.ev; ev['cens']=DE-ev.ev
ref=pd.read_parquet(REF,columns=['ISSUERID','PARENT_ULTIMATE_ISSUERID']).drop_duplicates('ISSUERID')
ev=ev.merge(ref,on='ISSUERID',how='left'); ev['grp']=ev.PARENT_ULTIMATE_ISSUERID.fillna(ev.ISSUERID); ev['late']=(ev.era=='late').astype(int)
def cum(k):
    c=1
    for m in range(1,H+1):
        ar=((k.lag.isna()&(k.cens>=m))|(k.lag>=m)).sum(); f=(k.lag==m).sum(); c*=1-(f/ar if ar else 0)
    return round(1-c,3)
def haz(k):
    rows=[]
    for g,late,lag,cens in zip(k.grp,k.late,k.lag.values,k.cens.values):
        h=int(min(H, lag if not np.isnan(lag) else cens))
        for m in range(1,h+1):
            f=1 if (not np.isnan(lag) and lag==m) else 0; rows.append((g,late,m,f))
            if f: break
    pm=pd.DataFrame(rows,columns=['g','late','month','fail'])
    X=sm.add_constant(pd.get_dummies(pm.month,prefix='m',drop_first=True).astype(float)); X['late']=pm.late.astype(float)
    r=sm.GLM(pm.fail,X,family=sm.families.Binomial(sm.families.links.CLogLog())).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(pm.g)[0]})
    return round(r.params['late'],3),round(r.tvalues['late'],1),round(float(np.exp(r.params['late'])),2)
print("[E] Section 6.5:")
for lab,k in [('as in paper',ev),('excl first 12m of coverage',ev[ev.since_first>=12])]:
    print(f"    {lab:28} early N={int((k.era=='early').sum()):,} cum24={cum(k[k.era=='early'])} | late N={int((k.era=='late').sum()):,} cum24={cum(k[k.era=='late'])} | cloglog late {haz(k)}")
