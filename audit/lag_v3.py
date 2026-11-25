#!/usr/bin/env python3
"""Re-run of the external-clock (logging lag) tests on the 27-Oct-2026 hand audit (727 rows; audited earliest dates)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, "/home/claude/p2/kit"); sys.path.insert(0, "/home/claude/p8")
import es_engine as E
import phase2_analysis as P

X = Path(sys.argv[1]); F = Path(sys.argv[2]); OUT = Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)


H = pd.read_pickle(X / "hand3_m.pkl")
for c in ["MSCI date", "News date", "Audited earliest date"]:
    H[c] = pd.to_datetime(H[c], errors="coerce")
H["ver"] = H["Audit status"].astype(str).str.startswith("Verified")
H["screen_ok"] = H["Audit verdict"].isin(["Correct (headline screen)", "Correct (headline only)"])
H["v5"] = H["MSCI date"] == "2026-03-23"
H["year"] = H["MSCI date"].dt.year
H["period"] = np.select([H.year <= 2019, H.year == 2020, H.year <= 2025], ["2018-19", "2020", "2021-25"], "2026")
H["sev"] = H["Severity rank (1–3)"].astype(int)
H["severe"] = (H.sev == 2).astype(int); H["vsev"] = (H.sev == 3).astype(int)
H["uk"] = (H.Country == "GB").astype(int)
H["y2020"] = (H.period == "2020").astype(int); H["early"] = (H.period == "2018-19").astype(int); H["y2026"] = (H.period == "2026").astype(int)
H["pid"] = H["Parent ID"]
H["ext"] = np.where(H.ver, H["Audited earliest date"], np.where(H.screen_ok, H["News date"], pd.NaT))
H["ext"] = pd.to_datetime(H.ext)
H["lag"] = (H["MSCI date"] - H.ext).dt.days

S = {"A. Verified (audited earliest date), excl. v5.0 re-rating day": H[H.ver & ~H.v5],
     "B. Verified, excl. all 2026": H[H.ver & (H.year < 2026)],
     "C. Verified incl. v5.0 re-rating day": H[H.ver],
     "D. Verified + headline-screen rows (GDELT date), excl. v5.0": H[(H.ver | H.screen_ok) & ~H.v5]}
PRIM = "A. Verified (audited earliest date), excl. v5.0 re-rating day"

# ---------------------------------------------------------------- L1 descriptive
def st(d, lab):
    return dict(sample=lab, N=len(d), events=d["Event ID"].nunique(), firms=d.pid.nunique(), mean=d.lag.mean(),
                median=d.lag.median(), p25=d.lag.quantile(.25), p75=d.lag.quantile(.75),
                le30=(d.lag <= 30).mean(), le90=(d.lag <= 90).mean(), le180=(d.lag <= 180).mean(),
                gt365=(d.lag > 365).mean())
rows = []
for k, d in S.items():
    rows.append(st(d, k))
A = S[PRIM]
for g, d in A.groupby("Severity"):
    rows.append(st(d, f"   A: {g}"))
for g, d in A.groupby("period"):
    rows.append(st(d, f"   A: {g}"))
for g, d in A.groupby("Country"):
    rows.append(st(d, f"   A: {g}"))
for g, d in A.groupby("Audit verdict"):
    rows.append(st(d, f"   A: verdict = {g}"))
ev = A.sort_values("sev", ascending=False).drop_duplicates("Event ID")
rows.append(st(ev, "A, one row per incident (Event ID)"))
L1 = pd.DataFrame(rows); L1.to_csv(OUT / "L1v3_lag_descriptive.csv", index=False)
log("=== L1 audited logging lag ===\n" + L1.round(2).to_string(index=False))

# ---------------------------------------------------------------- L2 regressions
rr = []
def fit(f, d, lab, quant=False):
    if quant:
        r = smf.quantreg(f, d).fit(q=0.5)
    else:
        r = smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.pid)[0]})
    for t in ["severe", "vsev", "y2020", "early", "y2026", "uk"]:
        if t in r.params:
            rr.append(dict(sample=lab.split(",")[0], model=lab, term=t, coef=r.params[t], t=r.tvalues[t], p=r.pvalues[t], N=int(r.nobs)))
base = "severe + vsev + y2020 + early + uk"
for k in [PRIM, "B. Verified, excl. all 2026", "D. Verified + headline-screen rows (GDELT date), excl. v5.0"]:
    d = S[k].copy(); d["loglag"] = np.log1p(d.lag.clip(lower=0))
    b = base + (" + y2026" if d.y2026.sum() > 0 else "")
    fit(f"lag ~ {b}", d, f"{k[:2]} days, OLS")
    fit(f"lag ~ {b} + C(Issue)", d, f"{k[:2]} days, OLS + issue FE")
    fit(f"loglag ~ {b} + C(Issue)", d, f"{k[:2]} log(1+lag) + issue FE")
    fit(f"lag ~ {b} + C(Issue)", d, f"{k[:2]} median regression + issue FE", quant=True)
L2 = pd.DataFrame(rr); L2.to_csv(OUT / "L2v3_lag_regressions.csv", index=False)
log("\n=== L2 regressions ===\n" + L2.round(3).to_string(index=False))

# selection: which rows were verified?
H["one"] = 1
H["veri"] = H.ver.astype(int)
r = smf.ols("veri ~ severe + vsev + y2020 + early + y2026 + uk", H).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(H.pid)[0]})
SEL = pd.DataFrame({"term": r.params.index, "coef": r.params.values, "t": r.tvalues.values})
SEL.to_csv(OUT / "L3v3_selection_into_verified.csv", index=False)
log("\n=== L3 probability that a row has a verified date (linear probability) ===\n" + SEL.round(3).to_string(index=False))
dist = pd.cut(A.lag, [-10000, -1, 30, 90, 180, 365, 100000], labels=["<0", "0-30", "31-90", "91-180", "181-365", ">365"]).value_counts().sort_index()
dist = pd.DataFrame({"lag_bin": dist.index.astype(str), "N": dist.values, "share": dist.values / dist.sum()})
dist.to_csv(OUT / "L4v3_lag_distribution.csv", index=False)
log("\n" + dist.round(3).to_string(index=False))

# ---------------------------------------------------------------- K external vs internal clock to rating change
R = P.Ratings("/home/claude/p2/kit/data/ratings.parquet")
par = pd.read_csv("/home/claude/p2/kit/data/parents.csv", dtype={"parent_id": str}, low_memory=False).drop_duplicates("parent_id")
k = A.rename(columns={"pid": "parent_id", "Onset ID": "onset_id", "MSCI date": "msci_date"}).copy()
k = k.merge(par[["parent_id", "sector"]], on="parent_id", how="left").reset_index(drop=True)
k["spell_id"] = k.onset_id + "_" + k.index.astype(str)
krows, hz = [], []
for clock, dcol in [("external (audited news date)", "ext"), ("internal (MSCI date)", "msci_date")]:
    b = k.join(R.asof(k, dcol)).dropna(subset=["band"])
    b["cal_month"] = b[dcol].dt.month
    for kind in ["any", "down"]:
        sp, one = P.build_spells(b, dcol, R, kind)
        med, p12, p24 = P.km_median(one)
        krows.append(dict(clock=clock, event="letter change" if kind == "any" else "downgrade", spells=len(one),
                          events=int(one.event.sum()), KM_median_months=med, P12=p12, P24=p24))
        res, rws = P.fit_hazard(sp, ["severe", "vsev", "dist_threshold"], [], "parent_id", f"{clock}|{kind}")
        hz += [dict(r_, clock=clock, event=kind) for r_ in rws if r_["term"] in ["severe", "vsev", "dist_threshold"]]
K = pd.DataFrame(krows); K.to_csv(OUT / "K1v3_KM_external_vs_internal.csv", index=False)
HZ = pd.DataFrame(hz); HZ.to_csv(OUT / "K2v3_hazard_external_vs_internal.csv", index=False)
log("\n=== K1 months from news (external) vs from MSCI logging (internal) to the rating change ===\n" + K.round(3).to_string(index=False))
log("\n=== K2 hazard (cloglog, month bins), severity effects ===\n" + HZ.round(3).to_string(index=False))

# ---------------------------------------------------------------- V returns at audited dates
D = E.Daily(pd.read_parquet(F / "daily/wrds_extra/crsp_daily.parquet"), pd.read_parquet(F / "main/wrds_extra/ff_daily.parquet"),
            pd.read_parquet(F / "main/wrds_extra/crsp_market_daily.parquet"))
d = A.drop_duplicates(["pid", "ext"]).reset_index(drop=True)
WIN = [(-30, -2), (-1, 1), (0, 5), (-5, 20)]
cn = D.car(d.pid.values, d.ext, WIN, est=(-310, -90))
cp = D.car(d.pid.values, d.ext - pd.Timedelta(days=364), WIN, est=(-310, -90))
cm = D.car(d.pid.values, d["MSCI date"], WIN, est=(-310, -90))
vr = []
for w in ["car_-30_-2", "car_-1_1", "car_0_5", "car_-5_20"]:
    for kind, c in [("audited news date", cn), ("placebo (news - 364 d)", cp), ("MSCI date", cm)]:
        vr.append(dict(window=w, date=kind, **E.mean_test(c[w], d.pid, d.ext.astype(str))))
    vr.append(dict(window=w, date="news minus placebo", **E.mean_test(cn[w] - cp[w], d.pid, d.ext.astype(str))))
V = pd.DataFrame(vr); V.to_csv(OUT / "V1v3_returns_at_audited_dates.csv", index=False)
log("\n=== V returns at audited news dates (US-listed; one row per firm-date) ===\n" + V[["window", "date", "N", "mean", "t"]].round(4).to_string(index=False))
(OUT / "LOG_v3.txt").write_text("\n".join(LOG), encoding="utf-8")
