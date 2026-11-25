*===========================================================================
* MASTER DO-FILE — "Transmission of Adverse Information Through the MSCI ESG Rating"
* Requires: reghdfe, ftools  (ssc install reghdfe ; ssc install ftools)
* Input panels are built in Python (see ../pipeline) and exported to Stata:
*   panel_fy.dta       : firm-year  (issuerid year ias was tot mod sev vs minor
*                        d_ias d_was d_sev d_mod d_vs d_minor d_tot dias_t1)
*   monthly.dta        : firm-month (issuerid midx ias band lowmo6 fmin12 fmin24
*                        low_on mat_on nprev nfut) ; sustlow = (lowmo6>=2)
*   issue_counts.dta   : firm-issue-date moderate/severe counts & diffs (dmod dsev)
*   issue_onsets.dta   : firm-issue-month low/severe onset flags
*   pricing_panel.dta  : firm-year (issuerid yr dias dwas fwd12w own nonown ctry sector)
*   events.dta         : firm-month (issuerid midx car6 sevonset downgrade contr12 nf)
*   km_events.dta      : severe-onset events (issuerid eventmidx lag era) for Fig 2 / hazard
*===========================================================================
clear all
set more off
global DATA  "../data"      // folder holding the exported .dta panels
global OUT   "../output"    // tables/logs out
cap mkdir "$OUT"
log using "$OUT/stata_reproduction.log", replace text

* NOTE (v26): cluster by ultimate parent (egen pgroup = PARENT_ULTIMATE_ISSUERID, else issuerid);
*             severity counts use valid-time (start<=dec31(t)<=end). See docs/CONSTRUCTION_DOCUMENTATION.md.
do t1_summary.do
do t2_severity.do
do t3_earlylate.do        // Table 3  (early vs late windows)
do t3_yearbyyear.do       // Appendix Table A2 (year-by-year; underlies Table 3)
do t4_ownshare.do
do channel_passthrough.do
do fig2_monthly.do
do t66_reclass_lead_crossissue.do
do t5_pricing.do
do t6_twoevent.do
do t7_externalclock.do    // Section 8 eq.9 external-clock hazard (needs external_spells.dta)

log close
