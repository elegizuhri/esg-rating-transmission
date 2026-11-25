#!/usr/bin/env python3
"""
score_predicts_returns_fundamentals.py — does the ESG rating (IAS) predict the future?

  (A) FORWARD RETURNS   : year-end IAS[t] -> next-12-month market-adjusted return.
  (B) FORWARD FUNDAMENTALS: year-end IAS[t] -> next-year operating ROA (oibdp/at),
                            controlling for current ROA.

Both at the ultimate-parent level (returns and Compustat are keyed by parent_id, which is
the same IID identifier as the panel's PARENT_ULTIMATE_ISSUERID). Year fixed effects;
standard errors clustered by parent. Scores aggregated to the parent-year by mean.
Estimated on the paper's canonical sample window: base year t in 2018-2025 excluding 2020
(so forward outcomes fall in 2019-2025), matching Tables 2/5 and the rest of the draft.

Inputs (licensed, not shipped):
  w2/panel_fy_validtime.parquet            issuer-year IAS/WAKIS + PARENT_ULTIMATE_ISSUERID
  p2/kit/data/returns.parquet              parent-month market-adjusted return (ra), midx=year*12+month
  w2/wrds_extra/compustat_annual.parquet   parent-year fundamentals (oibdp, at)

Run:  python score_predicts_returns_fundamentals.py   (writes P4_score_predicts.csv)
"""
import os, numpy as np, pandas as pd, statsmodels.api as sm

W = os.environ.get("W", "w2"); KIT = os.environ.get("KIT", "p2/kit/data")
z = lambda s: (s - s.mean()) / s.std()
KEEP = [2018, 2019, 2021, 2022, 2023, 2024, 2025]   # paper window: 2018-2025 excl. 2020 (base year t)

def creg(d, y, xs, cl="pid"):
    d = d.dropna(subset=[y] + xs + [cl]).copy(); d["yr"] = d["yr"].astype(int); yrs = sorted(d["yr"].unique())
    X = np.column_stack([np.ones(len(d))] + [(d["yr"] == yy).astype(float) for yy in yrs[1:]] + [d[x].values for x in xs])
    r = sm.OLS(d[y].values, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d[cl])[0]})
    p = len(xs); return [(xs[i], round(r.params[-p + i], 4), round(r.tvalues[-p + i], 1)) for i in range(p)], len(d), d[cl].nunique()

# parent-year ESG rating (IAS), year-end, from the valid-time panel
P = pd.read_parquet(f"{W}/panel_fy_validtime.parquet")[["yr", "ias", "PARENT_ULTIMATE_ISSUERID"]].rename(columns={"PARENT_ULTIMATE_ISSUERID": "pid"})
pg = P.groupby(["pid", "yr"]).agg(ias=("ias", "mean")).reset_index()

rows = []
# ---------- (A) forward returns ----------
ret = pd.read_parquet(f"{KIT}/returns.parquet"); ret["pid"] = ret.parent_id.astype(str)
lo, hi = ret.ra.quantile([.005, .995]); ret["raw_"] = ret.ra.clip(lo, hi)   # winsorise monthly return at 0.5/99.5, matching the Appendix H return tests
ret = ret.sort_values(["pid", "midx"]); g = ret.groupby("pid")
ret["f12"] = sum(g["raw_"].shift(-k) for k in range(1, 13)); ret["f12"] = ret["f12"].where(g["midx"].shift(-12) == ret["midx"] + 12)
ret["b12"] = sum(g["raw_"].shift(k) for k in range(0, 12))
dec = ret[ret["midx"] % 12 == 0].copy(); dec["yr"] = dec["midx"] // 12 - 1
R = pg.merge(dec[["pid", "yr", "f12", "b12"]], on=["pid", "yr"], how="inner")
R = R[R["yr"].isin(KEEP)].copy(); R["zias"] = z(R["ias"])
res, N, ncl = creg(R, "f12", ["zias"])
rows.append(dict(test="Next-12m market-adjusted return ~ IAS[t]", ias_coef_per_SD=res[0][1], ias_t=res[0][2], control="none", N=N, parents=ncl))
res2, N2, ncl2 = creg(R.dropna(subset=["b12"]), "f12", ["zias", "b12"])
rows.append(dict(test="Next-12m return ~ IAS[t] (+ past-12m return)", ias_coef_per_SD=res2[0][1], ias_t=res2[0][2], control="past-12m return", N=N2, parents=ncl2))

# ---------- (B) forward fundamentals ----------
comp = pd.read_parquet(f"{W}/wrds_extra/compustat_annual.parquet"); comp["pid"] = comp.parent_id.astype(str)
comp["at"] = pd.to_numeric(comp["at"], errors="coerce"); comp["yr"] = pd.to_datetime(comp.datadate).dt.year
comp["roa"] = (pd.to_numeric(comp.oibdp, errors="coerce") / comp["at"]).where(comp["at"] > 0).clip(-1, 1)
cm = comp[comp["at"] > 0].groupby(["pid", "yr"]).agg(roa=("roa", "mean")).reset_index().sort_values(["pid", "yr"])
cm["roa_next"] = cm.groupby("pid")["roa"].shift(-1); cm["ny"] = cm.groupby("pid")["yr"].shift(-1)
cm = cm[cm["ny"] - cm["yr"] == 1]
Fd = pg.merge(cm, on=["pid", "yr"], how="inner")
Fd = Fd[Fd["yr"].isin(KEEP)].dropna(subset=["roa_next", "roa", "ias"]).copy(); Fd["zias"] = z(Fd["ias"])
res, N, ncl = creg(Fd, "roa_next", ["zias", "roa"])
rows.append(dict(test="Next-year operating ROA ~ IAS[t] (+ current ROA)", ias_coef_per_SD=res[0][1], ias_t=res[0][2],
                 control=f"current ROA {res[1][1]} (t={res[1][2]})", N=N, parents=ncl))

T = pd.DataFrame(rows)
print(T.to_string(index=False))
print(f"\nmean forward-12m return = {R['f12'].mean()*100:.1f}% ; mean ROA = {Fd['roa'].mean():.3f} (sd {Fd['roa'].std():.3f})")
T.to_csv("P4_score_predicts.csv", index=False)
print("wrote P4_score_predicts.csv")
