* TABLE 1 — summary statistics (firm-year, 2018-2025 excl 2020)
use "$DATA/panel_fy.dta", clear
keep if inlist(yr,2018,2019,2021,2022,2023,2024,2025)
tabstat ias was tot mod sev vs minor d_ias d_was, ///
    stat(n mean sd p25 p50 p75) col(stat) format(%9.3f)
