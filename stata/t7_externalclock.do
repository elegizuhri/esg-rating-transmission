* t7_externalclock.do -- External-incident-clock hazard (paper Section 8, eq. 9)
* Input: external_spells.dta (one row per incident x month-since-first-awareness),
*        built by pipeline/09_external_clock.py after the incident feed is attached.
*        Vars: issuerid event m mbin severity dist_threshold industry cal_month source
use "$DATA/external_spells.dta", clear

* Discrete-time complementary-log-log hazard of a rating letter change, event time =
* months since the PROVIDER-INDEPENDENT first-awareness date (not MSCI's logging date).
cloglog event i.mbin severity dist_threshold i.industry i.cal_month, vce(cluster issuerid)
estimates store ext_full
di "Severity gradient on the external clock (identification):"
lincom severity                         // positive => more severe PUBLIC incidents incorporated faster

* PLACEBO / shared-source check: enforcement dates only (do not co-move with media).
preserve
    keep if source=="enforcement"
    cloglog event i.mbin severity dist_threshold i.industry i.cal_month, vce(cluster issuerid)
    di "If the lag persists here, it is not a media-sourcing artefact."
restore

* Optional: compare internal-clock vs external-clock median lag (descriptive).
* table , stat(p50 m_internal) stat(p50 m_external)
