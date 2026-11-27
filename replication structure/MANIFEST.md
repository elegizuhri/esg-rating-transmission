# MANIFEST — EZ-US replication package v36

Generated listing of every shipped file. Licensed raw data and regenerated caches are **not** shipped (see below).

### `./`
- `README.md` — Master guide: folders, data, reproduce steps, exhibit->script map, changelog  *(11 KB)*

### `audit/`
- `K1v3_KM_external_vs_internal.csv` — result table (CSV)  *(397 B)*
- `K2v3_hazard_external_vs_internal.csv` — result table (CSV)  *(2 KB)*
- `L1v3_lag_descriptive.csv` — result table (CSV)  *(2 KB)*
- `L2v3_lag_regressions.csv` — result table (CSV)  *(7 KB)*
- `L3v3_selection_into_verified.csv` — result table (CSV)  *(333 B)*
- `L4v3_lag_distribution.csv` — result table (CSV)  *(188 B)*
- `LOG_v3.txt` — Hand-audit log  *(12 KB)*
- `V1v3_returns_at_audited_dates.csv` — result table (CSV)  *(2 KB)*
- `lag_v3.py` — Hand-verified lag + audited-date returns (manuscript clock)  *(8 KB)*

### `consequences/`
- `downgrade_drift_eventstudy.py` — event-time CAR around downgrades (Table H3); drift artifact + momentum robustness  *(script)*
- `results/H3_event_time_path.csv`, `results/H3_window_CARs.csv`, `results/H3_drift_robustness.csv`, `results/downgrade_drift_LOG.txt` — its outputs  *(results/log)*
- `a1_ownership_linked.py` — Ownership linkage / revision frequency  *(10 KB)*
- `section8_extra.py` — Abnormal volume & liquidity around downgrades (Table 11)  *(11 KB)*
- `section8_final.py` — Section 7 real effects: fund flows, index vs other ESG  *(19 KB)*

### `consequences/results/`
- `A1_ownership_linked.csv` — result table (CSV)  *(13 KB)*
- `I2_index_vs_other_ESG_funds.csv` — result table (CSV)  *(3 KB)*
- `L1_logging_lag.csv` — result table (CSV)  *(1 KB)*
- `L2_lag_regression.csv` — result table (CSV)  *(2 KB)*
- `V1_abnormal_volume_liquidity.csv` — result table (CSV)  *(11 KB)*

### `docs/`
- `CONSTRUCTION_DOCUMENTATION.md` — Journal-standard record of every exhibit  *(18 KB)*
- `EXTERNAL_CLOCK.md` — As-run GDELT keyword method  *(4 KB)*
- `EXTERNAL_CLOCK_PLAN.md` — Earlier external-clock plan (superseded by EXTERNAL_CLOCK.md)  *(3 KB)*

### `external_clock/`
- `09_external_clock.py` — External-clock estimator (eq.9) scaffold  *(9 KB)*
- `HAND_CHECK_300.xlsx` — Hand-check workbook (300 cases)  *(150 KB)*
- `HAND_CHECK_list.csv` — Hand-check worklist  *(201 KB)*
- `K0_keyword_dictionary.csv` — 718-term keyword dictionary, 25 key issues, 6 roles  *(24 KB)*
- `Keyword_Clock_Results.docx` — Keyword-clock results writeup  *(54 KB)*
- `a4_clock_sample.py` — Funnel, representativeness, severity-reweighted lag, 2nd-coder draw  *(7 KB)*
- `keyword_dated_clock.csv` — Automated per-controversy dated clock  *(1993 KB)*
- `run_meta.json` — Frozen retrieval parameters (US+GB, body, seed 7, funnel counts)  *(749 B)*

