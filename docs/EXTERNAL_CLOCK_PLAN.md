# External incident clock — identification core (Section 8, eq. 9)

## Why
The in-sample timing tests measure the lag between MSCI's own controversy-logging date
and MSCI's own rating change — one MSCI series against another. That cannot distinguish
informational staleness from MSCI's internal data-entry sequencing. Anchoring event time
on a **provider-independent first-awareness date** converts the estimand into *time-to-update
relative to public information*, which is the object the paper claims to measure.

## Data sources (in order of preference)
1. **RepRisk** (licensed): firm-level ESG incident feed with first-publication dates,
   severity, reach, novelty. Preferred; cannot be scraped — attach a licensed extract.
2. **GDELT DOC 2.0 API** (public): earliest news article mentioning the firm together with
   ESG-adverse terms → a media first-awareness date. `pipeline/09_external_clock.py --scrape`.
3. **Violation Tracker, Good Jobs First** (public): official US enforcement-action dates →
   used both as a source and as the **shared-source placebo** (enforcement dates do not
   co-move mechanically with media).

## Entity resolution
Match external records to MSCI issuers by (i) exact ticker/ISIN where the source carries it,
(ii) normalized legal-name match, (iii) manual review of the residual. Keep match rate and
false-match audit in the appendix. Carry `source` on every incident.

## First-awareness date
Per (firm, key-issue, incident), first-awareness = earliest external record date. De-duplicate
articles within a 30-day window to one incident. Keep only incidents whose severity maps to the
MSCI moderate/severe/very-severe ladder.

## Estimand and model (eq. 9)
Discrete-time complementary-log-log hazard of the first subsequent MSCI letter change, event
time m = months since first-awareness, right-censored at 24 months:
  h_{im} = 1 - exp{ -exp( lambda_m + delta' X_i ) },
X_i = severity, reach, novelty; distance to nearest letter threshold; industry and calendar-
month effects. SE clustered by firm. The **identifying coefficient** is the severity gradient
and the shift of the baseline hazard relative to the internal-clock baseline: a rating that is
timely relative to public information shows a hazard concentrated in the first months after
first-awareness; staleness shows a flat, right-shifted hazard.

## Pre-registered tests
- H4-ext (timeliness): median months-to-update on the external clock > 0 and larger than on the
  internal clock; baseline hazard right-shifted.
- Acceleration: interact lambda_m with the 2021–2025 window; a pure change in MSCI's logging
  date cannot move the external-clock hazard, so a shift here is genuine acceleration.
- Placebo: enforcement-only clock reproduces the lag (not a media artefact).
- Unincorporated-incident-load (consequence): partition firm-months into
  known-but-not-yet-rated vs already-incorporated; test that return/holdings predictability
  concentrates in the former (Section 8, eqs. 7–8).

## Power / feasibility
~7,500 rated issuers; even a 20% match rate yields tens of thousands of firm-incident spells,
ample for the hazard. GDELT + Violation Tracker are free; RepRisk sharpens severity/novelty.

## Reproduction
`python pipeline/09_external_clock.py --scrape --issuers issuers.csv --out incidents.csv`
`python pipeline/09_external_clock.py --estimate --incidents incidents.csv --panel panel_fy.parquet`
`stata -b do stata/t7_externalclock.do`
Offline estimator check (synthetic, not real): `python pipeline/09_external_clock.py --synthetic`.
