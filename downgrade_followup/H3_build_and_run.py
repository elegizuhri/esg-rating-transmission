#!/usr/bin/env python3
"""
H3_build_and_run.py — rebuild the downgrade event-study kit from the raw MSCI + return files and
run the two tests Giovanna asked for (comments 638/946) plus the backfill/re-rating robustness (640).

Unlike the earlier H3_followup_tests.py (which assumed a pre-built CRSP kit), this version builds the
kit from the files actually available:

  INPUTS
    HIST_SUMMARY_SCORES_20260731.parquet               MSCI scores: IVA_COMPANY_RATING (letter), INDUSTRY_ADJUSTED_SCORE
    HIST_MASTER_INSTRUMENT_REFERENCE_*.parquet         ISSUERID <-> ISIN (ASSET_TYPE='CMN')
    monthly_total_returns.csv                          global monthly total returns by ISIN (tr_return_pct, country)
    ff_monthly.parquet                                 Fama-French + Carhart factors (mktrf, smb, hml, umd, rf)

  BUILD
    ratings:  letter -> band (AAA=7..CCC=1); a downgrade is band < previous band, dated at START_DATE.
    returns:  ISIN monthly total return (/100) -> ISSUERID (median across the issuer's common shares);
              market-adjusted 'ra' = return minus the country-month mean (as in the Table H3 note);
              momentum-matched 'cmadj' = ra minus the mean of its country x month x prior-12m-return tercile;
              four-factor 'ff4' (US-listed only) = excess return minus a firm's fitted Carhart four-factor expectation.

  TESTS
    (a) month-0 return vs the mean of months -6..-1 and +1..+6, firm-clustered difference t (comment 946).
    (b) the balanced -6..+6 event-time path under market-adjusted, momentum-matched and four-factor returns (comment 638).
    robustness: 6-month forward drift excl. 2019 backfill / mass re-rating dates / by sub-period, and a past-6m control (640).

Run:  python3 H3_build_and_run.py      (set the paths below)
"""
import os, duckdb, pandas as pd, numpy as np, statsmodels.api as sm

SS  = os.environ.get("SS",  "HIST_SUMMARY_SCORES_20260731.parquet")
IR  = os.environ.get("IR",  "HIST_MASTER_INSTRUMENT_REFERENCE_none_20260831.parquet")
RET = os.environ.get("RET", "monthly_total_returns.csv")
FF  = os.environ.get("FF",  "ff_monthly.parquet")
con = duckdb.connect(); con.sql("PRAGMA threads=4")
BAND = {"AAA":7,"AA":6,"A":5,"BBB":4,"BB":3,"B":2,"CCC":1}
ct = lambda y,g: float(sm.OLS(np.asarray(y,float),np.ones((len(y),1))).fit(cov_type="cluster",cov_kwds={"groups":pd.factorize(g)[0]}).tvalues[0])
wins = lambda s:(lambda lo,hi:s.clip(lo,hi))(*s.quantile([.005,.995]))

