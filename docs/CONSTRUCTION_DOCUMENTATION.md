# CONSTRUCTION DOCUMENTATION
**"The Transmission of Firm-Specific Adverse Information Through the MSCI ESG Rating"** — reproduction record, journal-submission standard.

Every table, figure, and narrative statistic in the draft is documented below with data source, sample, variable construction, estimating equation, fixed effects, standard errors, exact estimated values, and draft location. Vintage: MSCI **July-2026** extract (`HIST_*_20260731`). Returns: LSEG monthly total returns (`monthly_total_returns.csv`, 2013m1–2026m7).

## 0. DATA SOURCES AND KEYS
- **MSCI summary scores** `HIST_SUMMARY_SCORES_20260731.parquet` (long: `ISSUERID, FIELD_ID, VALUE, START_DATE, VERSION_START_DATE`). Fields: `INDUSTRY_ADJUSTED_SCORE` (IAS), `WEIGHTED_AVERAGE_SCORE` (WAKIS).
- **MSCI controversies** `HIST_CONTROVERSIES_20260731.parquet`. Fields: `TOTAL_NUMBER_CONTROVERSIES`; per-issue `CONTR_<ISSUE>_N_SEVERE`; `<ISSUE>_MODERATE_CONTROVERSIES`, `<ISSUE>_SEVERE_CONTROVERSIES`, `<ISSUE>_VERY_SEVERE_CONTROVERSIES`.
- **MSCI instrument reference** `HIST_MASTER_INSTRUMENT_REFERENCE_none_20260831.parquet` (`ISSUERID, ISIN`) — MSCI↔returns join.
- **MSCI issuer reference** `HIST_MASTER_ISSUER_REFERENCE_20260831.parquet` (`ISSUERID, GICS_SECTOR, ISSUER_CNTRY_DOMICILE`) — industry FE.
- **LSEG returns** `monthly_total_returns.csv` (`isin, date, tr_return_pct, tri, ISSUER_CNTRY_DOMICILE`).
- **As-of (point-in-time) rule:** per (ISSUERID, period), take latest `VERSION_START_DATE` per `START_DATE`, then most recent `START_DATE` ≤ period end (ASOF). Removes back-filled restatements.
- **27 key issues:** ACCESS_TO_FIN, ACCESS_TO_HLTHCRE, BIODIV_LAND_USE, CARBON_EMISSIONS, CHEM_SAFETY, COMM_REL, CONTROV_SRC, E_WASTE, FINANCING_ENV_IMP, FIN_PROD_SAFETY, HLTH_SAFETY, HUMAN_CAPITAL_DEV, INS_CLIMATE_CHG_RISK, LABOR_MGMT, OPPS_CLN_TECH, OPPS_GREEN_BUILDING, OPPS_NUTRI_HLTH, OPPS_RENEW_ENERGY, PACK_MAT_WASTE, PRIVACY_DATA_SEC, PROD_CARB_FTPRNT, PROD_SFTY_QUALITY, RAW_MAT_SRC, RESPONSIBLE_INVEST, SUPPLY_CHAIN_LAB, TOXIC_EMISS_WSTE, WATER_STRESS.

## 1. CONSTRUCTED PANELS
- **P1 firm-year** (`panel_fy`): (ISSUERID, year) 2016–2026; main window change-years 2018–2025 excl. 2020. `ias, was` as-of Dec; `tot` (=TOTAL_NUMBER_CONTROVERSIES), `sev` (=Σ CONTR_*_N_SEVERE), `mod,vs` (=Σ per-issue MODERATE/VERY_SEVERE), `minor=max(tot−mod−sev−vs,0)`. Adjacent-year (gap==1) first differences `d_ias(ΔIAS), d_was(ΔWAKIS), d_sev,d_mod,d_vs,d_minor,d_tot`; lead `dias_t1=ias(t+1)−ias(t)`. N(ΔIAS)=414,175.
- **P2 monthly** (`monthly`): (ISSUERID, month) 2017m1–2026m7. As-of month-end IAS; `band=floor(IAS/(10/7))`; `low_on` (moderate onsets), `mat_on` (severe+very-severe onsets). Rolling: `lowmo6` (prior-6m low onset months), `matF6` (future-6m material), `fmin6/12/18/24` (future letter minima), `nprev/nfut`.
- **P3 issue-level** (`low_o`,`sev_o`): (ISSUERID, issue, month) onsets; plus per-(firm,issue,date) mod/sev counts and Δ (reclassification, lead).
- **P4 pricing** (`pricing_panel`): (ISSUERID, year) 2018–2024; `dias,dwas`, `fwd12=tri(Dec t+1)/tri(Dec t)−1` (winsor 1/99 → `fwd12w`), `ctry`, `sector`. N=43,296 (yr+ctry FE)/43,196 (+sector).
- **P5 event-study**: firm-month `ra=r−country×month mean`; `car6=Σ ra over [m+1,m+6]`; flags `sevonset,downgrade,contr12`. 2016m1–2025m12.
- **Onset** = positive month-to-month increment of a severity's summed count, dated to the observation month. **Band width** = 10/7 ≈ 1.4286.

