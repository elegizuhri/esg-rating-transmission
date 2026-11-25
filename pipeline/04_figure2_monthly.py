import duckdb, pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt, warnings
warnings.filterwarnings('ignore')
con=duckdb.connect('a.db'); con.sql("PRAGMA memory_limit='2GB'"); con.sql("PRAGMA temp_directory='tmp'"); con.sql('PRAGMA threads=4'); con.sql('PRAGMA disable_progress_bar')
SS='jul/HIST_SUMMARY_SCORES_20260731.parquet'; CF='jul/HIST_CONTROVERSIES_20260731.parquet'
mi=lambda d:(d//10000)*12+((d//100)%100); DE=mi(20260731); H=24
# dated IAS changes (latest version per START_DATE)
ias=con.sql(f"""WITH l AS (SELECT ISSUERID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{SS}' WHERE FIELD_ID='INDUSTRY_ADJUSTED_SCORE' AND START_DATE>=20160101) SELECT ISSUERID,START_DATE,v,LAG(v) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) pv FROM l WHERE rn=1 AND v IS NOT NULL""").df()
ias['dias']=ias.v-ias.pv
# dated severe (+very severe) onsets
sev=con.sql(f"""WITH l AS (SELECT ISSUERID,FIELD_ID,START_DATE,TRY_CAST(VALUE AS DOUBLE) v,ROW_NUMBER() OVER(PARTITION BY ISSUERID,FIELD_ID,START_DATE ORDER BY VERSION_START_DATE DESC) rn FROM '{CF}' WHERE FIELD_ID LIKE 'CONTR\\_%\\_N\\_SEVERE' ESCAPE '\\' AND START_DATE>=20160101), pd AS (SELECT ISSUERID,START_DATE,SUM(v) s FROM l WHERE rn=1 AND v IS NOT NULL GROUP BY 1,2) SELECT ISSUERID,START_DATE,s,LAG(s) OVER(PARTITION BY ISSUERID ORDER BY START_DATE) ps FROM pd""").df()
sev['dsev']=sev.s-sev.ps
ev=sev[sev.dsev>1e-9][['ISSUERID','START_DATE']].copy(); ev['ev']=mi(ev.START_DATE); yr=ev.START_DATE//10000
ev['era']=np.where((yr>=2018)&(yr<=2019),'early',np.where((yr>=2021)&(yr<=2025),'late','other')); ev=ev[ev.era!='other']
dg=ias[ias.dias<-1e-9][['ISSUERID','START_DATE']].copy(); dg['dg']=mi(dg.START_DATE)
ev=ev.sort_values('ev'); dg=dg.sort_values('dg')
ev=pd.merge_asof(ev,dg[['ISSUERID','dg']],by='ISSUERID',left_on='ev',right_on='dg',direction='forward')
ev['lag']=ev.dg-ev.ev; ev['cens']=DE-ev.ev
def monthly(sub):
    recs=[]
    for m in range(1,H+1):
        atrisk=((sub.lag.isna()&(sub.cens>=m))|(sub.lag>=m)).sum(); fail=(sub.lag==m).sum()
        recs.append((m,fail/atrisk if atrisk>0 else np.nan))
    d=pd.DataFrame(recs,columns=['month','hazard']); d['cum']=1-(1-d.hazard).cumprod(); return d
mE=monthly(ev[ev.era=='early']); mL=monthly(ev[ev.era=='late'])
tab=pd.DataFrame({'month':mE.month,'hazard_early':mE.hazard.round(4),'cum_early':mE.cum.round(4),'hazard_late':mL.hazard.round(4),'cum_late':mL.cum.round(4)})
tab.to_csv('tab_monthly.csv',index=False)
print('events: early',len(ev[ev.era=="early"]),'late',len(ev[ev.era=="late"]))
print('cum incidence @24mo: early %.2f  late %.2f'%(mE.cum.iloc[-1],mL.cum.iloc[-1]))
# figure
fig,ax=plt.subplots(1,2,figsize=(10,3.9),dpi=150); ce=(0.20,0.30,0.70); cl=(0.80,0.30,0.20)
ax[0].plot(tab.month,100*tab.cum_early,'-o',color=ce,lw=1.9,ms=3.5,label='2018–2019')
ax[0].plot(tab.month,100*tab.cum_late,'--s',color=cl,lw=1.9,ms=3.5,label='2021–2025')
ax[0].set_xlabel('Months since severe controversy'); ax[0].set_ylabel('Cumulative downgrade incidence (%)')
ax[0].set_title('(a) Cumulative probability of a rating downgrade',fontsize=10); ax[0].set_xlim(1,24); ax[0].set_xticks(range(0,25,3)); ax[0].grid(alpha=.3); ax[0].legend(fontsize=8,loc='lower right')
ax[1].plot(tab.month,100*tab.hazard_early,'-o',color=ce,lw=1.6,ms=3.5,label='2018–2019')
ax[1].plot(tab.month,100*tab.hazard_late,'--s',color=cl,lw=1.6,ms=3.5,label='2021–2025')
ax[1].set_xlabel('Months since severe controversy'); ax[1].set_ylabel('Monthly downgrade hazard (%)')
ax[1].set_title('(b) Per-month hazard of a downgrade',fontsize=10); ax[1].set_xlim(1,24); ax[1].set_xticks(range(0,25,3)); ax[1].grid(alpha=.3); ax[1].legend(fontsize=8,loc='upper right')
fig.tight_layout(); fig.savefig('fig_monthly.png',bbox_inches='tight',dpi=150)
print('figure saved')
