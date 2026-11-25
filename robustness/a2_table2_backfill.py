#!/usr/bin/env python3
"""Analysis 2: Table 2 (contemporaneous and t+1) without firm-years whose severity change comes from onsets dated
2019-07-01 (backfill) or 2017-08-31 (floor); overlap with the first-covered-year flag. Paper sample, parent clusters."""
import duckdb, numpy as np, pandas as pd
W = "/home/claude/w2"; CF = f"{W}/jul/HIST_CONTROVERSIES_20260731.parquet"
P = pd.read_parquet(f"{W}/panel_fy_validtime.parquet")
con = duckdb.connect()
sevre = "regexp_matches(FIELD_ID,'_(MODERATE|SEVERE|VERY_SEVERE)_CONTROVERSIES$')"
fs = con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 fs FROM '{CF}' WHERE {sevre} GROUP BY 1").df()
ft = con.sql(f"SELECT ISSUERID, MIN(START_DATE)//10000 ft FROM '{CF}' WHERE FIELD_ID='TOTAL_NUMBER_CONTROVERSIES' GROUP BY 1").df()
# issuer-years with a positive severity record starting on a backfill/floor date (latest version per record)
bf = con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,
    ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE {sevre})
    SELECT ISSUERID, START_DATE//10000 yr, START_DATE d, COUNT(*) n FROM l WHERE rn=1 AND v>0 AND START_DATE IN (20190701,20170831) GROUP BY 1,2,3""").df()
print("issuers with a positive severity record on 2019-07-01:", bf[bf.d == 20190701].ISSUERID.nunique(),
      "| on 2017-08-31:", bf[bf.d == 20170831].ISSUERID.nunique())
P = P.merge(fs, on="ISSUERID", how="left").merge(ft, on="ISSUERID", how="left")
P = P.merge(bf.groupby(["ISSUERID", "yr"]).size().rename("bfn").reset_index(), on=["ISSUERID", "yr"], how="left")
P["first"] = (P.fs == P.yr) | (P.ft == P.yr)
P["backfill"] = P.bfn.notna()
Wy = [2018, 2019, 2021, 2022, 2023, 2024, 2025]
F = P[P.yr.isin(Wy)].dropna(subset=["dias", "d_c_sev"]).copy()
# a flagged firm-year counts only if its severity counts actually change in that year
F["sevchg"] = (F.d_c_mod != 0) | (F.d_c_sev != 0) | (F.d_c_vs != 0)
F["bf_any"] = F.backfill
F["bf_chg"] = F.backfill & F.sevchg
ov = dict(canonical=len(F), backfill_any=int(F.bf_any.sum()), backfill_with_change=int(F.bf_chg.sum()),
          first_covered=int(F["first"].sum()), both=int((F.bf_any & F["first"]).sum()),
          backfill_not_first=int((F.bf_any & ~F["first"]).sum()), first_not_backfill=int((F["first"] & ~F.bf_any).sum()),
          union=int((F.bf_any | F["first"]).sum()))
ov["backfill_by_year"] = F[F.bf_any].groupby("yr").size().to_dict()
print(ov)


def cl(d, y, x, c="group"):
    d = d.dropna(subset=[y, x]).copy(); d["yr"] = d.yr.astype(int); yrs = sorted(d.yr.unique())
    X = np.column_stack([np.ones(len(d))] + [(d.yr == yy).astype(float) for yy in yrs[1:]] + [d[x].values]); Y = d[y].values
    XtXi = np.linalg.inv(X.T @ X); b = XtXi @ (X.T @ Y); e = Y - X @ b
    S = pd.DataFrame(X * e[:, None]).groupby(d[c].values).sum().values; N, k = X.shape; G = S.shape[0]
    se = np.sqrt(np.diag((G / (G - 1)) * ((N - 1) / (N - k)) * (XtXi @ (S.T @ S) @ XtXi)))
    return b[-1], b[-1] / se[-1], N, G


rows = []
samples = {"Table 2 (all)": F, "Excl. backfill/floor onsets": F[~F.bf_any], "Excl. first covered year": F[~F["first"]],
           "Excl. both": F[~(F.bf_any | F["first"])]}
for lab, D in samples.items():
    for c, nm in [("c_minor", "Other (residual)"), ("c_mod", "Moderate"), ("c_sev", "Severe"), ("c_vs", "Very severe")]:
        b0, t0, n0, g0 = cl(D, "dias", "d_" + c); b1, t1, n1, g1 = cl(D, "dias_t1", "d_" + c)
        rows.append(dict(sample=lab, level=nm, b_t=b0, t_t=t0, N_t=n0, G_t=g0, b_t1=b1, t_t1=t1, N_t1=n1, G_t1=g1))
T = pd.DataFrame(rows); T.to_csv(f"{W}/out/A2_table2_backfill.csv", index=False)
pd.Series(ov).to_csv(f"{W}/out/A2_overlap.csv")
pd.set_option("display.width", 250); print(T.round(4).to_string())