---
## 2. TABLES

### TABLE 1 — Summary statistics  [§4]  (P1, 2018–2025 excl. 2020)
| Variable | N | Mean | SD | p25 | Median | p75 |
|---|---|---|---|---|---|---|
| IAS | 469,613 | 5.125 | 2.290 | 3.4 | 5.2 | 6.9 |
| WAKIS | 468,690 | 4.817 | 1.076 | 4.2 | 4.8 | 5.5 |
| Total controversies | 471,871 | 6.412 | 14.164 | 0.0 | 1.0 | 5.0 |
| Moderate | 471,871 | 0.883 | 2.125 | 0.0 | 0.0 | 1.0 |
| Severe | 471,871 | 0.214 | 0.742 | 0.0 | 0.0 | 0.0 |
| Very severe | 471,871 | 0.010 | 0.139 | 0.0 | 0.0 | 0.0 |
| Minor/residual | 471,871 | 5.315 | 12.315 | 0.0 | 1.0 | 4.0 |
| ΔIAS | 414,175 | 0.050 | 0.537 | 0.0 | 0.0 | 0.0 |
| ΔWAKIS | 412,104 | 0.035 | 0.269 | 0.0 | 0.0 | 0.0 |

### TABLE 2 — Severity-graded incorporation  [§6.2]
Model: ΔIAS_it = α_t + β·ΔC^s_it + ε_it, **separately per severity s**; year FE; SE clustered by firm. Sample P1 2018–2025 excl. 2020.
| Severity | Mean/yr | t0: β (t) | t+1: β (t) |
|---|---|---|---|
| Minor/residual | 5.172 | −0.0021 (−1.8) | −0.0037 (−6.6) |
| Moderate | 0.853 | −0.0054 (−2.5) | +0.0041 (+2.2) |
| Severe | 0.205 | −0.0566 (−7.7) | +0.0052 (+1.0) |
| Very severe | 0.011 | −0.3320 (−6.8) | −0.0333 (−1.2) |
Tied narrative: severe t0 −0.057 = **4.3%** of a 1.43 band. Severity-dependent-timing robustness: severe t0 firm-FE −0.0589 (−7.8); severe t+1 +0.0053 (1.0); minor t+1 firm-FE −0.0006 (−1.0); aggregate t+1 year-FE −0.0028 (−5.6), firm-FE +0.0010 (+1.8) → low-severity lag not firm-FE robust.

### TABLE 3 — Early vs late incorporation timing  [§6.2]  (aggregate & severe count; year FE; SE clustered by firm)
Windows: early = change-years 2018–2019; late = 2021–2025; full = 2018–2025 excl. 2020. Mirrors `pipeline/02_table2_table3_severity.py` (`tab_earlylate.csv`) and `stata/t3_earlylate.do`.
| Horizon | Early 2018–19 | Late 2021–25 | Full (excl. 2020) |
|---|---|---|---|
| Aggregate, t | +0.0084 (+4.8) | −0.0146 (−12.7) | −0.0031 (−2.8) |
| Aggregate, t+1 | −0.0022 (−3.2) | −0.0034 (−4.8) | −0.0028 (−5.6) |
| Severe, t | −0.0721 (−5.1) | −0.0496 (−5.9) | −0.0566 (−7.7) |
| Severe, t+1 | +0.0779 (+6.8) | −0.0276 (−5.2) | +0.0052 (+1.0) |
| N (firm-years) | 38,668 | 375,507 | 414,175 |

