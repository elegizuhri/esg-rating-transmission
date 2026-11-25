#!/usr/bin/env python3
"""Analysis 3: 12-month letter downgrade on distance-to-threshold bins x controversy severity (LPM, year FE,
ultimate-parent clusters); IAS distribution around the letter cut-offs (bunching check)."""
import duckdb, numpy as np, pandas as pd, statsmodels.api as sm, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
W = "/home/claude/w2"; SS = f"{W}/jul/HIST_SUMMARY_SCORES_20260731.parquet"; BW = 10 / 7
con = duckdb.connect(); con.sql("PRAGMA threads=6")


def asof(field):
    return con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,VALUE s,TRY_CAST(VALUE AS DOUBLE) v,
        ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
        FROM '{SS}' WHERE FIELD_ID='{field}' AND START_DATE>=20150101), r AS (SELECT * FROM l WHERE rn=1 AND s IS NOT NULL),
        y AS (SELECT UNNEST(range(2016,2027)) yr)
        SELECT r.ISSUERID, y.yr, arg_max(v,START_DATE) v, arg_max(s,START_DATE) s FROM r JOIN y ON START_DATE<=yr*10000+1231 GROUP BY 1,2""").df()


ias = asof("INDUSTRY_ADJUSTED_SCORE").rename(columns={"v": "ias"})[["ISSUERID", "yr", "ias"]]
let = asof("IVA_COMPANY_RATING").rename(columns={"s": "letter"})[["ISSUERID", "yr", "letter"]]
B = ias.merge(let, on=["ISSUERID", "yr"], how="inner").dropna()
rk = {"CCC": 1, "B": 2, "BB": 3, "BBB": 4, "A": 5, "AA": 6, "AAA": 7}
B["lr"] = B.letter.map(rk); B = B.dropna(subset=["lr"]).sort_values(["ISSUERID", "yr"])
g = B.groupby("ISSUERID"); B["lrn"] = g.lr.shift(-1); B["yn"] = g.yr.shift(-1)
B["down12"] = np.where(B.yn - B.yr == 1, (B.lrn < B.lr).astype(float), np.nan)
B["dist"] = B.ias - np.floor(B.ias / BW) * BW
# severity of new controversy onsets at t (issue-level onset from zero, July valid-time panel, as in the memo)
A = pd.read_parquet("/home/claude/evt/panelA_vt_july.parquet").rename(columns={"mod": "MOD"}).sort_values(["ISSUERID", "issue", "yr"])
gg = A.groupby(["ISSUERID", "issue"]); cons = A.yr - gg.yr.shift(1) == 1
A["o_v"] = (A.vsev >= 1) & ((gg.vsev.shift(1) < 1) | gg.vsev.shift(1).isna()) & cons
A["o_s"] = (A.sevvsev >= 1) & ((gg.sevvsev.shift(1) < 1) | gg.sevvsev.shift(1).isna()) & cons
A["o_m"] = (A.MOD >= 1) & ((gg.MOD.shift(1) < 1) | gg.MOD.shift(1).isna()) & cons
fo = A.groupby(["ISSUERID", "yr"]).agg(v=("o_v", "max"), s=("o_s", "max"), m=("o_m", "max")).reset_index()
fo["sevcat"] = np.where(fo.v, "very severe", np.where(fo.s, "severe", np.where(fo.m, "moderate", "none")))
D = B.merge(fo[["ISSUERID", "yr", "sevcat"]], on=["ISSUERID", "yr"], how="left"); D["sevcat"] = D.sevcat.fillna("none")
D = D[D.yr.isin([2018, 2019, 2021, 2022, 2023, 2024, 2025])].dropna(subset=["down12"])
nCCC = int((D.letter == "CCC").sum()); D = D[D.letter != "CCC"].copy()          # CCC cannot be downgraded
ref = pd.read_parquet(f"{W}/mref/HIST_MASTER_ISSUER_REFERENCE_20260831.parquet", columns=["ISSUERID", "PARENT_ULTIMATE_ISSUERID"]).drop_duplicates("ISSUERID")
D = D.merge(ref, on="ISSUERID", how="left"); D["grp"] = D.PARENT_ULTIMATE_ISSUERID.fillna(D.ISSUERID)
D["bin"] = pd.cut(D.dist, [-1e-9, 0.3, 0.6, 1.0, BW + 1e-9], labels=["<0.3", "0.3-0.6", "0.6-1.0", "1.0-1.43"])
print("N", len(D), "parents", D.grp.nunique(), "| dropped CCC firm-years:", nCCC)
cells = [(s, b) for s in ["none", "moderate", "severe", "very severe"] for b in ["<0.3", "0.3-0.6", "0.6-1.0", "1.0-1.43"]]
X = pd.DataFrame({f"{s}|{b}": ((D.sevcat == s) & (D["bin"] == b)).astype(float) for s, b in cells if (s, b) != ("none", "1.0-1.43")})
X = pd.concat([X, pd.get_dummies(D.yr.astype(int), prefix="y", drop_first=True).astype(float)], axis=1)
r = sm.OLS(D.down12.values, sm.add_constant(X).values).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(D.grp)[0]})
names = ["const"] + list(X.columns); b = pd.Series(r.params, index=names); t = pd.Series(r.tvalues, index=names)
rows = []
for s, bn in cells:
    k = f"{s}|{bn}"; sub = D[(D.sevcat == s) & (D["bin"] == bn)]
    rows.append(dict(severity=s, bin=bn, N=len(sub), raw_pct=100 * sub.down12.mean() if len(sub) else np.nan,
                     coef_pp=100 * b.get(k, 0.0), t=t.get(k, np.nan)))
T = pd.DataFrame(rows)
# severe minus none, within bin; and near-minus-far difference in that gap
V = r.cov_params(); ix = {n: i for i, n in enumerate(names)}


def lin(w):
    v = np.zeros(len(names))
    for k, c in w.items():
        if k in ix: v[ix[k]] += c
    est = v @ r.params; se = np.sqrt(v @ V @ v); return 100 * est, est / se


tests = {}
for s in ["moderate", "severe", "very severe"]:
    for bn in ["<0.3", "1.0-1.43"]:
        w = {f"{s}|{bn}": 1}; w.update({f"none|{bn}": -1} if bn != "1.0-1.43" else {})
        tests[f"{s} minus none, {bn}"] = lin(w)
    tests[f"{s}: (near gap) minus (far gap)"] = lin({f"{s}|<0.3": 1, "none|<0.3": -1, f"{s}|1.0-1.43": -1})
T.to_csv(f"{W}/out/A3_threshold_lpm.csv", index=False)
pd.DataFrame([(k, v[0], v[1]) for k, v in tests.items()], columns=["test", "pp", "t"]).to_csv(f"{W}/out/A3_tests.csv", index=False)
print(T.round(3).to_string()); print({k: (round(v[0], 2), round(v[1], 2)) for k, v in tests.items()})
print("year FE; N =", int(r.nobs), "; clusters =", D.grp.nunique())

# -------------------------------------------------------------- bunching around cut-offs
cut = [k * BW for k in range(1, 7)]
Y = B[B.yr.isin([2018, 2019, 2021, 2022, 2023, 2024, 2025])]
dec = (np.round(Y.ias * 10) - Y.ias * 10).abs() < 1e-6
print("share of year-end IAS values on the one-decimal grid:", round(dec.mean(), 3))
rec = con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn
     FROM '{SS}' WHERE FIELD_ID='INDUSTRY_ADJUSTED_SCORE' AND START_DATE>=20180101) SELECT v FROM l WHERE rn=1 AND v IS NOT NULL""").df().v
