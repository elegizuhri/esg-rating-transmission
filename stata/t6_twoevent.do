* TABLE 6 — preliminary two-event study (6-mo fwd market-adjusted CAR around events)
use "$DATA/events.dta", clear                 // issuerid midx car6 sevonset downgrade contr12 nf
keep if nf>=6
* unconditional means
mean car6 if sevonset==0 & downgrade==0                    // no event  -0.0016
mean car6 if sevonset==1                                   // severe onset -0.0289 (N 1,276)
mean car6 if downgrade==1                                  // downgrade all +0.0192 (N 4,169)
mean car6 if downgrade==1 & contr12==1                     // controversy-linked -0.0357 (N 189)
mean car6 if downgrade==1 & contr12==0                     // not linked +0.0218 (N 3,980)
* firm-FE regression with disjoint event dummies
gen dg_linked   = downgrade*contr12
gen dg_unlinked = downgrade*(1-contr12)
egen fid=group(issuerid)
reghdfe car6 sevonset dg_linked dg_unlinked, absorb(fid) vce(cluster issuerid)
*   sevonset -0.0123(-2.0) ; dg_linked -0.0130(-0.8) ; dg_unlinked +0.0272(+0.7)