Robustness: restricting the late window to firms already rated in 2018 leaves aggregate t0 = −0.0120 (−9.4), N = 102,880 → the acceleration is not a post-2020 universe-expansion artefact. Reading: severe incorporated contemporaneously throughout; the low-severity–dominated aggregate is deferred early (negative only at t+1) and contemporaneous from 2021 onward.

### APPENDIX TABLE A2 — Year-by-year timing  [underlies Table 3]  (single-year OLS; SE clustered by firm)
| Year | Severe t: β(t) | Agg t: β(t) | Agg t+1: β(t) | N |
|---|---|---|---|---|
| 2018 | −0.164 (−2.1) | −0.000 (−0.1) | −0.005 (−2.2) | 18,092 |
| 2019 | −0.071 (−4.9) | +0.010 (+5.1) | −0.002 (−2.5) | 20,576 |
| 2020 (COVID) | −0.055 (−9.0) | −0.006 (−5.3) | −0.002 (−4.0) | 66,984 |
| 2021 | −0.079 (−2.9) | −0.037 (−10.8) | +0.002 (+0.9) | 72,111 |
| 2022 | −0.087 (−5.5) | −0.014 (−2.9) | −0.002 (−0.9) | 74,008 |
| 2023 | +0.109 (+6.0) | −0.006 (−3.3) | −0.003 (−2.0) | 75,187 |
| 2024 | −0.043 (−2.6) | −0.016 (−7.6) | −0.012 (−6.3) | 76,528 |
| 2025 | −0.098 (−7.6) | −0.012 (−9.2) | −0.002 (−1.5) | 77,673 |
| 2026 (partial) | −0.036 (−1.5) | −0.066 (−4.5) | n/a | 78,657 |

### TABLE 4 — Own-score share of rating-change variance  [§6.3]
Model: ΔIAS_it = a + b·ΔWAKIS_it + u_it. Sample P1 2018–2025 excl. 2020; N≈410,436.
| Specification | R² | adj R² | within R² |
|---|---|---|---|
| Pooled OLS | 0.412 | 0.412 | — |
| + Year FE | 0.413 | 0.413 | 0.412 |
| + Firm FE | — | — | 0.375 |
| + Firm & year FE | — | — | 0.375 |
By-year R²: 2018 0.523; 2019 0.460; 2021 0.269; 2022 0.367; 2023 0.380; 2024 0.484; 2025 0.506 (range 0.27–0.52). Non-own ≈ 0.59 (upper bound).
**Controversy-channel (narrative):** ΔIAS~Δsevere −0.0577 (−8.1); ΔWAKIS~Δsevere −0.0454 (−13.6); ΔIAS~ΔWAKIS slope **1.32** (119.1); channel share = (−0.0454×1.32)/−0.0577 ≈ **≈100%** own-score, ~1.3× amplification, residual ≈0.

### TABLE 5 — Subsidiary pricing check  [§6.7]
Components (P4): b̂ from ΔIAS~ΔWAKIS (b̂=1.12); own=b̂·ΔWAKIS; nonown=ΔIAS−b̂·ΔWAKIS. Model: fwd12w = a + β_own·own + β_nonown·nonown + FE + e; FE year+country+GICS sector; SE clustered by firm; fwd12 winsor 1/99.
| Dependent: 12m-fwd total return | Coef (t) |
|---|---|
| Own-score component of ΔIAS | −0.006 (−1.5) |
| Non-own-score component of ΔIAS | −0.003 (−1.4) |
| Joint test (both=0) | F=2.04 (p=0.13) |
| FE / N | year, country, industry / 43,196 |
Robustness (year+country FE only): own −0.0066 (−1.77); nonown −0.0026 (−1.07); F=2.05 p=0.128; N=43,296.

### TABLE 6 — Preliminary two-event study  [§8]  (P5; firm FE; SE clustered by firm)
| Event | Mean CAR6 | N | FE coef (t) |
|---|---|---|---|
| No event | −0.0016 | 780,460 | — |
| Severe controversy onset | −0.0289 | 1,276 | −0.0123 (−2.0) |
| Downgrade (all) | +0.0192 | 4,169 | — |
| — controversy-linked (prior 12m) | −0.0357 | 189 | −0.0130 (−0.8) |
| — not controversy-linked | +0.0218 | 3,980 | +0.0272 (+0.7) |

