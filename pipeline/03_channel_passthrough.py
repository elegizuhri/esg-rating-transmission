# 03_channel_passthrough.py (v26) — asymmetric pass-through of WAKIS changes into IAS (6.4).
# Reads the canonical valid-time panel (02); clusters by ultimate parent.
import pandas as pd, numpy as np
P=pd.read_parquet("panel_fy_validtime.parquet")
W=[2018,2019,2021,2022,2023,2024,2025]; A=P[P.dias.notna() & P.yr.isin(W)].copy()
A["dwp"]=A.dwas.clip(lower=0); A["dwn"]=A.dwas.clip(upper=0)
def cl(df,xvs):
    d=df[["dias","yr","group"]+xvs].dropna(); yrs=sorted(d.yr.unique())
    X=np.column_stack([np.ones(len(d))]+[(d.yr==y).astype(float) for y in yrs[1:]]+[d[x].values for x in xvs]); y=d.dias.values
    XtXi=np.linalg.inv(X.T@X); b=XtXi@(X.T@y); e=y-X@b
    S=pd.DataFrame(X*e[:,None]).groupby(d["group"].values).sum().values; meat=S.T@S
    N,k=X.shape; G=S.shape[0]; c=(G/(G-1))*((N-1)/(N-k)); V=c*(XtXi@meat@XtXi); se=np.sqrt(np.diag(V))
    # Wald test pos=neg
    R=np.zeros(X.shape[1]); R[-2]=1; R[-1]=-1; diff=R@b; sed=np.sqrt(R@V@R); 
    return {xvs[i]:(round(b[-len(xvs)+i],3),round((b/se)[-len(xvs)+i],1)) for i in range(len(xvs))}, round(diff,3), round(diff/sed,1)
res,diff,zt=cl(A,["dwp","dwn"])
print("=== 6.4 ASYMMETRIC PASS-THROUGH (parent-clustered) ===")
print(f"  positive {res['dwp']}  negative {res['dwn']}  diff {diff} (z={zt})")
