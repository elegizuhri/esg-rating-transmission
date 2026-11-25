* TABLE 3 — early vs late incorporation-timing windows (year FE, cluster firm)
* Windows:  early = 2018-2019 ;  late = 2021-2025 ;  full = 2018-2025 excl 2020
* Mirrors pipeline/02_table2_table3_severity.py (year-demeaned OLS == absorb(yr)).
use "$DATA/panel_fy.dta", clear

gen byte early = inlist(yr,2018,2019)
gen byte late  = inlist(yr,2021,2022,2023,2024,2025)
gen byte full  = inlist(yr,2018,2019,2021,2022,2023,2024,2025)

foreach w in early late full {
    di _n "================ window: `w' ================"
    reghdfe d_ias   d_tot if `w'==1, absorb(yr) vce(cluster issuerid)   // aggregate, t
    reghdfe dias_t1 d_tot if `w'==1, absorb(yr) vce(cluster issuerid)   // aggregate, t+1
    reghdfe d_ias   d_sev if `w'==1, absorb(yr) vce(cluster issuerid)   // severe,    t
    reghdfe dias_t1 d_sev if `w'==1, absorb(yr) vce(cluster issuerid)   // severe,    t+1
}

* Robustness: late window restricted to firms already rated in 2018
bys issuerid: egen byte rated18 = max(yr==2018)
di _n "== late, firms rated in 2018 only (expect aggregate t0 ~ -0.012, t ~ -9.4, N~102,880) =="
reghdfe d_ias d_tot if late==1 & rated18==1, absorb(yr) vce(cluster issuerid)

* Expected (July-2026 vintage):
*   early  agg_t0 +0.0084(+4.8)  agg_t1 -0.0022(-3.2)  sev_t0 -0.0721(-5.1)  sev_t1 +0.0779(+6.8)  N 38,668
*   late   agg_t0 -0.0146(-12.7) agg_t1 -0.0034(-4.8)  sev_t0 -0.0496(-5.9)  sev_t1 -0.0276(-5.2)  N 375,507
*   full   agg_t0 -0.0031(-2.8)  agg_t1 -0.0028(-5.6)  sev_t0 -0.0566(-7.7)  sev_t1 +0.0052(+1.0)  N 414,175