### `external_clock/results/`
- `A4_funnel.csv` — result table (CSV)  *(703 B)*
- `A4_representativeness.csv` — result table (CSV)  *(2 KB)*
- `A4_reweighted_lag.csv` — result table (CSV)  *(222 B)*
- `A4_severity_mix.csv` — result table (CSV)  *(244 B)*
- `K1_by_severity.csv` — result table (CSV)  *(559 B)*
- `K2_by_issue.csv` — result table (CSV)  *(3 KB)*
- `K3_placebo_validation.csv` — result table (CSV)  *(2 KB)*
- `K4_severity_language.csv` — result table (CSV)  *(233 B)*
- `K5_link_status.csv` — result table (CSV)  *(436 B)*
- `T2_logging_lag_keyword.csv` — result table (CSV)  *(2 KB)*
- `T2_logging_lag_keyword_severe.csv` — result table (CSV)  *(1 KB)*
- `T2b_lag_late_regression_keyword.csv` — result table (CSV)  *(506 B)*
- `T3_decomposition_keyword.csv` — result table (CSV)  *(933 B)*
- `T4_hazard_eq9_keyword.csv` — result table (CSV)  *(10 KB)*
- `T5_KM_months_to_update_keyword.csv` — result table (CSV)  *(366 B)*
- `T6_acceleration_keyword.csv` — result table (CSV)  *(2 KB)*

### `external_clock/returns_robustness/`
- `R0_preregistered_plan.json` — parameters/metadata  *(620 B)*
- `R1_event_study.csv` — result table (CSV)  *(40 KB)*
- `R2_state_returns.csv` — result table (CSV)  *(13 KB)*
- `R3_downgrade_split.csv` — result table (CSV)  *(15 KB)*
- `R4_robustness_return_treatment.csv` — result table (CSV)  *(13 KB)*
- `R5_all_tests_BH.csv` — result table (CSV)  *(80 KB)*
- `RETURNS_ROBUSTNESS_LOG.txt` — log/notes  *(1 KB)*
- `Returns_Robustness.docx` — Word writeup  *(40 KB)*

### `latex/`
- `equations.tex` — LaTeX source  *(1 KB)*
- `main.pdf` — compiled PDF  *(396 KB)*
- `main.tex` — LaTeX source  *(1 KB)*
- `main_standalone.pdf` — compiled PDF  *(396 KB)*
- `main_standalone.tex` — LaTeX source  *(78 KB)*
- `references.bib` — LaTeX source  *(10 KB)*

### `latex/figures/`
- `fig1_architecture.png` — figure  *(88 KB)*
- `fig2_monthly.png` — figure  *(123 KB)*
- `figures.tex` — LaTeX source  *(1 KB)*

### `latex/sections/`
- `abstract.tex` — LaTeX source  *(3 KB)*
- `appendix.tex` — LaTeX source  *(3 KB)*
- `conclusion.tex` — LaTeX source  *(885 B)*
- `consequences.tex` — LaTeX source  *(9 KB)*
- `data.tex` — LaTeX source  *(4 KB)*
- `discussion.tex` — LaTeX source  *(6 KB)*
- `empirical.tex` — LaTeX source  *(5 KB)*
- `institutional.tex` — LaTeX source  *(2 KB)*
- `intro.tex` — LaTeX source  *(7 KB)*
- `literature.tex` — LaTeX source  *(4 KB)*
- `results.tex` — LaTeX source  *(12 KB)*

### `latex/tables/`
- `tab1.tex` — LaTeX source  *(1 KB)*
- `tab2.tex` — LaTeX source  *(848 B)*
- `tab3.tex` — LaTeX source  *(1 KB)*
- `tab4.tex` — LaTeX source  *(756 B)*
- `tab5.tex` — LaTeX source  *(880 B)*
- `tab6.tex` — LaTeX source  *(935 B)*
- `tabA2.tex` — LaTeX source  *(1 KB)*
- `tabA3.tex` — LaTeX source  *(546 B)*
- `tabA4.tex` — LaTeX source  *(543 B)*

### `log/`
- `REPRODUCTION_LOG.txt` — Every coefficient, t-stat, N in one place  *(13 KB)*

### `pipeline/`
- `00_figure1_architecture.py` — analysis script  *(2 KB)*
- `01_table1_table4_revfreq.py` — analysis script  *(2 KB)*
- `02_table2_table3_severity.py` — analysis script  *(8 KB)*
- `03_channel_passthrough.py` — analysis script  *(1 KB)*
- `04_figure2_monthly.py` — analysis script  *(4 KB)*
- `05_reclass_lead_hazard.py` — analysis script  *(6 KB)*
- `06_crossissue_downgradehorizon.py` — analysis script  *(6 KB)*
- `07_table5_pricing.py` — analysis script  *(5 KB)*
- `08_table6_twoevent_and_industryFE.py` — analysis script  *(7 KB)*
- `09_external_clock.py` — analysis script  *(9 KB)*
- `10_robustness_firstcoverage.py` — analysis script  *(7 KB)*
- `run_all.sh` — Run order for pipeline/ 00-10  *(2 KB)*

