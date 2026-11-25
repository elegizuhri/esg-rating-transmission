* §6.3 controversy-channel decomposition + §6.4 asymmetric pass-through
use "$DATA/panel_fy.dta", clear
keep if inlist(yr,2018,2019,2021,2022,2023,2024,2025)
reghdfe d_ias d_sev, absorb(yr) vce(cluster issuerid)      // total severe->dIAS  (~ -0.058)
scalar b_total = _b[d_sev]
reghdfe d_was d_sev, absorb(yr) vce(cluster issuerid)      // severe->dWAKIS       (~ -0.045)
scalar b_wakis = _b[d_sev]
reghdfe d_ias d_was, absorb(yr) vce(cluster issuerid)      // slope / amplification(~ 1.32)
scalar slope = _b[d_was]
di "own-score channel share = " %4.2f (b_wakis*slope)/b_total   // ~1.0
* §6.4 asymmetric pass-through
gen pos = max(d_was,0)
gen neg = min(d_was,0)
reghdfe d_ias pos neg, absorb(yr) vce(cluster issuerid)    // good 1.41 ; bad 1.16
test pos = neg                                             // p<0.001
