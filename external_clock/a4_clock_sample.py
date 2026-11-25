#!/usr/bin/env python3
"""Analysis 4: hand-checked clock sample: funnel, representativeness of the 223, severity-reweighted lag,
random 30 cases for an independent second dating."""
import numpy as np, pandas as pd
from scipy import stats
W = "/home/claude/w2"; KIT = "/home/claude/p2/kit"
ons = pd.read_csv(f"{KIT}/data/onsets.csv", dtype={"parent_id": str}, parse_dates=["msci_date"])
par = pd.read_csv(f"{KIT}/data/parents.csv", dtype={"parent_id": str}, low_memory=False).drop_duplicates("parent_id")
o = ons.merge(par[["parent_id", "country", "sector"]], on="parent_id", how="left")
o = o[o.country.isin(["US", "GB"])]
fl = o.flag_backfill_20190701.astype(bool) | o.flag_floor_20170831.astype(bool)
U = o[~fl].copy()
C = pd.read_pickle(f"{W}/x3/contro3_Controversies.pkl"); H = pd.read_pickle(f"{W}/x3/hand3_m.pkl")
H["MSCI date"] = pd.to_datetime(H["MSCI date"]); H["Audited earliest date"] = pd.to_datetime(H["Audited earliest date"], errors="coerce")
ver = H["Audit status"].astype(str).str.startswith("Verified"); v5 = H["MSCI date"] == "2026-03-23"
V = H[ver & ~v5].copy(); V["lag"] = (V["MSCI date"] - V["Audited earliest date"]).dt.days
vs_add = H["Date source"] == "GDELT dated article (very-severe add-on)"
c_in = C.merge(H[["Onset ID"]], on="Onset ID", how="left", indicator=True)
funnel = [
    ("US and UK controversy onsets, excluding the 1 July 2019 backfill and 31 August 2017 floor dates", len(U), len(o) - len(U),
     f"{len(o):,} US/UK onsets before excluding {int(fl.sum()):,} backfill/floor onsets"),
    ("With at least one GDELT article matching the firm and the key issue", len(C), len(U) - len(C),
     "no matched article in the GDELT keyword search"),
    ("Selected for the audit file", len(H), len(C) - (len(H) - int(vs_add.sum())),
     f"{len(H) - int(vs_add.sum())} matched onsets retained after a first screening round "
     f"({int(H[~vs_add]['Onset ID'].isin(C[C['Within 0–90 d']]['Onset ID']).sum())} with an article 0–90 days before the MSCI date), "
     f"plus {int(vs_add.sum())} remaining very severe onsets"),
    ("Incident and earliest public report verified", int(ver.sum()), len(H) - int(ver.sum()),
     "; ".join(f"{k}: {v}" for k, v in H.loc[~ver, "Audit status"].value_counts().items())),
    ("Final sample", len(V), int(v5[ver].sum()), "dated 23 March 2026, MSCI's re-rating of all issuers"),
]
F = pd.DataFrame(funnel, columns=["stage", "N", "dropped", "reason for drop"])
print(F.to_string()); F.to_csv(f"{W}/out/A4_funnel.csv", index=False)

# ------------------------------------------------------------------ representativeness: 223 vs other onsets
U["verified"] = U.onset_id.isin(V["Onset ID"])
print("verified onsets found among the 14,207:", int(U.verified.sum()))
comp = pd.read_parquet(f"{W}/wrds_extra/compustat_annual.parquet"); comp["parent_id"] = comp.parent_id.astype(str)
comp["at"] = pd.to_numeric(comp["at"], errors="coerce"); comp["datadate"] = pd.to_datetime(comp.datadate).astype("datetime64[ns]")
comp = comp[comp["at"] > 0].sort_values("datadate")
x = U.copy(); x["_d"] = (x.msci_date - pd.DateOffset(months=3)).astype("datetime64[ns]")
x = pd.merge_asof(x.sort_values("_d"), comp[["parent_id", "datadate", "at"]], left_on="_d", right_on="datadate",
                  by="parent_id", direction="backward", tolerance=pd.Timedelta(days=550))
