#!/usr/bin/env python3
"""
section8_final.py -- final analysis for the research draft (US & UK), using
  * the hand-audit files (670 hand-audit rows; 31 incidents verified with an earliest public date),
  * CRSP daily returns + Fama-French factors (daily event studies),
  * Compustat annual (controls), CRSP Mutual Fund ESG-mandated ownership (eq. 7 / eq. 8),
  * the kit data (MSCI ratings, controversy onsets, monthly market-adjusted returns).

Blocks
  L  logging lag on the hand-audited subsample (with the truncation caveat: rows were kept only with news 0-90 d)
  V  return-based validation of the news dates: CAR at the news date vs a placebo date 364 days earlier
  E  daily event study on MSCI's own dates: controversy logging dates by severity; letter downgrades/upgrades,
     downgrades with vs without a prior MSCI-logged controversy; cross-sectional regression with controls
  O  ESG-mandated ownership: eq. (7) CAR6 x MandateOwn and eq. (8) change in MandateOwn after downgrades
  H  eq. (9) downgrade hazard after controversy logging, with Compustat controls
"""
import argparse
import json
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


def fe(s, prefix):
    return pd.get_dummies(s.astype(str), prefix=prefix, drop_first=True).astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True); ap.add_argument("--wrds", required=True); ap.add_argument("--daily", required=True)
    ap.add_argument("--hand", required=True); ap.add_argument("--contro", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    kit, W, out = Path(a.kit), Path(a.wrds), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(kit)); sys.path.insert(0, str(Path(__file__).resolve().parent))
    import phase2_analysis as P
    import es_engine as E
    T = {}

    # ------------------------------------------------------------------ data
    par = pd.read_csv(kit / "data/parents.csv", dtype={"parent_id": str}, low_memory=False).drop_duplicates("parent_id")
    par["country"] = par.country.replace({"GB": "UK"})
    R = P.Ratings(kit / "data/ratings.parquet")
    ons = pd.read_csv(kit / "data/onsets.csv", dtype={"parent_id": str}, parse_dates=["msci_date"])
    ons = ons[~(ons.flag_backfill_20190701.astype(bool) | ons.flag_floor_20170831.astype(bool))].copy()
    ons["msci_date"] = ons.msci_date.astype("datetime64[ns]")
    ons = ons.merge(par[["parent_id", "country", "sector"]], on="parent_id")
    ons = ons[ons.country.isin(["US", "UK"])]
    ons["sev"] = ons.severity.map(P.SEV_CODE)
    H = pd.read_pickle(a.hand); Cn = pd.read_pickle(a.contro)
    H = H.rename(columns={"Parent ID": "parent_id", "Onset ID": "onset_id", "MSCI date": "msci_date", "News date": "news_date"})
    H["lag"] = (H.msci_date - H.news_date).dt.days
    H["sev"] = H["Severity rank (1–3)"].astype(int)
    V = Cn[Cn["Correct incident?"] == "Y"].copy()
    V = V.rename(columns={"Parent ID": "parent_id", "Onset ID": "onset_id", "MSCI date": "msci_date"})
    V["news_date"] = pd.to_datetime(V["Earliest public date"]); V["msci_date"] = pd.to_datetime(V.msci_date)
    V["lag"] = (V.msci_date - V.news_date).dt.days
    V["sev"] = V.Severity.map(P.SEV_CODE)
    comp = pd.read_parquet(W / "compustat_annual.parquet")
    comp["datadate"] = pd.to_datetime(comp.datadate).astype("datetime64[ns]"); comp["parent_id"] = comp.parent_id.astype(str)
    for c in ["at", "ceq", "lt", "ni", "csho", "prcc_f", "dltt", "dlc"]:
        comp[c] = pd.to_numeric(comp[c], errors="coerce")
    comp["log_at"] = np.log(comp["at"].where(comp["at"] > 0))
    comp["lev"] = ((comp.dltt.fillna(0) + comp.dlc.fillna(0)) / comp["at"]).where(comp["at"] > 0).clip(0, 2)
    comp["roa"] = (comp.ni / comp["at"]).where(comp["at"] > 0).clip(-1, 1)
    me = comp.csho * comp.prcc_f
    comp["bm"] = np.log((comp.ceq / me).where((comp.ceq > 0) & (me > 0)))
    comp = comp.sort_values("datadate")
    CTRL = ["log_at", "lev", "roa", "bm"]

    def with_ctrl(df, dcol):
        """Latest Compustat fiscal year ending at least 3 months before the date."""
        x = df.reset_index().rename(columns={"index": "_i"})
        x["_d"] = (pd.to_datetime(x[dcol]) - pd.DateOffset(months=3)).astype("datetime64[ns]")
        m = pd.merge_asof(x.sort_values("_d"), comp[["parent_id", "datadate"] + CTRL].dropna(subset=["log_at"]),
                          left_on="_d", right_on="datadate", by="parent_id", direction="backward",
                          tolerance=pd.Timedelta(days=550))
        return m.set_index("_i").sort_index().drop(columns=["_d", "datadate"])

    mo = pd.read_csv(W.parent / "crsp_ownership/mandate_ownership.csv", dtype={"parent_id": str})
    lo_, hi_ = mo.mandate_own.quantile([0.01, 0.99])
    mo["mown"] = mo.mandate_own.clip(lo_, hi_) * 100                  # percent of market cap
    log(f"ESG-mandated ownership: {mo.parent_id.nunique():,} firms; median {mo.mown.median():.3f}% of market cap, "
        f"p90 {mo.mown.quantile(.9):.3f}%")

    D = E.Daily(pd.read_parquet(a.daily), pd.read_parquet(W / "ff_daily.parquet"), pd.read_parquet(W / "crsp_market_daily.parquet"))
    log(f"CRSP daily: {len(D.pids):,} firms with a primary US-listed security, {str(D.days[0])[:10]} to {str(D.days[-1])[:10]}")
    WIN = [(-1, 1), (0, 5), (-5, 5), (0, 20)]

    # ================================================================== L: logging lag
    log("\n=== L. Logging lag (MSCI date minus news date), hand-audited subsample ===")

    def lagstats(d, lab):
        return dict(sample=lab, N=len(d), firms=d.parent_id.nunique(), mean=d.lag.mean(), median=d.lag.median(),
                    p25=d.lag.quantile(.25), p75=d.lag.quantile(.75), share_le30=(d.lag <= 30).mean(),
                    share_negative=(d.lag < 0).mean())
    L = [lagstats(V, "Verified incidents (web audit, earliest public date)")]
    for s, g in V.groupby("Severity"):
        L.append(lagstats(g, f"  verified: {s}"))
    L.append(lagstats(H, "Hand-audit file (670; news 0-90 d by construction)"))
    for s, g in H.groupby("Severity"):
        L.append(lagstats(g, f"  670: {s}"))
    for s, g in H.groupby("Period"):
        L.append(lagstats(g, f"  670: {s}"))
    for s, g in H.groupby("Country"):
        L.append(lagstats(g, f"  670: {s}"))
    L.append(lagstats(H[H.Tier == "A"], "670, tier A only (clean onsets)"))
    L.append(lagstats(H[H["Date source"] != "GDELT dated article"], "670, date from a hand-checked/alternative article"))
    T["L1_logging_lag"] = pd.DataFrame(L)
    log(T["L1_logging_lag"].round(2).to_string(index=False))
    rows = []
    for lab, d in [("670 all", H), ("670 tier A", H[H.Tier == "A"]), ("670 excl. 2020", H[H.Period != "2020 (COVID)"])]:
        X = pd.DataFrame({"severe": (d.sev == 2).astype(float), "very_severe": (d.sev == 3).astype(float),
                          "y2020": (d.Period == "2020 (COVID)").astype(float), "early_2018_19": (d.Period == "Early 2018-19").astype(float),
                          "UK": (d.Country == "GB").astype(float)}, index=d.index)
        X = X.loc[:, X.std() > 0]
        r, _ = cl_ols(d.lag.astype(float), X, d.parent_id)
        rows += coefs(r, list(X.columns), f"lag ~ severity + period + UK [{lab}]")
    T["L2_lag_regression"] = pd.DataFrame(rows)
    log(T["L2_lag_regression"].round(3).to_string(index=False))

    # ================================================================== V: return validation of the news dates
    log("\n=== V. Do the news dates carry a stock-price reaction? (US-listed, daily 4-factor CARs) ===")
    vr = []
    for lab, d in [("670 hand-audit file", H), ("670, tier A", H[H.Tier == "A"]),
                   ("670, hand-checked/alternative article", H[H["Date source"] != "GDELT dated article"]),
                   ("Verified incidents", V)]:
        d = d.reset_index(drop=True)
        cn = D.car(d.parent_id.values, d.news_date, WIN)
        cp = D.car(d.parent_id.values, d.news_date - pd.Timedelta(days=364), WIN)
        cm = D.car(d.parent_id.values, d.msci_date, WIN)
        for w in ["car_-1_1", "car_0_5", "car_-5_5"]:
            for kind, c in [("news date", cn), ("placebo (news - 364 d)", cp), ("MSCI date", cm)]:
                vr.append(dict(sample=lab, window=w, date=kind, **E.mean_test(c[w], d.parent_id, d.news_date.astype(str))))
            diff = cn[w] - cp[w]
            vr.append(dict(sample=lab, window=w, date="news minus placebo (paired)", **E.mean_test(diff, d.parent_id, d.news_date.astype(str))))
    T["V1_news_date_validation"] = pd.DataFrame(vr)
    log(T["V1_news_date_validation"][["sample", "window", "date", "N", "mean", "t", "share_neg"]].round(4).to_string(index=False))

    # ================================================================== E: daily event study on MSCI dates
    log("\n=== E1. CAR around MSCI controversy logging dates (all primary US/UK onsets with daily returns) ===")
    o = ons[ons.parent_id.isin(D.pix) & (ons.msci_date >= "2013-02-01")].reset_index(drop=True)
    co = D.car(o.parent_id.values, o.msci_date, WIN)
    o = pd.concat([o, co], axis=1)
    e1 = []
    for s, g in [("all", o)] + list(o.groupby("severity")):
        for w in ["car_-1_1", "car_0_5", "car_-5_5", "car_0_20", "carm_-1_1", "carm_0_5"]:
            e1.append(dict(event="controversy logged by MSCI", severity=s, window=w,
                           **E.mean_test(g[w], g.parent_id, g.msci_date.astype(str))))
    T["E1_CAR_controversy_logging"] = pd.DataFrame(e1)
    log(T["E1_CAR_controversy_logging"][["severity", "window", "N", "mean", "t", "share_neg"]].round(4).to_string(index=False))

    log("\n=== E2. CAR around MSCI letter-rating changes ===")
    ch = R.changes.copy()
    ch = ch[ch.parent_id.isin(D.pix) & (ch.cdate >= "2013-02-01")].reset_index(drop=True)
    # prior MSCI-logged controversy within 365 days before the change (any severity / severe or worse)
    oo = ons[["parent_id", "msci_date", "sev"]].sort_values("msci_date")
    x = ch.reset_index().rename(columns={"index": "_i"}).sort_values("cdate")
    for lab, sub in [("prior_any", oo), ("prior_severe", oo[oo.sev >= 2])]:
        mm = pd.merge_asof(x[["_i", "parent_id", "cdate"]].sort_values("cdate"),
                           sub.rename(columns={"msci_date": "pd_"})[["parent_id", "pd_"]], left_on="cdate", right_on="pd_",
                           by="parent_id", direction="backward", tolerance=pd.Timedelta(days=365))
        ch[lab] = mm.set_index("_i").pd_.reindex(ch.index).notna().astype(float).values
    cc = D.car(ch.parent_id.values, ch.cdate, WIN)
    ch = pd.concat([ch, cc], axis=1)
    e2 = []
    groups = [("downgrade", ch[ch.down]), ("upgrade", ch[~ch.down]),
              ("downgrade, MSCI controversy logged in prior 12 m", ch[ch.down & (ch.prior_any == 1)]),
              ("downgrade, no controversy in prior 12 m", ch[ch.down & (ch.prior_any == 0)]),
              ("downgrade, severe/very severe controversy in prior 12 m", ch[ch.down & (ch.prior_severe == 1)])]
    for lab, g in groups:
        for w in ["car_-1_1", "car_0_5", "car_-5_5", "car_0_20", "carm_-1_1", "carm_0_5"]:
            e2.append(dict(event=lab, window=w, **E.mean_test(g[w], g.parent_id, g.cdate.astype(str))))
    T["E2_CAR_rating_changes"] = pd.DataFrame(e2)
    log(T["E2_CAR_rating_changes"][["event", "window", "N", "mean", "t", "share_neg"]].round(4).to_string(index=False))

    log("\n=== E3. Downgrade CARs: cross-section with controls and ESG-mandated ownership ===")
    dg = ch[ch.down].copy()
    dg = dg.join(with_ctrl(dg, "cdate")[CTRL])
    dg["midx"] = dg.cdate.dt.year * 12 + dg.cdate.dt.month
    dg = dg.merge(mo[["parent_id", "midx", "mown"]], on=["parent_id", "midx"], how="left")
    dg["year"] = dg.cdate.dt.year
    e3 = []
    for y in ["car_-1_1", "car_0_5", "car_0_20"]:
        for lab, xs in [("controls", ["prior_any"] + CTRL), ("controls + ESG ownership", ["prior_any", "mown"] + CTRL)]:
            X = pd.concat([dg[xs], fe(dg.year, "y")], axis=1)
            r, d = cl_ols(dg[y], X, dg.parent_id)
            e3 += coefs(r, xs, f"{y} ~ {lab} + year FE")
    T["E3_downgrade_CAR_regression"] = pd.DataFrame(e3)
    log(T["E3_downgrade_CAR_regression"].round(4).to_string(index=False))

    # ================================================================== O: ESG-mandated ownership
    log("\n=== O1. Eq.(7): 6-month CAR after downgrades x ESG-mandated ownership (monthly, US) ===")
    ret = pd.read_parquet(kit / "data/returns.parquet"); ret["parent_id"] = ret.parent_id.astype(str)
    ret["ra"] = P.winsor(ret.ra)
    ret = ret.sort_values(["parent_id", "midx"])
    g = ret.groupby("parent_id")
    ret["car_f6"] = sum(g.ra.shift(-k) for k in range(1, 7))
    ret["car_f6"] = ret.car_f6.where(g.midx.shift(-6) == ret.midx + 6)
    chm = R.changes.copy(); chm["midx"] = chm.cdate.dt.year * 12 + chm.cdate.dt.month
    Em = ret.merge(mo[["parent_id", "midx", "mown"]], on=["parent_id", "midx"], how="inner")
    Em = Em.merge(chm[chm.down][["parent_id", "midx"]].drop_duplicates().assign(downgrade=1.0), how="left")
    Em = Em.merge(chm[~chm.down][["parent_id", "midx"]].drop_duplicates().assign(upgrade=1.0), how="left")
    om_ = ons[["parent_id", "msci_date"]].assign(o_m=lambda d: d.msci_date.dt.year * 12 + d.msci_date.dt.month)
    pr = om_[["parent_id", "o_m"]].merge(Em[["parent_id", "midx"]].drop_duplicates(), on="parent_id")
    pr = pr[(pr.midx - pr.o_m).between(0, 12)][["parent_id", "midx"]].drop_duplicates().assign(known12=1.0)
    Em = Em.merge(pr, how="left").fillna({"downgrade": 0.0, "upgrade": 0.0, "known12": 0.0})
    Em["date"] = pd.to_datetime(dict(year=Em.midx // 12 - (Em.midx % 12 == 0), month=(Em.midx - 1) % 12 + 1, day=1))
    Em = Em.join(with_ctrl(Em, "date")[CTRL])
    Em["mown_z"] = (Em.mown - Em.mown.mean()) / Em.mown.std()
    Em["dg_x_mown"] = Em.downgrade * Em.mown_z
    Em["dg_x_known"] = Em.downgrade * Em.known12
    o1 = []
    for lab, xs in [("base", ["downgrade", "upgrade", "mown_z", "dg_x_mown", "known12", "dg_x_known"]),
                    ("with controls", ["downgrade", "upgrade", "mown_z", "dg_x_mown", "known12", "dg_x_known"] + CTRL)]:
        X = pd.concat([Em[xs], fe(Em.midx, "t")], axis=1)
        r, d = cl_ols(Em.car_f6, X, Em.parent_id)
        o1 += coefs(r, xs, f"CAR6 ~ eq.(7) [{lab}] + month FE")
    T["O1_eq7_CAR6_mandate_ownership"] = pd.DataFrame(o1)
    log(T["O1_eq7_CAR6_mandate_ownership"].round(4).to_string(index=False))

    log("\n=== O2. Eq.(8): change in ESG-mandated ownership after downgrades (quarterly, US) ===")
    q = pd.read_csv(W.parent / "crsp_ownership/mandate_ownership_quarterly.csv", dtype={"parent_id": str})
    q["mown"] = q.mandate_own.clip(lo_, hi_) * 100
    q["qp"] = pd.PeriodIndex(q.q, freq="Q"); q = q.sort_values(["parent_id", "qp"])
    q["qi"] = q.qp.dt.year * 4 + q.qp.dt.quarter
    chq = R.changes.copy(); chq["qi"] = chq.cdate.dt.year * 4 + chq.cdate.dt.quarter
    q = q.merge(chq[chq.down][["parent_id", "qi"]].drop_duplicates().assign(downgrade=1.0), how="left")
    q = q.merge(chq[~chq.down][["parent_id", "qi"]].drop_duplicates().assign(upgrade=1.0), how="left")
    q = q.fillna({"downgrade": 0.0, "upgrade": 0.0})
    qq = q.set_index(["parent_id", "qi"]).mown
    q["date"] = q.qp.dt.start_time
    q = q.join(with_ctrl(q, "date")[CTRL])
    o2 = []
    for h in (2, 4, 8):
        fut = qq.reindex(pd.MultiIndex.from_arrays([q.parent_id, q.qi + h])).values
        prev = qq.reindex(pd.MultiIndex.from_arrays([q.parent_id, q.qi - 1])).values
        q[f"d_mown_{h}"] = fut - prev
        for lab, xs in [("base", ["downgrade", "upgrade"]), ("with controls", ["downgrade", "upgrade"] + CTRL)]:
            X = pd.concat([q[xs], fe(q.qi, "q")], axis=1)
            r, d = cl_ols(q[f"d_mown_{h}"], X, q.parent_id)
            o2 += coefs(r, xs, f"change in ESG ownership (pp) from q-1 to q+{h} ~ [{lab}] + quarter FE",
                        mean_dep=float(d.y.mean()), mean_level=float(q.mown.mean()))
    T["O2_eq8_change_in_mandate_ownership"] = pd.DataFrame(o2)
    log(T["O2_eq8_change_in_mandate_ownership"].round(4).to_string(index=False))
    # event-time path of ownership around downgrades (relative to quarter -1)
    path = []
    ev = q[q.downgrade == 1][["parent_id", "qi"]]
    for k in range(-4, 9):
        v = qq.reindex(pd.MultiIndex.from_arrays([ev.parent_id, ev.qi + k])).values
        b = qq.reindex(pd.MultiIndex.from_arrays([ev.parent_id, ev.qi - 1])).values
        dlt = v - b
        path.append(dict(quarter_rel_to_downgrade=k, N=int(np.isfinite(dlt).sum()), mean_change_pp=np.nanmean(dlt),
                         median_change_pp=np.nanmedian(dlt)))
    T["O3_ownership_path_around_downgrades"] = pd.DataFrame(path)
    log(T["O3_ownership_path_around_downgrades"].round(4).to_string(index=False))

    # ================================================================== H: hazard with controls
    log("\n=== H. Eq.(9) hazard of a downgrade after MSCI logging, with Compustat controls ===")
    m = ons.reset_index(drop=True).copy()
    m["spell_id"] = m.onset_id
    m = m.join(R.asof(m, "msci_date")).dropna(subset=["band"])
    m = m.join(with_ctrl(m, "msci_date")[CTRL])
    m["cal_month"] = m.msci_date.dt.month
    m["severe"] = (m.sev == 2).astype(float); m["very_severe"] = (m.sev == 3).astype(float)
    m["us"] = m.country == "US"
    hz = []
    for kind in ["down", "any"]:
        sp, one = P.build_spells(m, "msci_date", R, kind)
        for s_lab, s_df in [("US+UK", sp), ("US", sp[sp.us])]:
            for c_lab, xc in [("no controls, same sample", ["severe", "very_severe", "dist_threshold"]),
                              ("Compustat controls", ["severe", "very_severe", "dist_threshold", "log_at", "lev", "roa"])]:
                s2 = s_df.dropna(subset=["log_at", "lev", "roa"])
                res, rows = P.fit_hazard(s2, xc, ["sector", "cal_month"], "parent_id", f"{kind}|{s_lab}|{c_lab}")
                hz += [dict(r, event=kind, sample=s_lab, spec=c_lab) for r in rows
                       if r["term"] in ["severe", "very_severe", "dist_threshold", "log_at", "lev", "roa"]]
    T["H1_hazard_with_controls"] = pd.DataFrame(hz)
    log(T["H1_hazard_with_controls"].round(3).to_string(index=False))

    for k, v in T.items():
        v.to_csv(out / f"{k}.csv", index=False)
    (out / "FINAL_LOG.txt").write_text("\n".join(LOG), encoding="utf-8")
    pd.to_pickle(T, out / "tables.pkl")
    log(f"\nDONE -> {out}")


if __name__ == "__main__":
    main()