---
## 3. FIGURES
### FIGURE 1 — MSCI rating architecture  [§2]  schematic (no estimation). File `fig1_architecture.png` (built by `02_figures.py`).
### FIGURE 2 — Month-by-month incorporation  [§6.5]
Event = severe onset (dated to month); forward ASOF to next downgrade month; censor at 2026m7; KM-style hazard h_m=fail_m/atrisk_m; cumulative 1−Π(1−h_m), m=1..24; early (2018–19) vs late (2021–25). Anchors: cumulative incidence @24m **early 47% / late 70%**; events early 2,665, late 4,994; cloglog Late coef **0.431 (z 12.6)**, **HR 1.54**. File `fig2_monthly.png`; series `tab_monthly.csv`.

---
## 4. APPENDIX TABLES
### A1 Variable definitions [App. A] — see §0–§1.
### A3 Month-by-month incidence/hazard (selected months 1,3,6,12,24) [App. B] — from Figure 2 series (`tab_monthly.csv`).
### A4 Downgrade-horizon test [App. C]  (P2)
Model: Downgrade_{i,m→m+H} = φ_i + δ·SustLow_im + θ·IAS_im + ε; SustLow = moderate onsets in ≥2 of prior 6 months; firm FE; SE clustered by firm.
Values: H=12m δ=**−0.009 (−5.8)**; H=24m δ=**−0.023 (−12.7)**.

---
## 5. OTHER NARRATIVE STATISTICS (none omitted)
- **§6.1:** median gap between IAS obs = **10 months** (mean 10.1); zero severe-count-change share = **97.6%** (≈98%); unconditional R²(ΔIAS~Δsevere) **<0.001**.
- **§6.4 pass-through:** good b⁺=**1.41** (142.5); bad b⁻=**1.16** (50.6); H0 b⁺=b⁻ rejected **p<0.001** (year FE; firm-clustered).
- **§6.6 lead:** median **6** months (mean 10.1; %≥6m **52%**; n=13,338).
- **§6.6 reclassification:** at severe onset same-issue moderate falls **56%** / unchanged **25%** / rises **19%** (n=22,438).
- **§6.6 cross-issue:** same-issue **+0.0155 (40.3)** vs different-issue **+0.00013 (6.2)** (firm FE).
- **§3.3 literature:** Berg et al. (2026): implemented downgrades predict **−2.8%**/12m; suppressed none (cited only).

## 6. INFERENCE & CONVENTIONS
SE clustered by firm (ISSUERID) throughout. Large-panel FE by within-transform; adjusted R² only where dummy OLS feasible. Forward returns winsorised 1/99. Band = 10/7 ≈ 1.4286. t in parentheses. 2020 reported separately. Single July-2026 vintage throughout.


## Bitemporal valid-time construction & ultimate-parent clustering (v26)

Controversy severity counts are built on a **valid-time** basis: for a year-end snapshot at Dec 31 of year *t*, a controversy field contributes only if `START_DATE <= Dec31(t) <= END_DATE`. The earlier construction used the latest `START_DATE <= Dec31(t)` and summed co-dated fields before the as-of, which (a) carried expired records forward and (b) dropped issues last updated on an earlier date — jointly mis-measuring the per-severity counts, most visibly around the **2020-08-28 methodology reissue** (~500k severe records expire on that date). The IAS outcome and `TOTAL_NUMBER_CONTROVERSIES` chain continuously and are unaffected.

