#!/usr/bin/env python3
"""Analysis 5 (robustness): methodology-implied change in WAKIS from MSCI's controversy-deduction schedule vs observed ΔWAKIS."""
import duckdb, numpy as np, pandas as pd
W = "/home/claude/w2"; SS = f"{W}/jul/HIST_SUMMARY_SCORES_20260731.parquet"; CF = f"{W}/jul/HIST_CONTROVERSIES_20260731.parquet"
# midpoints of the non-structural/structural deduction range, by highest severity in the key issue
DED = {0: 0.0, 1: (0.8 + 1.3) / 2, 2: (1.7 + 2.5) / 2, 3: (3.0 + 5.0) / 2}
WMAP = {"TOXIC_EMISS": "TOXIC_EMISS_WSTE_WEIGHT"}
GOV = {"BUS_ETHICS_ETHICSFRAUD", "BUS_ETHICS_ANTICOMP", "BUS_ETHICS_CORRUPTION"}      # governance: deduction works through Key Metrics
A = pd.read_parquet("/home/claude/evt/panelA_vt_july.parquet").rename(columns={"mod": "MOD"})
A = A[~A.issue.isin(GOV)].copy()
A["h"] = np.select([A.vsev > 0, A.sev > 0, A.MOD > 0], [3, 2, 1], 0)
A = A.sort_values(["ISSUERID", "issue", "yr"]); g = A.groupby(["ISSUERID", "issue"])
A["h_prev"] = np.where(A.yr - g.yr.shift(1) == 1, g.h.shift(1), 0)          # issue not covered in t-1: treated as 0
A["dded"] = A.h.map(DED) - pd.Series(A.h_prev).map(DED).values
A["wfield"] = A.issue.map(lambda s: WMAP.get(s, f"{s}_WEIGHT"))
con = duckdb.connect(); con.sql("PRAGMA threads=6")
fl = pd.DataFrame({"FIELD_ID": A.wfield.unique()}); con.register("fl", fl)
w = con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
   FROM '{SS}' JOIN fl USING(FIELD_ID) WHERE START_DATE>=20150101), r AS (SELECT * FROM l WHERE rn=1 AND v IS NOT NULL), y AS (SELECT UNNEST(range(2016,2027)) yr)
   SELECT r.ISSUERID, r.FIELD_ID wfield, y.yr, arg_max(v,START_DATE) wt FROM r JOIN y ON START_DATE<=yr*10000+1231 GROUP BY 1,2,3""").df()
print("weight scale (median, p99):", w.wt.median(), w.wt.quantile(.99))
A = A.merge(w, on=["ISSUERID", "wfield", "yr"], how="left")
A["covered_w"] = A.wt.notna()
A["contrib"] = -(A.wt.fillna(0) / 100.0) * A.dded                   # weights are in percent
imp = A.groupby(["ISSUERID", "yr"]).agg(implied=("contrib", "sum"), n_chg=("dded", lambda s: int((s != 0).sum())),
                                         n_chg_w=("contrib", lambda s: int((s != 0).sum()))).reset_index()
P = pd.read_parquet(f"{W}/panel_fy_validtime.parquet")
fs = con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 fs FROM '{CF}' WHERE regexp_matches(FIELD_ID,'_(MODERATE|SEVERE|VERY_SEVERE)_CONTROVERSIES$') GROUP BY 1").df()
ft = con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 ft FROM '{CF}' WHERE FIELD_ID='TOTAL_NUMBER_CONTROVERSIES' GROUP BY 1").df()
bf = pd.read_csv(f"{W}/out/A2_bf_flags.csv") if False else None
P = P.merge(fs, on="ISSUERID", how="left").merge(ft, on="ISSUERID", how="left").merge(imp, on=["ISSUERID", "yr"], how="left")
P["implied"] = P.implied.fillna(0.0); P["n_chg"] = P.n_chg.fillna(0); P["n_chg_w"] = P.n_chg_w.fillna(0)
F = P[P.yr.isin([2018, 2019, 2021, 2022, 2023, 2024, 2025])].dropna(subset=["dias", "d_c_sev", "dwas"]).copy()
F = F[~((F.fs == F.yr) | (F.ft == F.yr)) & (F.yr != 2019) | ((F.yr == 2019) & ~((F.fs == F.yr) | (F.ft == F.yr)))]


def cl(d, y, x, c="group"):
    d = d.dropna(subset=[y, x]).copy(); d["yr"] = d.yr.astype(int); yrs = sorted(d.yr.unique())
    X = np.column_stack([np.ones(len(d))] + [(d.yr == yy).astype(float) for yy in yrs[1:]] + [d[x].values]); Y = d[y].values
    XtXi = np.linalg.inv(X.T @ X); b = XtXi @ (X.T @ Y); e = Y - X @ b
    S = pd.DataFrame(X * e[:, None]).groupby(d[c].values).sum().values; N, k = X.shape; G = S.shape[0]
    se = np.sqrt(np.diag((G / (G - 1)) * ((N - 1) / (N - k)) * (XtXi @ (S.T @ S) @ XtXi)))
    return b[-1], b[-1] / se[-1], N, G


rows = []
for lab, D in [("All firm-years (implied = 0 where no change)", F),
               ("Firm-years with a weighted key-issue severity change", F[F.n_chg_w > 0]),
               ("  of which: severity rises only (onsets)", F[(F.n_chg_w > 0) & (F.implied < 0)]),
               ("  of which: a single changed key issue", F[F.n_chg_w == 1])]:
    b, t, n, gg = cl(D, "dwas", "implied")
    b2, t2, _, _ = cl(D, "dias", "implied")
    rows.append(dict(sample=lab, slope_dWAKIS=b, t_dWAKIS=t, slope_dIAS=b2, t_dIAS=t2, N=n, clusters=gg,
                     mean_implied=D.implied.mean(), mean_dWAKIS=D.dwas.mean()))
T = pd.DataFrame(rows); T.to_csv(f"{W}/out/A5_implied.csv", index=False)
pd.set_option("display.width", 220); print(T.round(4).to_string())
print("share of changed issue-years with no weight in force:", round(1 - A[A.dded != 0].covered_w.mean(), 3))