x["log_at"] = np.log(x["at"]); x["year"] = x.msci_date.dt.year
x["period"] = np.select([x.year <= 2019, x.year == 2020, x.year <= 2025], ["2017–2019", "2020", "2021–2025"], "2026")
rows = []


def share_rows(var, lab):
    tab = pd.crosstab(x[var], x.verified)
    chi = stats.chi2_contingency(tab)
    for k in tab.index:
        rows.append(dict(variable=lab, category=k, verified_pct=100 * tab.loc[k, True] / tab[True].sum(),
                         other_pct=100 * tab.loc[k, False] / tab[False].sum(), test=f"chi2 p = {chi[1]:.3f}"))


share_rows("severity", "Severity"); share_rows("period", "Year of MSCI date"); share_rows("country", "Country")
sec = x.sector.fillna("missing"); top = sec.value_counts().index[:10]
x["sector2"] = np.where(sec.isin(top), sec, "other"); share_rows("sector2", "Sector")
a, b = x[x.verified].log_at.dropna(), x[~x.verified].log_at.dropna()
tt = stats.ttest_ind(a, b, equal_var=False)
rows.append(dict(variable="Log total assets (Compustat)", category=f"mean (N = {len(a)} / {len(b):,})",
                 verified_pct=a.mean(), other_pct=b.mean(), test=f"t = {tt.statistic:.2f}"))
rows.append(dict(variable="Onsets", category="N", verified_pct=int(x.verified.sum()), other_pct=int((~x.verified).sum()), test=""))
R = pd.DataFrame(rows); R.to_csv(f"{W}/out/A4_representativeness.csv", index=False); print(R.round(2).to_string())

# ------------------------------------------------------------------ severity-reweighted lag
pop = U.severity.value_counts(normalize=True)
V["sevk"] = V.Severity.map({"moderate": "moderate", "severe": "severe", "very_severe": "very_severe", "very severe": "very_severe"}).fillna(V.Severity)
smp = V.sevk.value_counts(normalize=True)
V["w"] = V.sevk.map(pop / smp)


def wq(v, w, q):
    i = np.argsort(v); v, w = v[i], w[i]; c = np.cumsum(w) / w.sum(); return v[np.searchsorted(c, q)]


lv, wv = V.lag.values.astype(float), V.w.values
RW = pd.DataFrame([
    dict(weighting="Unweighted (verified 223)", median=np.median(lv), mean=lv.mean(), p25=np.percentile(lv, 25), p75=np.percentile(lv, 75),
         le90=100 * (lv <= 90).mean()),
    dict(weighting="Reweighted to the severity mix of the 14,207 onsets", median=wq(lv, wv, .5), mean=np.average(lv, weights=wv),
         p25=wq(lv, wv, .25), p75=wq(lv, wv, .75), le90=100 * np.average(lv <= 90, weights=wv))])
mix = pd.DataFrame({"share_all_onsets": pop, "share_verified": smp, "weight": pop / smp})
print(mix.round(3)); print(RW.round(1).to_string())
RW.to_csv(f"{W}/out/A4_reweighted_lag.csv", index=False); mix.to_csv(f"{W}/out/A4_severity_mix.csv")

# ------------------------------------------------------------------ random 30 for an independent second dating
rs = V.sample(30, random_state=20261031)
blind = rs[["ID", "Firm", "Country", "Issue", "Severity", "MSCI date", "Identified incident / note"]].copy()
blind.columns = ["ID", "Firm", "Country", "MSCI key issue", "Severity", "MSCI date", "Incident (as identified in audit 1)"]
blind["Second coder: earliest public date"] = ""; blind["Second coder: source link"] = ""; blind["Second coder: notes"] = ""
key = rs[["ID", "Audited earliest date", "Audit source link"]]
with pd.ExcelWriter(f"{W}/out/A4_second_coder_30.xlsx") as xw:
    blind.to_excel(xw, sheet_name="For second coder", index=False)
    key.to_excel(xw, sheet_name="First coder (keep hidden)", index=False)
print("checked-by field in the matched file:", C["Checked by"].value_counts(dropna=False).to_dict())
