#!/usr/bin/env python3
"""Analysis 1: ESG-mandated ownership after controversy-linked vs other downgrades; controversy-date and public-report-date checks."""
import sys
import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, "/home/claude/p2/kit")
import phase2_analysis as P

W = "/home/claude/w2"
KIT = "/home/claude/p2/kit"
OUT = f"{W}/out"; import os; os.makedirs(OUT, exist_ok=True)


def fe(s, p):
    return pd.get_dummies(s.astype(str), prefix=p, drop_first=True).astype(float)


def cl_ols(y, X, g):
    d = pd.concat([y.rename("y"), X, g.rename("g")], axis=1).dropna()
    Xc = sm.add_constant(d[X.columns], has_constant="add")
    Xc = Xc.loc[:, (Xc.std() > 0) | (Xc.columns == "const")]
    r = sm.OLS(d.y, Xc).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.g.astype(str))[0]})
    return r, d


# ------------------------------------------------------------------ ratings, onsets, controls
R = P.Ratings(f"{KIT}/data/ratings.parquet")
par = pd.read_csv(f"{KIT}/data/parents.csv", dtype={"parent_id": str}, low_memory=False).drop_duplicates("parent_id")
ons = pd.read_csv(f"{KIT}/data/onsets.csv", dtype={"parent_id": str}, parse_dates=["msci_date"])
ons = ons[~(ons.flag_backfill_20190701.astype(bool) | ons.flag_floor_20170831.astype(bool))]
sev = ons[ons.severity.isin(["severe", "very_severe"])].copy()
sev["msci_date"] = sev.msci_date.astype("datetime64[ns]")

comp = pd.read_parquet(f"{W}/wrds_extra/compustat_annual.parquet")
comp["datadate"] = pd.to_datetime(comp.datadate).astype("datetime64[ns]"); comp["parent_id"] = comp.parent_id.astype(str)
for c in ["at", "ceq", "lt", "ni", "csho", "prcc_f", "dltt", "dlc"]:
    comp[c] = pd.to_numeric(comp[c], errors="coerce")
comp["log_at"] = np.log(comp["at"].where(comp["at"] > 0))
comp["lev"] = ((comp.dltt.fillna(0) + comp.dlc.fillna(0)) / comp["at"]).where(comp["at"] > 0).clip(0, 2)
comp["roa"] = (comp.ni / comp["at"]).where(comp["at"] > 0).clip(-1, 1)
me = comp.csho * comp.prcc_f
comp["bm"] = np.log((comp.ceq / me).where((comp.ceq > 0) & (me > 0)))
comp = comp.sort_values("datadate"); CTRL = ["log_at", "lev", "roa", "bm"]


def with_ctrl(df, dcol):
    x = df.reset_index().rename(columns={"index": "_i"})
    x["_d"] = (pd.to_datetime(x[dcol]) - pd.DateOffset(months=3)).astype("datetime64[ns]")
    m = pd.merge_asof(x.sort_values("_d"), comp[["parent_id", "datadate"] + CTRL].dropna(subset=["log_at"]),
                      left_on="_d", right_on="datadate", by="parent_id", direction="backward", tolerance=pd.Timedelta(days=550))
    return m.set_index("_i").sort_index()[CTRL]


# ------------------------------------------------------------------ downgrade events and linkage
ch = R.changes.copy(); ch["cdate"] = ch.cdate.astype("datetime64[ns]")
dg = ch[ch.down].copy()
# definition 1: severe/very severe onset logged in the 12 months before the downgrade (inclusive of the downgrade day)
m = dg.merge(sev[["parent_id", "msci_date", "issue", "onset_id"]], on="parent_id", how="left")
m["in12"] = (m.msci_date <= m.cdate) & (m.msci_date > m.cdate - pd.DateOffset(months=12))
link1 = m[m.in12].groupby(["parent_id", "cdate"]).size().rename("n_link").reset_index()
dg = dg.merge(link1, on=["parent_id", "cdate"], how="left"); dg["linked1"] = dg.n_link.notna()

# definition 2: the linked controversy's key-issue score fell between the day before the onset and the downgrade
ISSUE_SCORE = {"TOXIC_EMISS": "TOXIC_EMISS_WSTE_SCORE", "BUS_ETHICS_ETHICSFRAUD": "CORP_BEHAV_ETHICS_SCORE",
               "BUS_ETHICS_ANTICOMP": "CORP_BEHAV_ETHICS_SCORE", "BUS_ETHICS_CORRUPTION": "CORP_BEHAV_ETHICS_SCORE"}
