#!/usr/bin/env python3
"""
F1_daily_CAR_61_125.py  —  Reconciles the daily and monthly post-downgrade results (comment 321, Section 7.2).

WHY: Section 7.2 reports "no drift in the 60 trading days after a downgrade" (daily four-factor),
     while Appendix H reports a -2.8% four-factor decline over months +1 to +6 (monthly).
     These are not in conflict: 60 trading days is ~3 months, so the monthly drift accumulates
     mostly AFTER day +60. This script measures the daily four-factor CAR over the window [+61, +125]
     (about months +3 to +6) on the SAME downgrades, to confirm the drift appears there.

INPUT (you supply from WRDS; not in the cloud workspace):
  crsp_daily   : firm-level CRSP daily stock file  (permno, date, ret)       -> crsp.dsf
  ff_daily     : Fama-French + Carhart daily factors (date, mktrf, smb, hml, umd, rf)
  downgrades   : the downgrade events used in Table 10 Panel B / Appendix H
                 (permno, downgrade_date); the US-listed downgrade sample.

OUTPUT: mean four-factor CAR and t over [+61,+125], printed and saved to F1_daily_CAR_61_125.csv.
RUN:    python3 F1_daily_CAR_61_125.py   (edit the three paths below)
"""
import pandas as pd, numpy as np, statsmodels.api as sm

CRSP = "crsp_daily.parquet"      # permno, date, ret
FF   = "ff_daily.parquet"        # date, mktrf, smb, hml, umd, rf
DG   = "downgrades_us.parquet"   # permno, downgrade_date

FAC = ["mktrf","smb","hml","umd"]
ff  = pd.read_parquet(FF); ff["date"] = pd.to_datetime(ff.date)
crsp= pd.read_parquet(CRSP); crsp["date"] = pd.to_datetime(crsp.date)
dg  = pd.read_parquet(DG);  dg["downgrade_date"] = pd.to_datetime(dg.downgrade_date)

# trading-day index so we can count event-days (+61..+125) off each downgrade
cal = ff[["date"]].sort_values("date").reset_index(drop=True); cal["td"] = np.arange(len(cal))
td  = dict(zip(cal.date, cal.td))

m = crsp.merge(ff, on="date", how="inner")
m["exc"] = m.ret - m.rf
m["td"]  = m.date.map(td)

def firm_abn(g):
    # estimate the four-factor loadings on the firm's own [-250,-11] pre-window, then abnormal = exc - fitted
    g = g.dropna(subset=["exc"]+FAC)
    if len(g) < 60: return pd.Series(np.nan, index=g.index)
    b = sm.OLS(g.exc, sm.add_constant(g[FAC])).fit().params
    return g.exc - (b["const"] + (g[FAC]*b[FAC.__class__(FAC)]).sum(axis=1))

rows = []
for _, e in dg.iterrows():
    t0 = td.get(e.downgrade_date);  g = m[m.permno == e.permno]
    if t0 is None or g.empty: continue
    est = g[(g.td >= t0-250) & (g.td <= t0-11)]
    win = g[(g.td >= t0+61) & (g.td <= t0+125)]
    if len(est) < 60 or len(win) < 40: continue
    bb = sm.OLS(est.exc, sm.add_constant(est[FAC])).fit().params
    abn = win.exc - (bb["const"] + (win[FAC]*bb[FAC]).sum(axis=1))
    rows.append(abn.sum())                      # CAR over [+61,+125]

car = np.array(rows); t = car.mean()/ (car.std(ddof=1)/np.sqrt(len(car)))
print(f"Daily four-factor CAR over [+61,+125]: {car.mean()*100:+.2f}%  (t = {t:+.2f}, N = {len(car)})")
pd.DataFrame({"window":["+61..+125"],"CAR_pct":[car.mean()*100],"t":[t],"N":[len(car)]}).to_csv("F1_daily_CAR_61_125.csv", index=False)
