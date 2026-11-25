* APPENDIX TABLE A2 — single-year (year-by-year) timing regressions; underlies Table 3 (cluster firm)
use "$DATA/panel_fy.dta", clear
foreach y in 2018 2019 2020 2021 2022 2023 2024 2025 2026 {
    di _n "== year `y' =="
    regress d_ias d_sev if yr==`y', vce(cluster issuerid)          // severe t0
    regress d_ias d_tot if yr==`y', vce(cluster issuerid)          // aggregate t0
    cap regress dias_t1 d_tot if yr==`y', vce(cluster issuerid)    // aggregate t+1 (n/a for 2026)
}