pairs = m[m.in12][["parent_id", "cdate", "msci_date", "issue"]].copy()
pairs["field"] = pairs.issue.map(lambda s: ISSUE_SCORE.get(s, f"{s}_SCORE"))
con = duckdb.connect(); con.sql("PRAGMA threads=6")
ids = pd.DataFrame({"ISSUERID": pairs.parent_id.unique()}); con.register("ids", ids)
flds = pd.DataFrame({"FIELD_ID": pairs.field.unique()}); con.register("flds", flds)
sc = con.sql(f"""WITH l AS (SELECT s.ISSUERID,s.FIELD_ID,s.START_DATE,TRY_CAST(s.VALUE AS DOUBLE) v,
    ROW_NUMBER() OVER(PARTITION BY s.ISSUERID,s.FIELD_ID,s.START_DATE ORDER BY s.VERSION_START_DATE DESC) rn
    FROM '{W}/jul/HIST_SUMMARY_SCORES_20260731.parquet' s JOIN ids USING(ISSUERID) JOIN flds USING(FIELD_ID))
    SELECT ISSUERID parent_id, FIELD_ID field, START_DATE, v FROM l WHERE rn=1 AND v IS NOT NULL""").df()
sc["date"] = pd.to_datetime(sc.START_DATE.astype(str), format="%Y%m%d").astype("datetime64[ns]")
sc = sc.sort_values("date")


def score_at(df, dcol):
    x = df.reset_index().sort_values(dcol)
    x[dcol] = x[dcol].astype("datetime64[ns]")
    r = pd.merge_asof(x, sc[["parent_id", "field", "date", "v"]], left_on=dcol, right_on="date",
                      by=["parent_id", "field"], direction="backward")
    return r.set_index("index").sort_index().v


pairs["pre"] = pairs.msci_date - pd.Timedelta(days=1)
pairs["s_pre"] = score_at(pairs, "pre").values
pairs["s_dg"] = score_at(pairs, "cdate").values
pairs["fell"] = pairs.s_dg < pairs.s_pre - 1e-9
cov2 = pairs.groupby(["parent_id", "cdate"]).agg(any_scored=("s_pre", lambda s: s.notna().any() ), fell=("fell", "any")).reset_index()
dg = dg.merge(cov2, on=["parent_id", "cdate"], how="left")
dg["linked2"] = dg.fell.fillna(False).astype(bool)
print("downgrades (all years):", len(dg), "| linked1:", int(dg.linked1.sum()), "| linked2 (score fell in the linked issue):", int(dg.linked2.sum()),
      "| linked1 with an issue score observed:", int(dg.any_scored.fillna(False).sum()))

# ------------------------------------------------------------------ quarterly ownership panel (US-listed, CRSP MF)
q = pd.read_csv(f"{W}/crsp_ownership/mandate_ownership_quarterly.csv", dtype={"parent_id": str})
lo_, hi_ = q.mandate_own.quantile([0.01, 0.99])
q["all"] = q.mandate_own.clip(lo_, hi_) * 100
q["idx"] = q.mandate_own_index.clip(0, hi_) * 100
q["oth"] = (q.mandate_own - q.mandate_own_index).clip(0, hi_) * 100
q["qp"] = pd.PeriodIndex(q.q, freq="Q"); q["qi"] = q.qp.dt.year * 4 + q.qp.dt.quarter
q = q.sort_values(["parent_id", "qi"]).reset_index(drop=True)
qtr = lambda d: d.dt.year * 4 + d.dt.quarter
dg["qi"] = qtr(dg.cdate)
up = ch[~ch.down].copy(); up["qi"] = qtr(up.cdate)
g = dg.groupby(["parent_id", "qi"]).agg(l1=("linked1", "max"), l2=("linked2", "max")).reset_index().assign(dgq=1.0)
q = q.merge(g, on=["parent_id", "qi"], how="left").merge(up[["parent_id", "qi"]].drop_duplicates().assign(upgrade=1.0), how="left")
q["downgrade"] = q.dgq.fillna(0.0); q["upgrade"] = q.upgrade.fillna(0.0)
q["dg_link1"] = q.downgrade * q.l1.fillna(False).astype(float); q["dg_not1"] = q.downgrade - q.dg_link1
q["dg_link2"] = q.downgrade * q.l2.fillna(False).astype(float); q["dg_not2"] = q.downgrade - q.dg_link2

# controversy logged, no rating change in quarters q..q+4
sev["qi"] = qtr(sev.msci_date)
cq = sev[["parent_id", "qi"]].drop_duplicates()
chq = ch.copy(); chq["qi"] = qtr(chq.cdate); chset = set(zip(chq.parent_id, chq.qi))
cq["nochange"] = [all((p, k + j) not in chset for j in range(0, 5)) for p, k in zip(cq.parent_id, cq.qi)]
q = q.merge(cq[cq.nochange][["parent_id", "qi"]].assign(contro_nochg=1.0), how="left")
q = q.merge(cq[["parent_id", "qi"]].assign(contro_any=1.0), how="left")
q[["contro_nochg", "contro_any"]] = q[["contro_nochg", "contro_any"]].fillna(0.0)

