import duckdb, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
con=duckdb.connect('a.db'); con.sql("PRAGMA memory_limit='2GB'"); con.sql("PRAGMA temp_directory='tmp'"); con.sql('PRAGMA threads=4'); con.sql('PRAGMA disable_progress_bar')
CF='jul/HIST_CONTROVERSIES_20260731.parquet'; SS='jul/HIST_SUMMARY_SCORES_20260731.parquet'
ISS=['ACCESS_TO_FIN','ACCESS_TO_HLTHCRE','BIODIV_LAND_USE','CARBON_EMISSIONS','CHEM_SAFETY','COMM_REL','CONTROV_SRC','E_WASTE','FINANCING_ENV_IMP','FIN_PROD_SAFETY','HLTH_SAFETY','HUMAN_CAPITAL_DEV','INS_CLIMATE_CHG_RISK','LABOR_MGMT','OPPS_CLN_TECH','OPPS_GREEN_BUILDING','OPPS_NUTRI_HLTH','OPPS_RENEW_ENERGY','PACK_MAT_WASTE','PRIVACY_DATA_SEC','PROD_CARB_FTPRNT','PROD_SFTY_QUALITY','RAW_MAT_SRC','RESPONSIBLE_INVEST','SUPPLY_CHAIN_LAB','TOXIC_EMISS_WSTE','WATER_STRESS']
import glob as _g
_ref=pd.read_parquet(_g.glob('mref/HIST_MASTER_ISSUER_REFERENCE*')[0],columns=['ISSUERID','PARENT_ULTIMATE_ISSUERID']).drop_duplicates('ISSUERID')
_PMAP=dict(zip(_ref.ISSUERID,_ref.PARENT_ULTIMATE_ISSUERID))
def _grp(s):
    s=pd.Series(list(s)); return s.map(_PMAP).fillna(s).values
def fe_lpm(d,y,xs):  # firm FE (fid) ; SE clustered by ULTIMATE PARENT (gid)
    dd=d.dropna(subset=[y]+xs); fid=pd.factorize(dd['ISSUERID'])[0].astype(np.int64); nf=fid.max()+1; cnt=np.bincount(fid,minlength=nf).astype(float)
    gid=pd.factorize(_grp(dd['ISSUERID']))[0].astype(np.int64); ng=gid.max()+1
    dm=lambda a:(a.astype(float)-(np.bincount(fid,weights=a.astype(float),minlength=nf)/cnt)[fid])
    Y=dm(dd[y].values); X=np.column_stack([dm(dd[x].values) for x in xs]); inv=np.linalg.pinv(X.T@X); b=inv@(X.T@Y); r=Y-X@b; sc=X*r[:,None]
    Sm=np.column_stack([np.bincount(gid,weights=sc[:,j],minlength=ng) for j in range(len(xs))]); V=inv@(Sm.T@Sm)@inv; se=np.sqrt(np.diag(V))
    return {xs[i]:(round(float(b[i]),5),round(float(b[i]/se[i]),2)) for i in range(len(xs))}, len(dd)
# onset tables
def onset(name,like):
    con.sql(f"""CREATE OR REPLACE TABLE {name} AS WITH l AS (SELECT ISSUERID,REGEXP_REPLACE(FIELD_ID,'_(VERY_SEVERE|SEVERE|MODERATE)_CONTROVERSIES$','') issue,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE {like} AND START_DATE>=20160101), pd AS (SELECT ISSUERID,issue,START_DATE,SUM(v) s FROM l WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2,3), d AS (SELECT ISSUERID,issue,START_DATE, s-LAG(s) OVER(PARTITION BY ISSUERID,issue ORDER BY START_DATE) ds FROM pd) SELECT ISSUERID,issue,((START_DATE//10000)*12+((START_DATE//100)%100)) mi,1 ons FROM d WHERE ds>0 GROUP BY 1,2,3""")
