* §6.6 reclassification, lead, cross-issue ; Appendix A4 downgrade-horizon
* (a) RECLASSIFICATION — at a severe onset, what does same-issue moderate count do?
use "$DATA/issue_counts.dta", clear          // issuerid issue start_date dmod dsev
keep if dsev>0 & !missing(dsev)
gen fall = dmod<0
gen same = dmod==0
gen rise = dmod>0
summ fall same rise                           // 0.56 / 0.25 / 0.19 ; N=22,438
* (b) LEAD — months from same-issue moderate onset to next same-issue severe onset
use "$DATA/lead_pairs.dta", clear             // gap (months) per moderate->next-severe pair, 1..36
summ gap, detail                              // median 6 ; mean 10.1 ; p(>=6)=52% ; n=13,338
* (c) CROSS-ISSUE — severe onset ~ same-issue vs different-issue prior-6m moderate onset, firm FE
use "$DATA/issue_onsets.dta", clear           // issuerid issue midx sev_on same6 cross6
egen fid=group(issuerid)
reghdfe sev_on cross6 same6, absorb(fid) vce(cluster issuerid)   // cross +0.00013(6.2) ; same +0.0155(40.3)
* (d) APPENDIX A4 — downgrade within H months ~ sustained-low + IAS level, firm FE
use "$DATA/monthly.dta", clear
keep if nprev>=6
gen sustlow = lowmo6>=2
egen fid=group(issuerid)
gen down12 = (fmin12 < band) if !missing(fmin12)
gen down24 = (fmin24 < band) if !missing(fmin24)
reghdfe down12 sustlow ias, absorb(fid) vce(cluster issuerid)    // -0.009 (-5.8)
reghdfe down24 sustlow ias, absorb(fid) vce(cluster issuerid)    // -0.023 (-12.7)