# ---------- ratings / downgrades ----------
lett=con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,VALUE,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
   FROM '{SS}' WHERE FIELD_ID='IVA_COMPANY_RATING' AND START_DATE>=20150101) SELECT ISSUERID,START_DATE,VALUE letter FROM l WHERE rn=1""").df()
lett["band"]=lett.letter.map(BAND); lett=lett.dropna(subset=["band"]).sort_values(["ISSUERID","START_DATE"])
lett["pband"]=lett.groupby("ISSUERID").band.shift(1)
dg=lett[lett.band<lett.pband].rename(columns={"ISSUERID":"parent_id","START_DATE":"start"}).copy()
dg["d"]=pd.to_datetime(dg.start.astype(int).astype(str),format="%Y%m%d"); dg["midx"]=dg.d.dt.year*12+dg.d.dt.month
dg=dg.reset_index(drop=True); dg["ev"]=dg.index
print("downgrades:",len(dg))

# ---------- returns ----------
link=con.sql(f"SELECT ISIN, ANY_VALUE(ISSUERID) issuerid FROM '{IR}' WHERE ISIN IS NOT NULL AND ASSET_TYPE='CMN' GROUP BY ISIN").df()
ret=con.sql(f"""WITH r AS (SELECT isin, ISSUER_CNTRY_DOMICILE ctry, CAST(date AS DATE) dt, TRY_CAST(tr_return_pct AS DOUBLE)/100.0 r FROM read_csv_auto('{RET}'))
  SELECT l.issuerid parent_id, ANY_VALUE(r.ctry) ctry, (EXTRACT(year FROM r.dt)*12+EXTRACT(month FROM r.dt))::INT midx, median(r.r) r
  FROM r JOIN link l ON r.isin=l.ISIN WHERE r.r IS NOT NULL GROUP BY 1,3""").df()
ret["ra"]=ret.r-ret.groupby(["ctry","midx"]).r.transform("mean")
ret=ret.sort_values(["parent_id","midx"]); g=ret.groupby("parent_id")
ret["mom"]=sum(g.r.shift(k) for k in range(1,13))
ret["mb"]=ret.groupby(["ctry","midx"]).mom.transform(lambda s: pd.qcut(s,3,labels=False,duplicates="drop") if s.notna().sum()>=9 else np.nan)
ret["cmadj"]=ret.ra-ret.groupby(ret.ctry.astype(str)+ret.midx.astype(str)+ret.mb.astype("Int64").astype(str)).ra.transform("mean")
ff=pd.read_parquet(FF); ff["midx"]=ff.year.astype(int)*12+ff.month.astype(int)
us=ret[ret.ctry=="US"].merge(ff[["midx","mktrf","smb","hml","umd","rf"]],on="midx",how="left"); us["exc"]=us.r-us.rf
FAC=["mktrf","smb","hml","umd"]
def resid(gp):
    gp=gp.dropna(subset=["exc"]+FAC)
    if len(gp)<24: return pd.Series(np.nan,index=gp.index)
    b=sm.OLS(gp.exc,sm.add_constant(gp[FAC])).fit().params; return gp.exc-(b["const"]+(gp[FAC]*b[FAC]).sum(axis=1))
us["ff4"]=us.groupby("parent_id",group_keys=False).apply(resid)
ret=ret.merge(us[["parent_id","midx","ff4"]],on=["parent_id","midx"],how="left")

def path_and_contrast(col,label,sub=None):
    r=(ret if sub is None else ret[sub]); rr=r[["parent_id","midx",col]].dropna().copy(); rr["x"]=wins(rr[col])
    E=dg[["ev","parent_id","midx"]].merge(pd.DataFrame({"k":range(-6,7)}),how="cross"); E["tgt"]=E.midx+E.k
    E=E.merge(rr[["parent_id","midx","x"]].rename(columns={"midx":"tgt"}),on=["parent_id","tgt"],how="inner").dropna(subset=["x"])
    B=E[E.ev.isin(E.groupby("ev").k.count().pipe(lambda s:s[s==13]).index)]
    print(f"\n### {label} (N={B.ev.nunique()})")
    for a,b,lab in [(-6,-1,"before"),(0,0,"month0"),(1,6,"after")]:
        s=B[B.k.between(a,b)].groupby("ev").agg(x=("x","sum"),pid=("parent_id","first")).reset_index()
        print(f"   {lab:7s} {s.x.mean()*100:+.2f}%  t={ct(s.x,s.pid):+.2f}")
    fl=B[B.k!=0].groupby("ev").agg(f=("x","mean"),pid=("parent_id","first")).reset_index()
    z=B[B.k==0][["ev","x"]].rename(columns={"x":"m0"}); c=fl.merge(z,on="ev"); c["diff"]=c.m0-c.f
    print(f"   TEST(a): month0={c.m0.mean()*100:+.2f}% flank={c.f.mean()*100:+.2f}% diff={c['diff'].mean()*100:+.2f}pp t={ct(c['diff'],c.pid):+.2f} N={len(c)}")

path_and_contrast("ra","(RA) market-adjusted, full")
path_and_contrast("cmadj","(b2) momentum-matched, full")
path_and_contrast("ff4","(b1) four-factor abnormal, US-listed", sub=(ret.ctry=="US"))

# robustness
for col,name in [("ra","market-adjusted"),("cmadj","momentum-matched")]:
    r=ret.copy(); r["w"]=wins(r[col]); g=r.sort_values(["parent_id","midx"]).groupby("parent_id")
    r["f6"]=sum(g.w.shift(-k) for k in range(1,7)); r["f6"]=r.f6.where(g.midx.shift(-6)==r.midx+6)
    r["b6"]=sum(g.w.shift(k) for k in range(0,6)); r["b6"]=r.b6.where(g.midx.shift(5)==r.midx-5)
    F=dg.merge(r[["parent_id","midx","f6","b6"]],on=["parent_id","midx"],how="left").dropna(subset=["f6"])
    F["ds"]=F.d.dt.strftime("%Y-%m-%d"); batch=set(F.ds.value_counts()[F.ds.value_counts()>150].index)
    print(f"\n=== 6m forward drift robustness [{name}] ===")
    for d_,l in [(F,"baseline"),(F[~F.ds.isin(batch)],"excl re-rating/backfill dates"),(F[F.d.dt.year!=2019],"excl 2019"),
                 (F[~F.d.dt.year.isin([2019,2020])],"excl 2019-2020"),(F[F.d.dt.year>=2021],"2021+"),(F[F.d.dt.year<=2018],"pre-2019")]:
        print(f"   {l:30s} {d_.f6.mean()*100:+.2f}%  t={ct(d_.f6,d_.parent_id):+.2f}  N={len(d_)}")
