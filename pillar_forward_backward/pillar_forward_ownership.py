#!/usr/bin/env python3
"""
pillar_forward_ownership.py — three analyses added for the E/S/G pillar split and the
forward- vs backward-looking question:

  (1) PILLAR split of the severity-graded incorporation (Table 2 spec: binding measure,
      year FE, ultimate-parent clustering, 2018-2025 excl. 2020, first-coverage-robust).
  (2) FORWARD-LOOKING test: does a firm's ESG pillar SCORE at t predict a severe
      controversy in that pillar at t+1, controlling for the current controversy?
  (3) OWNERSHIP WEIGHT: ESG-mandated mutual-fund ownership as a share of shares outstanding.

Inputs (licensed, not shipped):
  evt/panelA_vt_july.parquet          per (issuer, issue, year) valid-time mod/sev/vsev counts
  w2/panel_fy_validtime.parquet       issuer-year panel with dias, py, group
  w2/jul/HIST_CONTROVERSIES_*.parquet, HIST_SUMMARY_SCORES_*.parquet
  w2/crsp_ownership/mandate_ownership_quarterly.csv

Run:  python pillar_forward_ownership.py       (writes P1_*.csv, P2_*.csv, P3_*.csv + an Excel)
"""
import os, numpy as np, pandas as pd, duckdb, statsmodels.api as sm

EVT = os.environ.get("EVT", "evt"); W = os.environ.get("W", "w2")
SS = f"{W}/jul/HIST_SUMMARY_SCORES_20260731.parquet"; CF = f"{W}/jul/HIST_CONTROVERSIES_20260731.parquet"
PILLAR = {**{k: "E" for k in ["BIODIV_LAND_USE", "E_WASTE", "FINANCING_ENV_IMP", "PACK_MAT_WASTE",
                              "RAW_MAT_SRC", "TOXIC_EMISS", "WATER_STRESS"]},
          **{k: "G" for k in ["BUS_ETHICS_ANTICOMP", "BUS_ETHICS_CORRUPTION", "BUS_ETHICS_ETHICSFRAUD"]}}
pillar_of = lambda s: PILLAR.get(s, "S")
con = duckdb.connect(); con.sql("PRAGMA threads=4")

def clustered(d, y, xs, cl="group"):
    d = d.dropna(subset=[y] + xs + [cl]).copy(); d["yr"] = d["yr"].astype(int); yrs = sorted(d["yr"].unique())
    X = np.column_stack([np.ones(len(d))] + [(d["yr"] == yy).astype(float) for yy in yrs[1:]] + [d[x].values for x in xs])
    Y = d[y].values; XtXi = np.linalg.inv(X.T @ X); b = XtXi @ (X.T @ Y); e = Y - X @ b
    S = pd.DataFrame(X * e[:, None]).groupby(d[cl].values).sum().values
    N, k = X.shape; G = S.shape[0]; c = (G / (G - 1)) * ((N - 1) / (N - k))
    se = np.sqrt(np.diag(c * (XtXi @ (S.T @ S) @ XtXi))); p = len(xs)
    return {x: (round(b[-p + i], 4), round(b[-p + i] / se[-p + i], 1)) for i, x in enumerate(xs)}, len(d), G

# ============== (1) PILLAR split of incorporation ==============
A = pd.read_parquet(f"{EVT}/panelA_vt_july.parquet"); A["pillar"] = A["issue"].map(pillar_of)
A["lvl"] = np.where(A["vsev"] > 0, "vs", np.where(A["sev"] > 0, "sev", np.where(A["mod"] > 0, "mod", "none")))
def bcount(level, pre):
    b = A[A["lvl"] == level].groupby(["ISSUERID", "yr", "pillar"]).size().unstack("pillar", fill_value=0).reset_index()
    b.columns = ["ISSUERID", "yr"] + [f"{pre}_{c}" for c in b.columns[2:]]; return b
bs, bv = bcount("sev", "bsev"), bcount("vs", "bvs")
P = pd.read_parquet(f"{W}/panel_fy_validtime.parquet")[["ISSUERID", "yr", "dias", "py", "group"]]
fs = con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 fs FROM '{CF}' WHERE regexp_matches(FIELD_ID,'_(MODERATE|SEVERE|VERY_SEVERE)_CONTROVERSIES$') GROUP BY 1").df()
ft = con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 ft FROM '{CF}' WHERE FIELD_ID='TOTAL_NUMBER_CONTROVERSIES' GROUP BY 1").df()
P = P.merge(fs, on="ISSUERID", how="left").merge(ft, on="ISSUERID", how="left"); P["first"] = (P["fs"] == P["yr"]) | (P["ft"] == P["yr"])
m = P.merge(bs, on=["ISSUERID", "yr"], how="left").merge(bv, on=["ISSUERID", "yr"], how="left")
cols = [c for c in m.columns if c.startswith(("bsev_", "bvs_"))]
for c in cols: m[c] = m[c].fillna(0)
lagp = m[["ISSUERID", "yr"] + cols].rename(columns={"yr": "py", **{c: c + "_p" for c in cols}})
m = m.merge(lagp, on=["ISSUERID", "py"], how="left")
for c in cols:
    m[c + "_p"] = m[c + "_p"].fillna(0); m["d_" + c] = np.where(m["yr"] - m["py"] == 1, m[c] - m[c + "_p"], np.nan)
