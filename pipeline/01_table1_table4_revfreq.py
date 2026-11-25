# 01_table1_table4_revfreq.py (v26) — Table 1 (summary stats) + Table 4 (own-score share).
# Reads the canonical valid-time panel built by 02 (panel_fy_validtime.parquet); clusters by
# ultimate parent.  Run 02 first.
import pandas as pd, numpy as np, glob
P=pd.read_parquet("panel_fy_validtime.parquet")
W=[2018,2019,2021,2022,2023,2024,2025]
A=P[P.dias.notna() & P.yr.isin(W)].copy()
# --- Table 1 ---
def st(x): x=x.dropna().astype(float); return (int(x.size),round(x.mean(),3),round(x.std(),3),round(x.quantile(.25),2),round(x.quantile(.5),2),round(x.quantile(.75),2))
print("=== TABLE 1 (canonical, ΔIAS analysis sample) ===  N mean sd p25 med p75")
for lab,c in [("IAS","ias"),("WAKIS","was"),("Total controversies","tot"),("Moderate","c_mod"),
              ("Severe","c_sev"),("Very severe","c_vs"),("Minor/residual","c_minor"),("dIAS","dias"),("dWAKIS","dwas")]:
    print(f"  {lab:20}",st(A[c]))
# --- Table 4: own-score share R^2 (dias ~ dwas) across FE specs ---
def r2(df,fe):
    d=df[["dias","dwas","yr"]].dropna()
    if fe=="pooled": X=np.column_stack([np.ones(len(d)),d.dwas.values])
    else:
        yrs=sorted(d.yr.unique()); X=np.column_stack([np.ones(len(d))]+[(d.yr==y).astype(float) for y in yrs[1:]]+[d.dwas.values])
    y=d.dias.values; b=np.linalg.lstsq(X,y,rcond=None)[0]; e=y-X@b; return 1-(e@e)/(((y-y.mean())**2).sum())
d=A[["dias","dwas","ISSUERID"]].dropna(); yw=(d.dias-d.groupby("ISSUERID").dias.transform("mean")).values
xw=(d.dwas-d.groupby("ISSUERID").dwas.transform("mean")).values; bw=(xw@yw)/(xw@xw); ew=yw-bw*xw
print("\n=== TABLE 4 own-score share R^2 ===")
print(f"  pooled {r2(A,'pooled')*100:.1f}%  +yearFE {r2(A,'year')*100:.1f}%  within-firm {(1-(ew@ew)/((yw**2).sum()))*100:.1f}%")
# --- revision frequency (Table 4 panel b / 6.1): share of firm-years with no change in severe count ---
A2=A.dropna(subset=['d_c_sev']); print(f"\n6.1 no-change in severe count: {(A2.d_c_sev==0).mean()*100:.1f}%")