brow = []
fig, ax = plt.subplots(2, 3, figsize=(11, 6), dpi=150, sharey=False)
for i, c in enumerate(cut):
    v = np.round(Y.ias.values, 1)
    grid = np.round(np.arange(np.floor(c * 10) / 10 - 0.2, np.floor(c * 10) / 10 + 0.31, 0.1), 1)
    cnt = [(v == gpt).sum() for gpt in grid]
    for gpt, n in zip(grid, cnt): brow.append(dict(cutoff=round(c, 3), ias=gpt, side="above" if gpt > c else "below", n=n))
    a = ax.flat[i]
    a.bar(grid, cnt, width=0.08, color=["#9aa5b1" if gpt < c else "#2f5d8a" for gpt in grid])
    a.axvline(c, color="black", lw=1, ls="--"); a.set_title(f"Cut-off {c:.3f} ({['CCC/B','B/BB','BB/BBB','BBB/A','A/AA','AA/AAA'][i]})", fontsize=9)
    a.set_xticks(grid); a.tick_params(labelsize=7)
fig.suptitle("Year-end IAS within about ±0.3 of each letter cut-off (rounded to 0.1), firm-years 2018–2025 excl. 2020", fontsize=10)
fig.tight_layout(); fig.savefig(f"{W}/out/A3_bunching.png"); pd.DataFrame(brow).to_csv(f"{W}/out/A3_bunching_counts.csv", index=False)
print(pd.DataFrame(brow).pivot(index="ias", columns="cutoff", values="n").fillna("").to_string())
