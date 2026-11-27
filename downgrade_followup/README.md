# downgrade_followup — month-0 contrast, risk-adjusted paths, and robustness (Appendix H)

Added for the reviewer tests on the post-downgrade drift (v42).

`H3_build_and_run.py` rebuilds the downgrade event-study kit from the raw MSCI + return files and runs:
  - TEST (a): the downgrade-month (month 0) return vs the mean of months -6..-1 and +1..+6, firm-clustered difference t.
  - TEST (b): the balanced -6..+6 event-time path under market-adjusted, momentum-matched, and four-factor (US-listed) returns.
  - ROBUSTNESS: the 6-month forward drift excl. the 2019 backfill / mass re-rating dates / by sub-period, and a past-6m control.
  - Also reports the ultimate-parent-level path (comment 646).

INPUTS (licensed, not shipped): HIST_SUMMARY_SCORES (IVA_COMPANY_RATING, INDUSTRY_ADJUSTED_SCORE),
HIST_MASTER_INSTRUMENT_REFERENCE (ISIN<->ISSUERID), monthly_total_returns.csv (global monthly TR by ISIN),
ff_monthly.parquet. See the header of H3_build_and_run.py for the exact schema and env vars.

`F1_daily_CAR_61_125.py` is the DAILY companion to the above, reconciling Section 7.2 with Appendix H.
It uses the SAME benchmark as Appendix H — **market-adjusted** returns (return minus the CRSP value-
weighted market), winsorised 0.5/99.5 — NOT a firm-beta Carhart model. (An earlier version subtracted a
firm-specific four-factor expectation with no intercept; on this sample that construction turned the
post-event window spuriously positive. It has been replaced; do not reintroduce it.) Inputs: CRSP_DAILY
(permno, date, ret, parent_id), CRSP_MKT (date, vwretd), DG (downgrade_events), and the optional ULT
issuer->ultimate-parent bridge (the CRSP ISSUERID is often the ultimate parent, so without ULT only a
small directly-keyed subsample links).

RESULTS (shipped): results/H4a_month0_contrast.csv, H4b_riskadj_paths.csv, H4c_robustness.csv.

KEY NUMBERS (balanced windows):
  month-0 contrast: -0.32pp (t=-2.07) market-adj full; -0.38pp (t=-1.11) US four-factor; -0.19pp (t=-1.5) ultimate-parent.
  path survives momentum-matching (before -1.5%, after -1.4%) and four-factor on US (before -2.8%, after -2.8%).
  6-month drift -1.55% (market-adj) / -1.37% (momentum-matched); robust to excluding 2019 backfill and re-rating dates.

DAILY reconciliation (F1, market-adjusted, US CRSP): before [-60,-1] -1.01% (t=-3.35); after [+1,+60]
  -0.29% (t=-0.91, "no drift in the first 60 days", Section 7.2); after [+61,+125] -1.14% (t=-3.15) —
  the post-event decline accumulates after day +60, mirroring the pre-event decline (the symmetric drift).