onset('low_o',"FIELD_ID LIKE '%\\_MODERATE\\_CONTROVERSIES' ESCAPE '\\'"); onset('sev_o',"FIELD_ID LIKE '%\\_SEVERE\\_CONTROVERSIES' ESCAPE '\\'")
# monthly IAS as-of + band + firm-month low onset (for downgrade-horizon)
months=[y*100+m for y in range(2017,2027) for m in range(1,13) if not (y==2026 and m>7)]; ml='['+','.join(map(str,months))+']'
con.sql(f"""CREATE OR REPLACE TABLE fw AS
 WITH iasm AS (WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{SS}' WHERE FIELD_ID='INDUSTRY_ADJUSTED_SCORE' AND START_DATE>=20160101), s AS (SELECT ISSUERID,START_DATE,v FROM l WHERE rn=1 AND v IS NOT NULL), grid AS (SELECT DISTINCT ISSUERID,ym,((ym//100)*10000+(ym%100)*100+31) thr,((ym//100)*12+(ym%100)) midx FROM s CROSS JOIN (SELECT UNNEST({ml}) ym)) SELECT g.ISSUERID,g.midx,x.v ias FROM grid g ASOF LEFT JOIN s x ON g.ISSUERID=x.ISSUERID AND g.thr>=x.START_DATE WHERE x.v IS NOT NULL),
   lom AS (SELECT ISSUERID, mi midx, SUM(ons) lo FROM low_o GROUP BY 1,2),
   j AS (SELECT i.ISSUERID,i.midx,i.ias,COALESCE(l.lo,0) lo, CAST(floor(i.ias/(10.0/7)) AS INT) band FROM iasm i LEFT JOIN lom l ON l.ISSUERID=i.ISSUERID AND l.midx=i.midx)
 SELECT *, LAG(band) OVER w bprev,
   SUM(CASE WHEN lo>0 THEN 1 ELSE 0 END) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 6 PRECEDING AND 1 PRECEDING) lowmo6,
   MIN(band) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 1 FOLLOWING AND 12 FOLLOWING) fmin12,
   MIN(band) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 1 FOLLOWING AND 24 FOLLOWING) fmin24,
   COUNT(*) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 6 PRECEDING AND 1 PRECEDING) nprev,
   COUNT(*) OVER (PARTITION BY ISSUERID ORDER BY midx RANGE BETWEEN 1 FOLLOWING AND 12 FOLLOWING) nf12
 FROM j WINDOW w AS (PARTITION BY ISSUERID ORDER BY midx)""")
d=con.sql("SELECT ISSUERID,ias,band,lowmo6,fmin12,fmin24,nprev,nf12 FROM fw WHERE nprev>=6").df()
d['sl']=(d.lowmo6>=2).astype(float)
for H,fc in [(12,'fmin12'),(24,'fmin24')]:
    dd=d[d.nf12>=1].copy() if H==12 else d.copy(); dd=dd[dd[fc].notna()]; dd['down']=(dd[fc]<dd['band']).astype(float)
    b=fe_lpm(dd,'down',['sl','ias'])[0]['sl']; print(f"[DOWNGRADE-HORIZON {H}m] sustained-low -> downgrade (firm FE+IAS): {b[0]:+.4f} (t={b[1]:+.1f})")
del d
# cross-issue: severe onset ~ cross-issue low(prior6m) + same-issue low, firm FE
con.sql("CREATE OR REPLACE TABLE fmths AS SELECT DISTINCT ISSUERID,midx FROM fw WHERE nprev>=6 AND ISSUERID IN (SELECT DISTINCT ISSUERID FROM sev_o)")
con.sql("CREATE OR REPLACE TABLE grid AS SELECT m.ISSUERID,m.midx,i.issue FROM fmths m CROSS JOIN (SELECT UNNEST("+str(ISS)+") issue) i")
con.sql("CREATE OR REPLACE TABLE lowfm AS SELECT ISSUERID,mi midx,SUM(ons) tot FROM low_o GROUP BY 1,2")
con.sql("""CREATE OR REPLACE TABLE reg AS WITH g AS (SELECT gr.ISSUERID,gr.midx,gr.issue,COALESCE(s.ons,0) sev_on,COALESCE(li.ons,0) lsame,COALESCE(lf.tot,0) ltot FROM grid gr LEFT JOIN sev_o s ON s.ISSUERID=gr.ISSUERID AND s.mi=gr.midx AND s.issue=gr.issue LEFT JOIN low_o li ON li.ISSUERID=gr.ISSUERID AND li.mi=gr.midx AND li.issue=gr.issue LEFT JOIN lowfm lf ON lf.ISSUERID=gr.ISSUERID AND lf.midx=gr.midx), w AS (SELECT *, SUM(lsame) OVER (PARTITION BY ISSUERID,issue ORDER BY midx RANGE BETWEEN 6 PRECEDING AND 1 PRECEDING) s6, SUM(ltot) OVER (PARTITION BY ISSUERID,issue ORDER BY midx RANGE BETWEEN 6 PRECEDING AND 1 PRECEDING) t6 FROM g) SELECT ISSUERID,sev_on,CASE WHEN s6>0 THEN 1 ELSE 0 END same6,CASE WHEN (t6-s6)>0 THEN 1 ELSE 0 END cross6 FROM w""")
ci=con.sql("SELECT ISSUERID,sev_on,same6,cross6 FROM reg").df().astype({'sev_on':'int8','same6':'int8','cross6':'int8'})
print("[CROSS-ISSUE] "+str(fe_lpm(ci,'sev_on',['cross6','same6'])[0]))
