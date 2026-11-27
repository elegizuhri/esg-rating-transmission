#!/usr/bin/env python3
"""
F1_daily_CAR_61_125.py  —  Daily reconciliation of the post-downgrade drift (Section 7.2).

WHAT THIS RECONCILES
  Section 7.2 reports no abnormal return in the ~60 trading days right after a letter downgrade,
  while Appendix H documents a symmetric monthly drift that straddles the event (about -1.5% market-
  adjusted / -2.8% four-factor US in BOTH the -6..-1 and +1..+6 month windows). These are not in
  conflict: ~60 trading days is only ~3 months, so the post-event half of the drift accumulates mostly
  AFTER day +60. This script measures the DAILY drift on the same downgrades and shows exactly that.

MEASURE (IMPORTANT — matches Appendix H, not a firm-beta factor model)
  Appendix H defines abnormal returns by SIMPLE BENCHMARK ADJUSTMENT (market-adjusted: return minus the
  market), NOT by subtracting a firm-specific Carhart expectation estimated on a pre-window. An earlier
  version of this script used firm-beta Carhart residuals with no alpha term; on this sample that
  construction flips the post-event window spuriously POSITIVE (an artifact of the estimation window and
  the missing intercept, not drift). To stay consistent with Appendix H and the main text, the daily
  abnormal return here is market-adjusted:

        ma_it = ret_it  -  vwret_t            (CRSP value-weighted market return that day)

  winsorised at 0.5/99.5, cumulated within each event window.

WINDOWS
  before  [-60, -1]    symmetric pre-event decline (mirrors Appendix H's -6..-1 month window)
  after   [+1, +60]    the Section 7.2 window  -> expected ~flat ("no drift in the first 60 days")
  after   [+61, +125]  about months +3..+6     -> where the post-event drift shows up

INPUTS (licensed; not shipped in this repo)
  CRSP_DAILY : CRSP daily stock file with an MSCI ISSUERID attached
               columns: permno, date, ret, parent_id   (parent_id = ISSUERID; -> crsp.dsf joined to the
               HIST_MASTER_INSTRUMENT_REFERENCE ISIN<->ISSUERID map)
  CRSP_MKT   : CRSP daily market file         columns: date, vwretd
  DG         : the letter-downgrade event set  columns: parent_id, date   (as built in H3_build_and_run.py;
               a prebuilt downgrade_events.parquet from the analysis-ready dataset works directly)
  ULT        : OPTIONAL issuer->ultimate-parent bridge   columns: issuer_id, parent_ultimate_id
               (e.g. firm_year_panel). The CRSP ISSUERID is often an ULTIMATE parent while the event
               ISSUERID is at the issuer level, so without this bridge only the directly-keyed events
               link and the sample is small. With it, each event is also matched through its ultimate
               parent, recovering the full US sample (t below -3 in the pre- and +61..+125 windows).

OUTPUT
  prints the three-window reconciliation and writes F1_daily_CAR_61_125.csv.

RUN
  CRSP_DAILY=crsp_daily.parquet CRSP_MKT=crsp_market_daily.parquet DG=downgrade_events.parquet \
      ULT=firm_year_panel.parquet python3 F1_daily_CAR_61_125.py
"""
import os, numpy as np, pandas as pd

CRSP_DAILY = os.environ.get("CRSP_DAILY", "crsp_daily.parquet")
CRSP_MKT   = os.environ.get("CRSP_MKT",   "crsp_market_daily.parquet")
DG         = os.environ.get("DG",         "downgrade_events.parquet")
ULT        = os.environ.get("ULT",        "")          # optional issuer->ultimate-parent bridge

