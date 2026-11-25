* TABLE 4 — share of rating-change variance attributable to own WAKIS (R2/adjR2/within)
use "$DATA/panel_fy.dta", clear
keep if inlist(yr,2018,2019,2021,2022,2023,2024,2025)
egen fid = group(issuerid)
regress d_ias d_was, vce(cluster issuerid)                 // Pooled  R2=adjR2=0.412
di "pooled R2 = " e(r2) "  adjR2 = " e(r2_a)
reghdfe d_ias d_was, absorb(yr)  vce(cluster issuerid)     // within-year R2 ~0.412
di "within-year R2 = " e(r2_within)
reghdfe d_ias d_was, absorb(fid) vce(cluster issuerid)     // within-firm  R2 ~0.375
di "within-firm R2 = " e(r2_within)
reghdfe d_ias d_was, absorb(fid yr) vce(cluster issuerid)  // within firm&year ~0.375
di "within firm&year R2 = " e(r2_within)
* by-year own-score share
foreach y in 2018 2019 2021 2022 2023 2024 2025 {
    quietly regress d_ias d_was if yr==`y'
    di "`y'  R2 = " %5.3f e(r2)
}
