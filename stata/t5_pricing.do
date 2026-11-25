* TABLE 5 — subsidiary pricing check (own vs non-own component of dIAS -> 12m fwd return)
use "$DATA/pricing_panel.dta", clear          // issuerid yr dias dwas fwd12w ctry sector
* components (own = bhat*dWAKIS ; nonown = dIAS - bhat*dWAKIS)
quietly regress dias dwas
scalar bhat = _b[dwas]                         // ~1.12
gen own    = bhat*dwas
gen nonown = dias - bhat*dwas
egen cid=group(ctry)
egen sid=group(sector)
reghdfe fwd12w own nonown, absorb(yr cid sid) vce(cluster issuerid)   // own -0.006(-1.5) ; nonown -0.003(-1.4)
test own nonown                                                       // F=2.04 p=0.13 ; N=43,196
* robustness: year+country FE only
reghdfe fwd12w own nonown, absorb(yr cid) vce(cluster issuerid)       // own -0.0066 ; nonown -0.0026 ; F=2.05 p=0.128
test own nonown
