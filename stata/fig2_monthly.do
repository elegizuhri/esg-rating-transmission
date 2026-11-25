* FIGURE 2 — cumulative downgrade incidence & hazard after a severe controversy; cloglog HR
* km_events.dta: one row per severe-onset event: issuerid eventmidx lag(=months to downgrade,. if none) era(0=2018-19,1=2021-25) cens
use "$DATA/km_events.dta", clear
gen fail = !missing(lag)
gen dur  = cond(fail, lag, min(cens,24))
stset dur, failure(fail==1)
sts graph, by(era) failure ylabel(0(.1).7) title("Cumulative probability of a downgrade")   // Fig 2(a)
* per-month hazard & later/earlier ratio via discrete-time complementary log-log
* expand to person-months 1..dur, event=fail in last month
expand dur
bysort issuerid eventmidx: gen m = _n
gen event = (m==dur & fail==1)
cloglog event i.m i.era, vce(cluster issuerid)
di "late-era HR = " exp(_b[1.era])    // ~1.54 ; coef ~0.431 (z 12.6)
* anchors: cumulative incidence @24m early 47% / late 70% ; events early 2665 late 4994
