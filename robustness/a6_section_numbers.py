import duckdb, numpy as np, pandas as pd
W="/home/claude/w2"; CF=f"{W}/jul/HIST_CONTROVERSIES_20260731.parquet"
con=duckdb.connect()
# --- 2020 measurement check: severity records ending / starting on the same day in 2020
sevre="regexp_matches(FIELD_ID,'_(MODERATE|SEVERE|VERY_SEVERE)_CONTROVERSIES$')"
r=con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,END_DATE,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE {sevre})
 SELECT END_DATE d, COUNT(*) n, COUNT(DISTINCT ISSUERID) iss FROM l WHERE rn=1 AND END_DATE BETWEEN 20180101 AND 20251231 GROUP BY 1 ORDER BY n DESC LIMIT 6""").df(); print("most common END_DATEs:\n",r)
r2=con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE {sevre})
 SELECT START_DATE d, COUNT(*) n, COUNT(DISTINCT ISSUERID) iss FROM l WHERE rn=1 AND START_DATE BETWEEN 20180101 AND 20251231 GROUP BY 1 ORDER BY n DESC LIMIT 6""").df(); print("most common START_DATEs:\n",r2)
P=pd.read_parquet(f"{W}/panel_fy_validtime.parquet")
def cl(d,y,xs,c="group",fe_firm=False):
    d=d.dropna(subset=[y]+xs).copy(); d["yr"]=d.yr.astype(int)
    Y=d[y].values.astype(float); X=d[xs].values.astype(float)
    # demean by year (and firm if requested) via iterative demeaning
    def dm(a,keys):
        a=a.copy()
        for _ in range(30 if len(keys)>1 else 1):
            for k in keys:
                a=a-pd.DataFrame(a).groupby(d[k].values).transform('mean').values
        return a
    keys=["yr"]+(["ISSUERID"] if fe_firm else [])
    Yd=dm(Y.reshape(-1,1),keys).ravel(); Xd=dm(X,keys)
    XtXi=np.linalg.inv(Xd.T@Xd); b=XtXi@(Xd.T@Yd); e=Yd-Xd@b
    S=pd.DataFrame(Xd*e[:,None]).groupby(d[c].values).sum().values; N,k=Xd.shape; G=S.shape[0]
    se=np.sqrt(np.diag((G/(G-1))*((N-1)/(N-k))*(XtXi@(S.T@S)@XtXi)))
    return {x:(round(b[i],4),round(b[i]/se[i],2)) for i,x in enumerate(xs)}, N, G
W8=[2018,2019,2021,2022,2023,2024,2025]
F=P[P.yr.isin(W8)].dropna(subset=["dias","d_c_sev"])
F20=P[P.yr.isin(W8+[2020])].dropna(subset=["dias","d_c_sev"])
print("N excl/incl 2020:",len(F),len(F20))
for c in ["c_mod","c_sev","c_vs"]:
    print(c,"incl2020",cl(F20,"dias",["d_"+c]))
print("firm FE severe:",cl(F,"dias",["d_c_sev"],fe_firm=True))
# pass-through by severity: dWAKIS response and dIAS response, slope dIAS on dWAKIS
sl=cl(F,"dias",["dwas"]); print("slope dIAS on dWAKIS:",sl)
for c in ["c_mod","c_sev","c_vs"]:
    print(c,"dIAS",cl(F,"dias",["d_"+c])[0],"dWAKIS",cl(F,"dwas",["d_"+c])[0])
# R2
d=F.dropna(subset=["dwas"]); 
def r2(y,x): return np.corrcoef(y,x)[0,1]**2
print("R2 pooled",round(r2(d.dias,d.dwas),3))
yd=d.dias-d.groupby("yr").dias.transform("mean"); xd=d.dwas-d.groupby("yr").dwas.transform("mean"); print("within-year",round(r2(yd,xd),3))
yf=d.dias-d.groupby("ISSUERID").dias.transform("mean"); xf=d.dwas-d.groupby("ISSUERID").dwas.transform("mean"); print("within-firm",round(r2(yf,xf),3))
# Table 1 (consistent valid-time severity counts; no total/residual)
d=F
rows=[]
for v,l in [("ias","IAS"),("was","WAKIS"),("c_mod","Moderate controversies"),("c_sev","Severe controversies"),("c_vs","Very severe controversies"),("dias","ΔIAS"),("dwas","ΔWAKIS"),("d_c_mod","ΔModerate"),("d_c_sev","ΔSevere"),("d_c_vs","ΔVery severe")]:
    s=d[v].dropna(); rows.append(dict(var=l,N=len(s),mean=s.mean(),sd=s.std(),p25=s.quantile(.25),med=s.median(),p75=s.quantile(.75)))
T1=pd.DataFrame(rows); print(T1.round(3).to_string()); T1.to_csv(f"{W}/out/T1_new.csv",index=False)
print("share firm-years with any severity change:",round(((d.d_c_mod!=0)|(d.d_c_sev!=0)|(d.d_c_vs!=0)).mean(),3),
      "severe change:",round((d.d_c_sev!=0).mean(),3), "issuers",d.ISSUERID.nunique(),"groups",d.group.nunique())