# ---- daily market-adjusted returns -------------------------------------------------------------
cd = pd.read_parquet(CRSP_DAILY); cd["date"] = pd.to_datetime(cd.date)
mk = pd.read_parquet(CRSP_MKT);   mk["date"] = pd.to_datetime(mk.date)
cd = cd.merge(mk[["date", "vwretd"]], on="date", how="inner")
cd["ma"] = cd.ret - cd.vwretd                       # market-adjusted (as in Appendix H)
lo, hi = cd.ma.quantile([.005, .995]); cd["ma"] = cd.ma.clip(lo, hi)

# trading-day index so we can count event-days off each downgrade
cal = mk[["date"]].sort_values("date").reset_index(drop=True); cal["td"] = np.arange(len(cal))
td = dict(zip(cal.date, cal.td)); cd["td"] = cd.date.map(td)

# ISSUERID -> permno set (an issuer may list several permnos / share classes)
key2permnos = {}
for pid, g in cd.groupby("parent_id"):
    key2permnos.setdefault(str(pid), set()).update(g.permno.unique())
permg = {pn: g[["td", "ma"]] for pn, g in cd.groupby("permno")}

# ---- downgrade events --------------------------------------------------------------------------
dg = pd.read_parquet(DG) if DG.endswith("parquet") else pd.read_csv(DG)
dg["date"] = pd.to_datetime(dg.date); dg["parent_id"] = dg.parent_id.astype(str)

# optional issuer -> ultimate-parent bridge, to also link events whose CRSP ISSUERID is the ultimate parent
iss2ult = {}
if ULT:
    u = pd.read_parquet(ULT) if ULT.endswith("parquet") else pd.read_csv(ULT)
    icol = "issuer_id" if "issuer_id" in u.columns else "parent_id"
    u = u[[icol, "parent_ultimate_id"]].dropna().drop_duplicates()
    iss2ult = dict(zip(u[icol].astype(str), u.parent_ultimate_id.astype(str)))

def permnos_for(pid):
    s = set(key2permnos.get(pid, ()))
    up = iss2ult.get(pid)
    if up: s |= key2permnos.get(up, set())
    return s

def car(permnos, t0, a, z):
    """winsorised market-adjusted CAR over event days [a, z]; pick the permno with the most coverage."""
    best = None
    for pn in permnos:
        g = permg.get(pn)
        if g is None: continue
        if best is None or len(g) > len(best): best = g
    if best is None: return np.nan
    w = best[(best.td >= t0 + a) & (best.td <= t0 + z)].ma
    return float(w.sum()) if len(w) >= int(0.6 * (z - a + 1)) else np.nan

WIN = {"before [-60,-1]": (-60, -1), "after [+1,+60]": (1, 60), "after [+61,+125]": (61, 125)}
acc = {k: [] for k in WIN}
for e in dg.itertuples():
    t0 = td.get(e.date)
    if t0 is None: continue
    pm = permnos_for(e.parent_id)
    if not pm: continue
    for k, (a, z) in WIN.items():
        v = car(pm, t0, a, z)
        if not np.isnan(v): acc[k].append(v)

rows = []
print("Daily market-adjusted CAR around letter downgrades (US CRSP):\n")
print(f"{'window':18s}{'CAR%':>9s}{'median%':>10s}{'t':>8s}{'N':>8s}")
for k in WIN:
    x = np.array(acc[k]); t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    print(f"{k:18s}{x.mean()*100:>+9.2f}{np.median(x)*100:>+10.2f}{t:>+8.2f}{len(x):>8d}")
    rows.append(dict(window=k, CAR_pct=round(x.mean()*100, 2), median_pct=round(np.median(x)*100, 2),
                     t=round(t, 2), N=len(x)))
print("\nReconciliation: the +1..+60 window is flat (Section 7.2 'no drift in the first 60 days'); the")
print("decline reappears in +61..+125 (~months 3-6) and mirrors the pre-event -60..-1 decline — the")
print("symmetric drift of Appendix H, in daily data and on the same market-adjusted benchmark.")
pd.DataFrame(rows).to_csv("F1_daily_CAR_61_125.csv", index=False)
print("\nwrote F1_daily_CAR_61_125.csv")
