* TABLE 2 — severity-graded incorporation (year FE, cluster firm), t0 and t+1
* + severity-dependent timing robustness (firm FE)
use "$DATA/panel_fy.dta", clear
keep if inlist(yr,2018,2019,2021,2022,2023,2024,2025)
egen fid = group(issuerid)
foreach s in minor mod sev vs {
    di _n "== severity: `s' =="
    reghdfe d_ias d_`s', absorb(yr) vce(cluster issuerid)      // t0
    reghdfe dias_t1 d_`s', absorb(yr) vce(cluster issuerid)    // t+1
}
* severity-dependent timing: firm-FE robustness
di _n "== robustness: firm FE =="
reghdfe d_ias  d_sev,   absorb(fid) vce(cluster issuerid)      // severe t0, firm FE  (~ -0.059, t -7.8)
reghdfe dias_t1 d_minor, absorb(fid) vce(cluster issuerid)     // minor t+1, firm FE  (~ -0.001, t -1.0)
reghdfe dias_t1 d_tot,   absorb(fid) vce(cluster issuerid)     // aggregate t+1, firm FE (~ +0.001)
* note: severe t0 = 0.0566/1.4286 = 4.3% of a 1.43-pt letter band