Standard errors are clustered by `PARENT_ULTIMATE_ISSUERID`: MSCI maps ratings to subsidiaries, so the 76,487 rated identifiers correspond to 29,119 ultimate-parent groups; a parents-only sample (140,474 firm-years) is the robustness column. The **binding** treatment counts Key Issues by their single highest-severity controversy (MSCI's single-highest-deduction rule). `pipeline/02` implements all three and reproduces Tables 1-3, A2 and the binding estimates in the paper (v26).


## v27 wording correction (no numbers affected)
§2 now states MSCI's controversy framework assigns a severity of **minor, moderate, severe, or very severe**, but the data feed reports counts only at the moderate, severe, and very severe levels (plus a total); there is no separately reported minor count, so the low-severity **minor/residual = Total − Moderate − Severe − Very Severe** (unchanged). This corrects an earlier phrasing that implied only three severity levels. No tables, tests, or sample counts change.

## Sample screen, clustering of memo results, and first covered years (v31 to v33)

**Canonical sample.** `pipeline/02` reads `INDUSTRY_ADJUSTED_SCORE` records with `START_DATE >= 20150101`. A firm-year enters only if the IAS in effect at Dec 31 of both t and t−1 has an effective date in 2015 or later; this removes 12,290 firm-years (3,205 in 2018, 2,983 in 2019, about 1,200 per later year) whose score was last updated before 2015. Without the filter the panel has 414,175 firm-years (the supervisor memo's sample). The filter, not clustering, produces 401,885: `group = PARENT_ULTIMATE_ISSUERID` with own `ISSUERID` as fallback, so clustering drops nothing; the excluded firm-years are 13% subsidiaries against 65% in the kept sample. IAS values are identical in the May-2026 and July-2026 extracts for 2017 to 2025.

**Memo results.** The memo's analyses (severity x Late; onset-type ΔIAS; letter-threshold logit) clustered by `ISSUERID`. Re-clustered by ultimate parent: very severe x Late −0.279 (t = −3.0 to −2.2) on 414,175 and −0.267 (t = −2.1) on the canonical sample with the 02 construction; onset-type reclassification difference +0.212 (t = 4.8 to 2.2); threshold logit severe x distance −0.79 (z = −5.2 to −1.7), distance −0.85 (z = −18), severe +2.03 (z = 5), moderate +1.51 (z = 10).

**First covered year.** Key-issue severity fields (`<ISSUE>_MODERATE/SEVERE/VERY_SEVERE_CONTROVERSIES`) first appear in 2019 for 63,281 issuers (2,162 earlier); `TOTAL_NUMBER_CONTROVERSIES` first appears in 2017 for 12,568, 2018 for 2,964 and 2019 for 49,260 issuers. Because 02 zero-fills missing counts, a firm-year whose year equals the first START_DATE year of either family records the firm's stock as a change. Flag `first = (yr == first severity year) | (yr == first total year)`; 14,389 canonical firm-years (13,841 in 2019).

| Check (parent-clustered) | All | Without first covered years |
|---|---|---|
| Table 2 t0: moderate / severe / very severe | −0.0118 (−4.4) / −0.0581 (−4.2) / −0.2997 (−3.4) | −0.0091 (−2.5) / −0.0551 (−3.5) / −0.3022 (−3.3) |
| Table 2 t0 residual | −0.0034 (−1.1) | −0.0114 (−3.8) |
| Table 3 early agg t0 / t+1 | +0.0057 (1.6) / −0.0047 (−1.9) | −0.0062 (−0.9) / −0.0032 (−0.4) |
| Table 3 late agg t0 | −0.0147 (−5.2) | −0.0149 (−5.3) |
| Table 3 early severe t0 / t+1 | −0.0715 (−2.5) / +0.0937 (2.2) | −0.0729 (−2.0) / +0.0283 (1.1) |
| Severity x Late, very severe interaction | −0.2665 (−2.1) | −0.2534 (−1.8) |
| Severity x Late, severe interaction | −0.0205 (−0.6) | +0.0360 (0.7) |

**Early-window lag (aggregate count).** Requiring TOTAL in both t and t−1 (the original 28,100-firm-year design; 28,027 here): agg t0 0.000 (0.0), t+1 −0.0093 (−2.0). Excluding also firm-years in which the severity fields begin (15,342): t+1 −0.0035 (−0.5). The residual's early t+1 coefficient (−0.0164, t = −3.9) is mechanical (the severity component starts in 2019) and is not used.

**Section 6.5.** Severe events from `CONTR_*_N_SEVERE` increases (first record excluded by the LAG). 2,267 of 2,665 early events fall within 12 months of the firm's first record. Two-year cumulative probability of a downward IAS revision: 47% early vs 70% late (cloglog late coefficient 0.431, z = 2.4, HR 1.54, parent-clustered); excluding events within 12 months of the first record: 61% (398 events) vs 70%, coefficient 0.13 (z = 1.4), HR 1.14.

**Section 6.5 hazard (v35).** Re-estimated with the 04/05 event construction and ultimate-parent clustering (Aug-2026 issuer reference): late-window coefficient 0.431 (z = 2.4; z = 11.4 clustered by firm; 12.6 unclustered), hazard ratio 1.54, 2,665 early and 4,994 late events. The earlier reported 0.37 (z = 2.1) is not reproduced by any script in this package and is replaced. Table A3 (2.4/12.5/28.1/43.9/46.9% early; 3.7/10.0/20.6/45.6/70.0% late) is reproduced exactly.

**Appendix A4 and cross-issue (v35).** `06` with ultimate-parent clustering: downgrade within 12 months −0.0091 (t = −2.2), within 24 months −0.0232 (t = −5.1); cross-issue LPM same-issue +0.01549 (t = 7.1), different-issue +0.00013 (t = 1.4). The earlier firm-clustered t-statistics (−5.8/−12.7 and 40.3/6.2) are superseded.

---

## v36 — full pipeline assembled
Every test and robustness move behind `Information_transmission_EZGM_v3.docx` is now scripted in this
package. New folders: `consequences/` (Section 7 real effects — index-vs-other ESG fund flows Table 10,
abnormal volume/liquidity Table 11, ownership linkage, logging lag), `robustness/` (backfill/floor
re-estimation a2, distance-to-threshold LPM + letter-category bunching a3, methodology-implied ΔWAKIS a5,
section-number/summary rebuild a6), `external_clock/` (718-term keyword dictionary K0, frozen run_meta,
automated dated clock, placebo K3, funnel/representativeness/reweighted lag A4, hand-check inputs,
a4_clock_sample.py, 09_external_clock.py), and `audit/` (hand-verified lag lag_v3.py + L*/K*/V1v3 outputs
and LOG_v3). See `README.md` section 4 for the exhibit→script map and `docs/EXTERNAL_CLOCK.md` for the
as-run keyword method. The two clocks (automated keyword, median ≈135d; hand-verified 223, the reported
lag) are kept in separate folders and must not be combined.


---

## v37 — Section 4 descriptive facts verified (robustness/verify_data_facts.py)
The manuscript's Section 4 data claims are reproduced by `robustness/verify_data_facts.py` against the
July-2026 extract. (a) Within-2020 re-issue: 748,944 key-issue severity records (50,158 issuers) closed on
2020-08-28 (effective-axis END_DATE), 134,326 (14,299 issuers) opened on 2020-11-10 (START_DATE). (b) Records
in force fell from 910,230 (62,816 issuers) at end-2019 to 325,560 (15,347) at end-2020, so end-2020 counts
are not comparable with end-2019; change-year 2020 is excluded from the baseline and kept only as the Table 3
'Including change-year 2020' robustness row (moderate/severe collapse to -0.001/-0.009). (c) Coverage-start
backfill: 920,424 severity records (62,716 issuers) effective-dated 2019-07-01. (d) Table 1 WAKIS N: a few
firm-years carry a published IAS with no WAKIS in force at year-end (e.g. 5 firms in 2022), so WAKIS is
reported for 401,872 firm-years and ΔWAKIS, needing WAKIS in both adjacent years, for 401,835; all other
variables use 401,885.


---

## v39 — E/S/G pillar split and the forward/backward tests (pillar_forward_backward/)
Table 8 (pillar incorporation): key-issue codes mapped to pillars (E=7 issues, S=14, G=3 Business-Ethics sub-issues); binding count per pillar (single-highest-deduction within pillar); dias on the three pillar binding counts jointly, year FE, parent-clustered, 2018-2025 excl. 2020, N=401,885 (387,496 excl. first-covered). Severe: E -0.117(-1.5), S -0.073(-2.7), G -0.128(-2.4). Very-severe: S -0.373(-4.9) dominant. Forward-looking test: firm pillar SCORE[t] (valid-time as-of year-end) -> severe-in-pillar[t+1], LPM with contemporaneous controversy control + year FE, firm-clustered; score coefs +0.0004(E,wrong sign), -0.0003(S,ns), -0.0013(G,t=-11.6 but tiny); persistence 0.42-0.74. Ownership weight: mandate_ownership_quarterly.csv; ESG-named 0.21% of shares (mean), index-tracking ESG 0.03%.


## v40 — does the rating predict the future (Table 13)
Parent-level: year-end IAS (parent-year mean) linked by PARENT_ULTIMATE_ISSUERID to kit returns (market-adjusted monthly ra; forward 12m from December) and to Compustat (oibdp/at, next year). Year FE, parent-clustered. Returns: +0.004/SD (t=0.3). ROA[t+1] on IAS[t] + current ROA: +0.0024/SD (t=4.0), persistence 0.74 (t=28).
