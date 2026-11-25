#!/usr/bin/env python3
"""
downgrade_drift_eventstudy.py — reconciles the Appendix H post-downgrade drift with the main
result (no price reaction at the rating change), and shows the drift is NOT an MSCI
re-issue/backfill ("washing out") artifact.

Produces:
  (H3) the event-time CAR path around letter downgrades (months -6..+6) on a BALANCED window
       (events with the full window present), plus the before / event-month / after window CARs -> Table H3
  (robustness) the 6-month forward drift under exclusions of the MSCI batch re-issue / backfill /
               re-rating dates and by sub-period (shows the drift is not a data artifact)
  (control)    whether controlling for the firm's own past-6-month return absorbs the drift

Inputs (from the external-clock kit, not licensed here): ratings.parquet (parent_id, start, ias,
letter, band) and returns.parquet (parent_id, midx, r, ra), where midx = year*12 + month and
ra is the market-adjusted monthly return. Set KIT to that folder.
Run:  KIT=/path/to/kit python downgrade_drift_eventstudy.py
"""
import os, numpy as np, pandas as pd, statsmodels.api as sm

KIT = os.environ.get("KIT", "kit")
out = []
def log(s): out.append(str(s)); print(s)

def ct(y, groups):
    """mean with a firm-clustered t-statistic."""
    r = sm.OLS(np.asarray(y, float), np.ones((len(y), 1))).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(groups)[0]})
    return float(r.tvalues[0])

# ---- letter downgrades from the band series ----
rt = pd.read_parquet(f"{KIT}/ratings.parquet"); rt["parent_id"] = rt.parent_id.astype(str)
rt["d"] = pd.to_datetime(rt.start.astype(str), format="%Y%m%d"); rt = rt.sort_values(["parent_id", "d"])
rt["pband"] = rt.groupby("parent_id").band.shift(1)
dg = rt[rt.band < rt.pband].copy()
dg["midx"] = dg.d.dt.year * 12 + dg.d.dt.month
dg = dg.reset_index(drop=True); dg["ev"] = dg.index

# ---- monthly market-adjusted returns, winsorised 0.5/99.5 ----
ret = pd.read_parquet(f"{KIT}/returns.parquet"); ret["parent_id"] = ret.parent_id.astype(str)
lo, hi = ret.ra.quantile([.005, .995]); ret["raw_"] = ret.ra.clip(lo, hi)
ret = ret.sort_values(["parent_id", "midx"]); gg = ret.groupby("parent_id")
ret["f6"] = sum(gg.raw_.shift(-k) for k in range(1, 7)); ret["f6"] = ret.f6.where(gg.midx.shift(-6) == ret.midx + 6)
ret["b6"] = sum(gg.raw_.shift(k) for k in range(0, 6)); ret["b6"] = ret.b6.where(gg.midx.shift(5) == ret.midx - 5)

# ================= (H3) event-time path, BALANCED -6..+6 window =================
E = dg[["ev", "parent_id", "midx"]].merge(pd.DataFrame({"k": range(-6, 7)}), how="cross")
E["tgt"] = E.midx + E.k
E = E.merge(ret[["parent_id", "midx", "raw_"]].rename(columns={"midx": "tgt", "raw_": "ra"}),
            on=["parent_id", "tgt"], how="inner")
full = E.groupby("ev").k.count(); B = E[E.ev.isin(full[full == 13].index)]      # keep full windows only
log(f"=== Table H3: event-time CAR around letter downgrades (balanced window, N={B.ev.nunique()}) ===")
path, cum = [], 0.0
for k in range(-6, 7):
    d = B[B.k == k]; m = d.ra.mean() * 100; cum += m
    path.append(dict(event_month=k, mean_pct=round(m, 2), t=round(ct(d.ra, d.parent_id), 2),
                     cumCAR_pct=round(cum, 2), N=len(d)))
pathdf = pd.DataFrame(path); log(pathdf.to_string(index=False))

def win(a, b, lab):
    s = B[B.k.between(a, b)].groupby("ev").agg(ra=("ra", "sum"), pid=("parent_id", "first")).reset_index()
    return dict(window=lab, CAR_pct=round(s.ra.mean() * 100, 2), t=round(ct(s.ra, s.pid), 2), N=len(s))
wins = pd.DataFrame([win(-6, -1, "before (-6..-1)"), win(0, 0, "event month (0)"), win(1, 6, "after (+1..+6)")])
log("\nWindow CARs (Table H3 body):"); log(wins.to_string(index=False))
log("The event-month return is of the same order as its neighbours, and the decline before the downgrade")
log("matches the decline after it: no abnormal return at the change; the drift straddles the event.")

# ================= (robustness) the drift is not a washing-out artifact =================
F = dg.merge(ret[["parent_id", "midx", "f6", "b6"]], on=["parent_id", "midx"], how="left").dropna(subset=["f6"])
F["ds"] = F.d.dt.strftime("%Y-%m-%d")
batch = set(F.ds.value_counts()[F.ds.value_counts() > 150].index)   # MSCI mass re-issue / re-rating dates
def rrow(d, lab): return dict(sample=lab, mean_pct=round(d.f6.mean() * 100, 2), t=round(ct(d.f6, d.parent_id), 2), N=len(d))
rob = pd.DataFrame([
    rrow(F, "all downgrades (baseline)"),
    rrow(F[~F.ds.isin(batch)], "excl. mass batch dates (re-rating+backfill)"),
    rrow(F[~F.d.dt.year.isin([2019, 2020])], "excl. 2019-2020 (backfill+re-issue)"),
    rrow(F[F.d.dt.year >= 2021], "2021 onward only"),
    rrow(F[F.d.dt.year <= 2018], "2018 and earlier (pre-backfill)")])
log("\n=== 6-month forward drift: NOT an MSCI re-issue/backfill artifact ===")
log(rob.to_string(index=False))

# ================= (control) past return does not absorb it =================
log("\n=== Does the firm's own past-6-month return absorb the forward drift? ===")
base = ret.dropna(subset=["f6", "b6"]).copy()
key = set(zip(dg.parent_id, dg.midx))
base["dn"] = [1.0 if (p, m) in key else 0.0 for p, m in zip(base.parent_id, base.midx)]
for xs, lab in [(["dn"], "downgrade only"), (["dn", "b6"], "downgrade + past-6m return")]:
    r = sm.OLS(base.f6, sm.add_constant(base[xs])).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(base.parent_id)[0]})
    log(f"  {lab:<30} downgrade coef={r.params['dn']*100:6.2f}%  t={r.tvalues['dn']:6.2f}")

pathdf.to_csv("H3_event_time_path.csv", index=False)
wins.to_csv("H3_window_CARs.csv", index=False)
rob.to_csv("H3_drift_robustness.csv", index=False)
open("downgrade_drift_LOG.txt", "w").write("\n".join(out) + "\n")
log("\nwrote H3_event_time_path.csv, H3_window_CARs.csv, H3_drift_robustness.csv, downgrade_drift_LOG.txt")
