#!/usr/bin/env python3
"""
section8_extra.py -- why is there no price reaction at MSCI rating changes?

  I  Index-review channel. ESG index funds (MSCI KLD 400, ESG Leaders/Select, SRI ...) trade a downgraded stock at the
     next MSCI index review, not on the rating date. Reviews take effect at the close of the last business day of
     February, May, August and November (announced about two weeks earlier).
     I1  CAR around review days for firms downgraded / upgraded since the previous review vs all other firm-reviews
     I2  change in ownership by MSCI-ESG index funds vs other ESG funds after downgrades (who sells, and when)
  V  Trading volume and liquidity around downgrades and controversy logging (needs crsp_daily_liq.parquet from
     wrds_volume.py): abnormal turnover, Amihud illiquidity, quoted spread, days -1..+20 vs the firm's own -60..-11 days.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)


def cl_ols(y, X, g):
    d = pd.concat([y.rename("y"), X, g.rename("g")], axis=1).dropna()
    Xc = sm.add_constant(d[X.columns], has_constant="add")
    Xc = Xc.loc[:, (Xc.std() > 0) | (Xc.columns == "const")]
    return sm.OLS(d.y, Xc).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.g.astype(str))[0]}), d


def coefs(r, terms, model, **kw):
    return [dict(model=model, term=t, coef=r.params[t], se=r.bse[t], t=r.tvalues[t], p=r.pvalues[t], N=int(r.nobs), **kw)
            for t in terms if t in r.params.index]


def fe(s, p):
    return pd.get_dummies(s.astype(str), prefix=p, drop_first=True).astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True); ap.add_argument("--wrds", required=True); ap.add_argument("--daily", required=True)
    ap.add_argument("--liq", default=None, help="crsp_daily_liq.parquet from wrds_volume.py (optional)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    kit, W, out = Path(a.kit), Path(a.wrds), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(kit)); sys.path.insert(0, str(Path(__file__).resolve().parent))
    import phase2_analysis as P
    import es_engine as E
    T = {}
    R = P.Ratings(kit / "data/ratings.parquet")
    ons = pd.read_csv(kit / "data/onsets.csv", dtype={"parent_id": str}, parse_dates=["msci_date"])
    ons = ons[~(ons.flag_backfill_20190701.astype(bool) | ons.flag_floor_20170831.astype(bool))]
    D = E.Daily(pd.read_parquet(a.daily), pd.read_parquet(W / "ff_daily.parquet"), pd.read_parquet(W / "crsp_market_daily.parquet"))
    days = pd.Series(pd.to_datetime(D.days))

    # ------------------------------------------------------------------ I1 review-day CARs
    log("=== I1. CAR around MSCI index review days: firms downgraded/upgraded since the previous review vs others ===")
    rev = days.groupby([days.dt.year, days.dt.month]).max()
    rev = rev[rev.dt.month.isin([2, 5, 8, 11]) & (rev >= "2013-05-01")].sort_values().reset_index(drop=True)
    cut = pd.Series([days[max(0, int(np.searchsorted(days.values, r.to_datetime64())) - 10)] for r in rev])  # ~announcement
    prev_cut = cut.shift(1)
    ch = R.changes[R.changes.parent_id.isin(D.pix)].copy()
    rows = []
    for i in range(1, len(rev)):
        win = ch[(ch.cdate > prev_cut[i]) & (ch.cdate <= cut[i])]
        dn = set(win[win.down].parent_id); up = set(win[~win.down].parent_id)
        lo = ons[(ons.msci_date > prev_cut[i]) & (ons.msci_date <= cut[i])]
        for p in D.pids:
            rows.append((p, rev[i], p in dn, p in up, p in set(lo.parent_id)))
    pr = pd.DataFrame(rows, columns=["parent_id", "review", "downgraded", "upgraded", "controversy"])
    # keep firms that had a rating at the review
    first = R.r.groupby("parent_id").date.min()
    pr = pr[pr.review > pr.parent_id.map(first)].reset_index(drop=True)
    log(f"   {len(rev) - 1} reviews; {len(pr):,} firm-reviews; downgraded {int(pr.downgraded.sum()):,}, upgraded {int(pr.upgraded.sum()):,}")
    WIN = [(-10, -1), (0, 0), (-10, 0), (1, 5), (-10, 5)]
    c = D.car(pr.parent_id.values, pr.review, WIN)
    pr = pd.concat([pr, c], axis=1)
    mo = pd.read_csv(W.parent / "crsp_ownership/mandate_ownership.csv", dtype={"parent_id": str})
    mo["held_by_esg_index_funds"] = (mo.mandate_own_index > 0).astype(float)
    pr["midx"] = pr.review.dt.year * 12 + pr.review.dt.month
    pr = pr.merge(mo[["parent_id", "midx", "held_by_esg_index_funds"]], on=["parent_id", "midx"], how="left")
    pr["held_by_esg_index_funds"] = pr.held_by_esg_index_funds.fillna(0)
    i1 = []
    for g_lab, sel in [("downgraded since last review", pr.downgraded), ("upgraded since last review", pr.upgraded),
                       ("downgraded & held by MSCI-ESG index funds", pr.downgraded & (pr.held_by_esg_index_funds == 1)),
                       ("no rating change", ~pr.downgraded & ~pr.upgraded)]:
        g = pr[sel]
        for w in ["car_-10_-1", "car_0_0", "car_-10_0", "car_1_5", "car_-10_5"]:
            i1.append(dict(group=g_lab, window=w, **E.mean_test(g[w], g.parent_id, g.review.astype(str))))
    T["I1_review_day_CAR_means"] = pd.DataFrame(i1)
    log(T["I1_review_day_CAR_means"][["group", "window", "N", "mean", "t"]].round(4).to_string(index=False))
    pr["dg_x_held"] = pr.downgraded.astype(float) * pr.held_by_esg_index_funds
    pr["up_x_held"] = pr.upgraded.astype(float) * pr.held_by_esg_index_funds
    reg = []
    xs = ["downgraded", "upgraded", "controversy", "held_by_esg_index_funds", "dg_x_held", "up_x_held"]
    for w in ["car_-10_0", "car_1_5", "car_-10_5"]:
        X = pd.concat([pr[xs].astype(float), fe(pr.review.dt.strftime("%Y%m"), "r")], axis=1)
        r, _ = cl_ols(pr[w], X, pr.parent_id)
        reg += coefs(r, xs, f"{w} ~ rating change since last review + review FE")
    T["I1b_review_day_CAR_regression"] = pd.DataFrame(reg)
    log(T["I1b_review_day_CAR_regression"].round(4).to_string(index=False))

    # ------------------------------------------------------------------ I2 who sells: index ESG funds vs other ESG funds
    log("\n=== I2. Ownership change after downgrades: MSCI-ESG index funds vs other ESG funds (quarterly, pp of market cap) ===")
    q = pd.read_csv(W.parent / "crsp_ownership/mandate_ownership_quarterly.csv", dtype={"parent_id": str})
    lo_, hi_ = q.mandate_own.quantile([0.01, 0.99])
    q["idx"] = q.mandate_own_index.clip(0, hi_) * 100
    q["oth"] = (q.mandate_own - q.mandate_own_index).clip(0, hi_) * 100
    q["qp"] = pd.PeriodIndex(q.q, freq="Q"); q["qi"] = q.qp.dt.year * 4 + q.qp.dt.quarter
    chq = R.changes.copy(); chq["qi"] = chq.cdate.dt.year * 4 + chq.cdate.dt.quarter
    q = q.merge(chq[chq.down][["parent_id", "qi"]].drop_duplicates().assign(downgrade=1.0), how="left")
    q = q.merge(chq[~chq.down][["parent_id", "qi"]].drop_duplicates().assign(upgrade=1.0), how="left").fillna({"downgrade": 0.0, "upgrade": 0.0})
    i2 = []
    for col, lab in [("idx", "MSCI-ESG index funds"), ("oth", "other ESG-named funds")]:
        s = q.set_index(["parent_id", "qi"])[col]
        base = s.reindex(pd.MultiIndex.from_arrays([q.parent_id, q.qi - 1])).values
        for h in (0, 1, 2, 4):
            q["dy"] = s.reindex(pd.MultiIndex.from_arrays([q.parent_id, q.qi + h])).values - base
            X = pd.concat([q[["downgrade", "upgrade"]], fe(q.qi, "q")], axis=1)
            r, d = cl_ols(q.dy, X, q.parent_id)
            i2 += coefs(r, ["downgrade", "upgrade"], f"{lab}: change q-1 to q+{h}", mean_level=float(q[col].mean()))
    T["I2_index_vs_other_ESG_funds"] = pd.DataFrame(i2)
    log(T["I2_index_vs_other_ESG_funds"].round(5).to_string(index=False))

    # ------------------------------------------------------------------ V volume / liquidity
    if a.liq and Path(a.liq).exists():
        log("\n=== V. Abnormal trading volume and liquidity around downgrades and controversy logging ===")
        L = pd.read_parquet(a.liq)
        L["date"] = pd.to_datetime(L.date).astype("datetime64[ns]")
        L = L[L.permno.isin(set(pd.read_parquet(a.daily, columns=["permno"]).permno))]
        for c_ in ["vol", "shrout", "prc", "bid", "ask", "ret"]:
            if c_ in L:
                L[c_] = pd.to_numeric(L[c_], errors="coerce")
        L["prc"] = L.prc.abs()
        L["turn"] = L.vol / (L.shrout * 1000.0)                       # shares traded / shares outstanding
        L["amihud"] = (L.ret.abs() / (L.vol * L.prc)).replace([np.inf, -np.inf], np.nan) * 1e6
        L["spread"] = ((L.ask - L.bid) / ((L.ask + L.bid) / 2)).where((L.ask > 0) & (L.bid > 0) & (L.ask >= L.bid))
        # one security per parent (as in the return tests)
        prim = pd.Series({p: None for p in D.pids})
        dd = pd.read_parquet(a.daily, columns=["parent_id", "permno", "mcap_k"])
        prim = dd.groupby(["parent_id", "permno"]).mcap_k.mean().reset_index().sort_values("mcap_k", ascending=False).drop_duplicates("parent_id")
        L = L.merge(prim[["parent_id", "permno"]], on="permno")
        dix = {d: i for i, d in enumerate(D.days)}
        M = {}
        for v in ["turn", "amihud", "spread"]:
            A = np.full(D.R.shape, np.nan)
            ok = L[v].notna() & L.date.isin(dix.keys())
            A[L.loc[ok, "parent_id"].map(D.pix).values, L.loc[ok, "date"].map(dix).values] = np.log(L.loc[ok, v].values + (1e-6 if v == "turn" else 1e-9))
            M[v] = A
        def abn(pids, dates, v, w=(0, 5)):
            t0 = D.day_index(dates); res = np.full(len(pids), np.nan)
            for k, (p, t) in enumerate(zip(pids, t0)):
                i = D.pix.get(p)
                if i is None or t - 60 < 0 or t + w[1] >= M[v].shape[1]:
                    continue
                base = M[v][i, t - 60:t - 10]; ev = M[v][i, t + w[0]:t + w[1] + 1]
                if np.isfinite(base).sum() >= 20 and np.isfinite(ev).sum() >= 1:
                    res[k] = np.nanmean(ev) - np.nanmean(base)
            return res
        vr = []
        chd = R.changes[R.changes.parent_id.isin(D.pix)]
        evs = [("downgrade", chd[chd.down].parent_id.values, chd[chd.down].cdate),
               ("upgrade", chd[~chd.down].parent_id.values, chd[~chd.down].cdate)]
        oo = ons[ons.parent_id.isin(D.pix)]
        for s in ["moderate", "severe", "very_severe"]:
            g = oo[oo.severity == s]; evs.append((f"controversy logged: {s}", g.parent_id.values, g.msci_date))
        evs.append(("index review: downgraded since last review", pr[pr.downgraded].parent_id.values, pr[pr.downgraded].review))
        evs.append(("index review: no rating change", pr[~pr.downgraded & ~pr.upgraded].parent_id.values, pr[~pr.downgraded & ~pr.upgraded].review))
        for lab, pids, dts in evs:
            for v in ["turn", "amihud", "spread"]:
                for w in [(-1, 1), (0, 5), (0, 20)]:
                    x = abn(pids, pd.to_datetime(dts), v, w)
                    vr.append(dict(event=lab, measure=f"log {v}", window=f"[{w[0]},{w[1]}]",
                                   **E.mean_test(x, pids, pd.to_datetime(dts).astype(str).values)))
        T["V1_abnormal_volume_liquidity"] = pd.DataFrame(vr)
        log(T["V1_abnormal_volume_liquidity"][["event", "measure", "window", "N", "mean", "t"]].round(4).to_string(index=False))
    else:
        log("\n(V skipped: run wrds_volume.py and pass --liq crsp_daily_liq.parquet)")

    for k, v in T.items():
        v.to_csv(out / f"{k}.csv", index=False)
    (out / "EXTRA_LOG.txt").write_text("\n".join(LOG), encoding="utf-8")
    pd.to_pickle(T, out / "tables_extra.pkl")


if __name__ == "__main__":
    main()