F = m[m["yr"].isin([2018, 2019, 2021, 2022, 2023, 2024, 2025])].dropna(subset=["dias"]).copy()
rows = []
for lab, D in [("Full (2020 excl.)", F), ("Excl. first-covered", F[~F["first"]])]:
    sev, N, ncl = clustered(D, "dias", ["d_bsev_E", "d_bsev_S", "d_bsev_G"])
    vs, _, _ = clustered(D, "dias", ["d_bvs_E", "d_bvs_S", "d_bvs_G"])
    for p in ["E", "S", "G"]:
        rows.append(dict(sample=lab, pillar=p, severe_coef=sev[f"d_bsev_{p}"][0], severe_t=sev[f"d_bsev_{p}"][1],
                         vsev_coef=vs[f"d_bvs_{p}"][0], vsev_t=vs[f"d_bvs_{p}"][1], N=N, clusters=ncl))
P1 = pd.DataFrame(rows); P1.to_csv("P1_pillar_incorporation.csv", index=False)
# frequency table
freq = []
for lvl in ["mod", "sev", "vsev"]:
    g = A[A[lvl] > 0].groupby("pillar").size(); tot = g.sum()
    for p in ["E", "S", "G"]: freq.append(dict(level=lvl, pillar=p, n=int(g.get(p, 0)), share=round(100 * g.get(p, 0) / tot, 1)))
P1f = pd.DataFrame(freq); P1f.to_csv("P1_pillar_frequency.csv", index=False)
print("(1) pillar incorporation + frequency written")

# ============== (2) FORWARD-LOOKING score test ==============
def asof(field):
    return con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,
        ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
        FROM '{SS}' WHERE FIELD_ID='{field}' AND START_DATE>=20150101),
      s AS (SELECT ISSUERID,START_DATE,v FROM l WHERE rn=1 AND v IS NOT NULL),
      g AS (SELECT DISTINCT ISSUERID, UNNEST(range(2017,2026)) y, UNNEST(range(2017,2026))*10000+1231 thr FROM s)
      SELECT g.ISSUERID,g.y yr,arg_max(x.v,x.START_DATE) score FROM g JOIN s x ON g.ISSUERID=x.ISSUERID AND x.START_DATE<=g.thr GROUP BY 1,2""").df()
A["sv"] = ((A["sev"] > 0) | (A["vsev"] > 0)).astype(int)
sevp = A.groupby(["ISSUERID", "yr", "pillar"])["sv"].max().unstack("pillar", fill_value=0).reset_index()
sevp.columns = ["ISSUERID", "yr"] + [f"sev_{c}" for c in sevp.columns[2:]]
rows = []
for p, nm in [("E", "ENVIRONMENTAL"), ("S", "SOCIAL"), ("G", "GOVERNANCE")]:
    d = asof(f"{nm}_PILLAR_SCORE").merge(sevp[["ISSUERID", "yr", f"sev_{p}"]], on=["ISSUERID", "yr"], how="left")
    d[f"sev_{p}"] = d[f"sev_{p}"].fillna(0); d = d.sort_values(["ISSUERID", "yr"])
    d["lead"] = d.groupby("ISSUERID")[f"sev_{p}"].shift(-1); d["ny"] = d.groupby("ISSUERID")["yr"].shift(-1)
    d = d[(d["ny"] - d["yr"]) == 1].dropna(subset=["lead", "score"]); d = d[d["yr"].between(2018, 2024)].copy()
    d["z"] = (d["score"] - d["score"].mean()) / d["score"].std(); yrs = sorted(d["yr"].unique())
    X = np.column_stack([np.ones(len(d)), d["z"].values, d[f"sev_{p}"].values] + [(d["yr"] == y).astype(float).values for y in yrs[1:]])
    r = sm.OLS(d["lead"].values, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ISSUERID"])[0]})
    rows.append(dict(pillar=p, score_coef_per_SD=round(r.params[1], 4), score_t=round(r.tvalues[1], 1),
                     current_controversy_coef=round(r.params[2], 4), current_t=round(r.tvalues[2], 1),
                     base_rate=round(d["lead"].mean(), 4), N=len(d)))
P2 = pd.DataFrame(rows); P2.to_csv("P2_forward_looking_scores.csv", index=False)
print("(2) forward-looking score test written")

# ============== (3) OWNERSHIP WEIGHT ==============
q = pd.read_csv(f"{W}/crsp_ownership/mandate_ownership_quarterly.csv", dtype={"parent_id": str})
rows = []
for col, lab in [("mandate_own", "All ESG-named funds"), ("mandate_own_index", "Index-tracking ESG funds")]:
    v = q[col].dropna()
    rows.append(dict(measure=lab, mean_pct=round(100 * v.mean(), 3), median_pct=round(100 * v.median(), 3),
                     p90_pct=round(100 * v.quantile(.9), 3), n_firm_quarters=len(v)))
P3 = pd.DataFrame(rows); P3.to_csv("P3_ownership_weight.csv", index=False)
print("(3) ownership weight written")

# ============== Excel workbook ==============
with pd.ExcelWriter("Pillar_forward_ownership_results.xlsx") as xw:
    P1f.to_excel(xw, sheet_name="Pillar frequency", index=False)
    P1.to_excel(xw, sheet_name="Pillar incorporation", index=False)
    P2.to_excel(xw, sheet_name="Forward-looking scores", index=False)
    P3.to_excel(xw, sheet_name="Ownership weight", index=False)
print("wrote Pillar_forward_ownership_results.xlsx")
