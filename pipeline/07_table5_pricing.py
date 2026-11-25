import duckdb, pandas as pd, numpy as np, statsmodels.api as sm, warnings
import glob as _g
_ref=pd.read_parquet(_g.glob('mref/HIST_MASTER_ISSUER_REFERENCE*')[0],columns=['ISSUERID','PARENT_ULTIMATE_ISSUERID']).drop_duplicates('ISSUERID')
_PMAP=dict(zip(_ref.ISSUERID,_ref.PARENT_ULTIMATE_ISSUERID))
def _grp(s):
    s=pd.Series(list(s)); return s.map(_PMAP).fillna(s).values
warnings.filterwarnings('ignore')
con=duckdb.connect(); con.sql('PRAGMA disable_progress_bar'); con.sql("PRAGMA memory_limit='3GB'"); con.sql("PRAGMA temp_directory='tmp'")
R='/mnt/user-data/uploads/monthly_total_returns__1_.csv'
IR='mref/HIST_MASTER_INSTRUMENT_REFERENCE_none_20260831.parquet'
# 1) ISSUERID -> ISIN, restricted to ISINs that appear in the returns file; if several, pick the ISIN with most return obs
con.sql(f"""CREATE OR REPLACE TABLE ret AS SELECT isin, CAST(date AS DATE) d, tri, ISSUER_CNTRY_DOMICILE ctry,
   (EXTRACT(year FROM CAST(date AS DATE))) yr, EXTRACT(month FROM CAST(date AS DATE)) mo FROM read_csv_auto('{R}') WHERE tri IS NOT NULL""")
con.sql("CREATE OR REPLACE TABLE isin_obs AS SELECT isin, COUNT(*) n, ANY_VALUE(ctry) ctry FROM ret GROUP BY isin")
con.sql(f"""CREATE OR REPLACE TABLE map AS
  WITH pairs AS (SELECT DISTINCT ISSUERID, ISIN FROM '{IR}' WHERE ISIN IS NOT NULL AND ISSUERID IS NOT NULL),
       j AS (SELECT p.ISSUERID, p.ISIN, o.n, o.ctry, ROW_NUMBER() OVER(PARTITION BY p.ISSUERID ORDER BY o.n DESC) rk FROM pairs p JOIN isin_obs o ON o.isin=p.ISIN)
  SELECT ISSUERID, ISIN, ctry FROM j WHERE rk=1""")
nmap=con.sql("SELECT COUNT(*) n FROM map").df().n[0]; print("issuers mapped to a returns ISIN:", nmap)
# 2) year-end (December) tri per isin, then forward 12m return  fwd[t] = tri(Dec t+1)/tri(Dec t) - 1
con.sql("CREATE OR REPLACE TABLE dec AS SELECT isin, yr, ARG_MAX(tri, d) tri_dec FROM ret WHERE mo=12 GROUP BY isin, yr")
con.sql("""CREATE OR REPLACE TABLE fwd AS SELECT a.isin, a.yr, (b.tri_dec/a.tri_dec - 1.0) fwd12
   FROM dec a JOIN dec b ON b.isin=a.isin AND b.yr=a.yr+1 WHERE a.tri_dec>0""")
# 3) firm-year rating-change panel
P=pd.read_parquet('panel_fy.parquet').sort_values(['ISSUERID','yr']); g=P.groupby('ISSUERID'); P['py']=g.yr.shift(1)
P['dias']=np.where(P.yr-P.py==1,P.ias-g.ias.shift(1),np.nan); P['dwas']=np.where(P.yr-P.py==1,P.was-g.was.shift(1),np.nan)
P=P.dropna(subset=['dias','dwas'])[['ISSUERID','yr','dias','dwas']]
con.register('P',P)
# 4) merge: firm-year rating change + its forward return (via ISIN map)
D=con.sql("""SELECT P.ISSUERID, P.yr, P.dias, P.dwas, f.fwd12, m.ctry
   FROM P JOIN map m ON m.ISSUERID=P.ISSUERID JOIN fwd f ON f.isin=m.ISIN AND f.yr=P.yr""").df()
D=D[D.yr.between(2018,2024)].copy()
# winsorize forward returns at 1/99
lo,hi=D.fwd12.quantile([.01,.99]); D['fwd12w']=D.fwd12.clip(lo,hi)
# own vs non-own components: b_hat from dias~dwas on this sample; nonown = residual orthogonal to dwas
bhat=np.polyfit(D.dwas,D.dias,1)[0]
D['own']=bhat*D.dwas                 # benchmarking-amplified own-score component
D['nonown']=D.dias-bhat*D.dwas       # non-own-score (benchmarking/committee/other) component, orthogonal to dwas
print("sample: firm-years with returns =",len(D),"| issuers =",D.ISSUERID.nunique(),"| years",sorted(D.yr.unique()),"| bhat=%.2f"%bhat)
print("mean fwd12 (winsor) = %.3f | sd = %.3f"%(D.fwd12w.mean(),D.fwd12w.std()))
def reg(y,xs):
    d=D.dropna(subset=[y]+xs).copy()
    d['yr']=d['yr'].astype(int)
    X=pd.concat([d[xs], pd.get_dummies(d['yr'],prefix='y',drop_first=True).astype(float), pd.get_dummies(d['ctry'],prefix='c',drop_first=True).astype(float)],axis=1)
    r=sm.OLS(d[y],sm.add_constant(X)).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(_grp(d['ISSUERID']))[0]})
    return {x:(round(r.params[x],4),round(r.tvalues[x],2)) for x in xs}, int(r.nobs)
print("\n=== PRICING VALIDATION: 12-month-forward return on components of the annual rating change (year+country FE, firm-clustered) ===")
print(" fwd12 ~ own(benchmarking-amplified WAKIS) + nonown(non-own-score):", reg('fwd12w',['own','nonown']))
print(" fwd12 ~ dias (total rating change):", reg('fwd12w',['dias']))
print(" fwd12 ~ dwas (own WAKIS change) + nonown:", reg('fwd12w',['dwas','nonown']))
# joint test that neither component is priced (Wald)
d=D.dropna(subset=['fwd12w','own','nonown']).copy(); d['yr']=d['yr'].astype(int)
X=pd.concat([d[['own','nonown']],pd.get_dummies(d['yr'],prefix='y',drop_first=True).astype(float),pd.get_dummies(d['ctry'],prefix='c',drop_first=True).astype(float)],axis=1)
r=sm.OLS(d['fwd12w'],sm.add_constant(X)).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(_grp(d['ISSUERID']))[0]})
w=r.f_test("own=0, nonown=0")
print(" joint Wald H0: own=nonown=0  -> F=%.2f  p=%.3f"%(float(w.fvalue),float(w.pvalue)))
D.to_parquet('pricing_panel.parquet')