# public-report date (hand-checked clock, verified, excl. 2026-03-23), US firms
H = pd.read_pickle(f"{W}/x3/hand3_m.pkl")
for c in ["MSCI date", "Audited earliest date"]:
    H[c] = pd.to_datetime(H[c], errors="coerce")
H = H[H["Audit status"].astype(str).str.startswith("Verified") & (H["MSCI date"] != "2026-03-23")]
print("verified rows:", len(H), "US:", int((H.Country == "US").sum()))
Hq = H[H.Country == "US"][["Parent ID", "Audited earliest date", "MSCI date"]].rename(columns={"Parent ID": "parent_id"})
Hq["qi"] = qtr(Hq["Audited earliest date"]); Hq["qm"] = qtr(Hq["MSCI date"])
q = q.merge(Hq[["parent_id", "qi"]].drop_duplicates().assign(public=1.0), how="left")
q = q.merge(Hq[["parent_id", "qm"]].drop_duplicates().rename(columns={"qm": "qi"}).assign(msci_hand=1.0), how="left")
q[["public", "msci_hand"]] = q[["public", "msci_hand"]].fillna(0.0)
nochg = lambda p, k: all((p, k + j) not in chset for j in range(0, 5))
q["public_nochg"] = q.public * np.array([nochg(p, k) for p, k in zip(q.parent_id, q.qi)], dtype=float)

q["date"] = q.qp.dt.start_time
q = q.join(with_ctrl(q, "date"))
q = q.set_index(["parent_id", "qi"], drop=False)
rows = []


def run(dep, hz, xs, lab, sample):
    s = q[dep]
    fut = s.reindex(pd.MultiIndex.from_arrays([q.parent_id, q.qi + hz])).values
    prev = s.reindex(pd.MultiIndex.from_arrays([q.parent_id, q.qi - 1])).values
    y = pd.Series(fut - prev, index=q.index)
    keep = sample
    X = pd.concat([q.loc[keep, xs + CTRL], fe(q.loc[keep, "qi"], "t")], axis=1)
    r, d = cl_ols(y[keep], X, q.loc[keep, "parent_id"])
    out = dict(spec=lab, funds=dep, h=hz, N=int(r.nobs), clusters=int(d.g.nunique()), mean_level=float(q.loc[keep, dep].mean()))
    for x in xs:
        out[x] = r.params.get(x, np.nan); out[x + "_t"] = r.tvalues.get(x, np.nan)
        out[x + "_n"] = int(d[x].sum()) if x in d else 0
    if "dg_link1" in xs or "dg_link2" in xs:
        a, b = ("dg_link1", "dg_not1") if "dg_link1" in xs else ("dg_link2", "dg_not2")
        w = r.t_test(f"{a} - {b} = 0"); out["diff"] = float(np.ravel(w.effect)[0]); out["diff_t"] = float(np.ravel(w.tvalue)[0]); out["diff_p"] = float(np.ravel(w.pvalue)[0])
    rows.append(out); return out


S18 = (q.qi >= 2018 * 4 + 1)
for dep in ["all", "idx", "oth"]:
    for hz in (1, 2, 4):
        run(dep, hz, ["dg_link1", "dg_not1", "upgrade"], "Def. 1: severe/very severe logged in prior 12 months", S18)
        run(dep, hz, ["dg_link2", "dg_not2", "upgrade"], "Def. 2: plus that issue's score fell", S18)
        run(dep, hz, ["contro_nochg", "downgrade", "upgrade"], "MSCI logging date, no rating change in q..q+4", S18)
        run(dep, hz, ["public", "msci_hand", "downgrade", "upgrade"], "Hand-checked clock: public-report and MSCI dates (US)", S18)
        run(dep, hz, ["public_nochg", "downgrade", "upgrade"], "Hand-checked clock: public-report date, no rating change in q..q+4", S18)
# replication check of Table 10 (all years, no linkage)
r10 = run("all", 4, ["downgrade", "upgrade"], "CHECK: Table 10 all years", q.qi > 0)
print("Table 10 check q+4:", round(r10["downgrade"], 4), round(r10["downgrade_t"], 2))
T = pd.DataFrame(rows); T.to_csv(f"{OUT}/A1_ownership_linked.csv", index=False)
pd.set_option("display.width", 250)
print(T.round(4).to_string())