### `robustness/`
- `verify_data_facts.py` — reproduces Section 4 facts: 2020 re-issue, end-year in-force collapse, 2019 coverage-start, IAS-vs-WAKIS gap  *(script)*
- `verify_data_facts_LOG.txt` — saved output of the above (verified against the July-2026 extract)  *(log/notes)*
- `a2_table2_backfill.py` — Backfill/floor-date re-estimation of Table 3 timing  *(4 KB)*
- `a3_threshold.py` — Distance-to-threshold LPM + letter-category bunching (Table 7/Fig 2)  *(7 KB)*
- `a5_implied.py` — Methodology-implied delta-WAKIS vs observed (Appendix G)  *(4 KB)*
- `a6_section_numbers.py` — Section-number/summary-stats rebuild (Table 1)  *(4 KB)*
- `build_results.py` — Builds robustness result CSVs  *(19 KB)*

### `robustness/results/`
- `A2_overlap.csv` — result table (CSV)  *(184 B)*
- `A2_table2_backfill.csv` — result table (CSV)  *(2 KB)*
- `A3_bunching_counts.csv` — result table (CSV)  *(772 B)*
- `A3_tests.csv` — result table (CSV)  *(640 B)*
- `A3_threshold_lpm.csv` — result table (CSV)  *(1 KB)*
- `A5_implied.csv` — result table (CSV)  *(775 B)*
- `T1_new.csv` — result table (CSV)  *(731 B)*
- `fig2_bunching_paper.png` — figure  *(100 KB)*

### `stata/`
- `channel_passthrough.do` — Stata do-file  *(821 B)*
- `fig2_monthly.do` — Stata do-file  *(884 B)*
- `master.do` — Stata do-file  *(2 KB)*
- `t1_summary.do` — Stata do-file  *(262 B)*
- `t2_severity.do` — Stata do-file  *(907 B)*
- `t3_earlylate.do` — Stata do-file  *(1 KB)*
- `t3_yearbyyear.do` — Stata do-file  *(487 B)*
- `t4_ownshare.do` — Stata do-file  *(854 B)*
- `t5_pricing.do` — Stata do-file  *(804 B)*
- `t66_reclass_lead_crossissue.do` — Stata do-file  *(1 KB)*
- `t6_twoevent.do` — Stata do-file  *(986 B)*
- `t7_externalclock.do` — Stata do-file  *(1 KB)*

---

## Deliberately excluded (regenerated by the scripts, or licensed)
- `K6_fetched_articles_scored.csv` (~35 MB raw scored GDELT articles) — rebuilt by the retrieval notebook.
- `fetch_cache.sqlite`, `kw_work.duckdb*`, `*.wal` — GDELT fetch caches.
- `K_sample.csv`, `SUBSAMPLE_matched_controversies.csv` — large intermediate match tables.
- MSCI / LSEG / CRSP / Compustat / CRSP-MF raw data — licensed; supply your own (see README section 2).
- `panel_fy_validtime.parquet` and other built panels — rebuilt by `pipeline/02`.
- `docs/paper_main.pdf` (outdated compiled draft) — authoritative manuscript is `Information_transmission_EZGM_v3.docx`.

### `pillar_forward_backward/`
- `score_predicts_returns_fundamentals.py` — does the IAS predict next-12m returns / next-year ROA (Table 13)  *(script)*
- `results/P4_score_predicts.csv` — its output  *(results)*
- `pillar_forward_ownership.py` — E/S/G pillar incorporation (Table 12), forward-looking score test, ownership weight  *(script)*
- `Pillar_forward_ownership_results.xlsx` — all four result tables in one workbook  *(workbook)*
- `results/P1_pillar_incorporation.csv`, `P1_pillar_frequency.csv`, `P2_forward_looking_scores.csv`, `P3_ownership_weight.csv` — outputs  *(results)*
