# External clock — as-run GDELT keyword method

This documents the pipeline actually run to build the external "clock" that dates when each MSCI
controversy first became public, independently of MSCI's own record date. It supersedes the earlier
plan in `EXTERNAL_CLOCK_PLAN.md` where they differ.

## Scope and language justification
Only **US and UK** controversy records are used. GDELT indexes global news but English-language matching
is markedly more precise (company-name and key-issue terms disambiguate cleanly; non-English coverage
introduces translation and transliteration noise that inflates false matches). The US is also the single
largest block of the sample, so restricting to US/UK retains the bulk of observations while holding match
quality constant. Extending to other languages is left to future work.

## Retrieval
- Source: **GDELT 2.0 DOC API**, retrieved with a Google Colab notebook.
- Window: from the MSCI controversy record date back to **three years prior** (0 to −3y).
- Match keys: company name(s) **and** key-issue terms, searched in article **title and body**.
- Frozen parameters (`run_meta.json`): GDELT span 2015-09-01 → 2026-10-20; rating vintage 2026-07-31;
  countries `US,GB`; `match_on = body`; `max_fetch = 15` per onset; placebo share 0.3; seed 7;
  onsets_total 14,207; auto-matched 2,399.

## Keyword dictionary (`K0_keyword_dictionary.csv`, 718 terms, 25 key issues)
Columns `key_issue, role, term`. Roles:
- **core** — issue-specific terms (e.g. `oil spill*`, `pollut*` for Toxic Emissions; `union bust*` for Labor Management).
- **regulator** — enforcement bodies (`EPA`, `CFPB`, `NLRB`, `FCA`, `DOJ`, …).
- **event** — generic adverse-event words (`fine*`, `lawsuit*`, `investigat*`, `settlement`, `indict*`).
- **severity_moderate / severity_severe / severity_very_severe** — severity-language cues (`killed`, `explosion`, `indicted`, `billion`, …).
- **exclude_title** — market-noise terms that veto a title match (`price target`, `stock rating`, `dividend`, `52 week`).

## Noise removal and verification
1. Automated matches passed through **Claude AI** to drop paywalled pages and separate real matches from
   false flags (random hits, wrong-firm collisions).
2. **Hand-verified by Elegi Zuhri**: for each retained onset, the incident and the earliest credible public
   report were confirmed and dated (`HAND_CHECK_list.csv`, `HAND_CHECK_300.xlsx`).

## Funnel (`results/A4_funnel.csv`)
14,207 US/UK onsets (excl. 1-Jul-2019 backfill and 31-Aug-2017 floor dates) → 2,399 with ≥1 matched
article → 727 retained after first screening → 239 selected for audit → **223 verified** (one 23-Mar-2026
re-rating dropped).

## Two clocks — do not combine
- **Automated keyword clock** (`keyword_dated_clock.csv`, `results/T2_*`): median implied lag ≈ 135 days
  across the 2,399 auto-matched controversies; deliberately noisy, used only for the placebo and for
  representativeness.
- **Hand-verified clock** (`../audit/`, `lag_v3.py`): the manuscript's reported incorporation lag, computed
  on the 223 verified onsets and reweighted to the severity mix of all 14,207 onsets
  (`results/A4_reweighted_lag.csv`).

## Placebo (`results/K3_placebo_validation.csv`)
Each MSCI date is shifted back one year and re-matched. In a 30% random sample of onsets the share with a
matched article over a one-year window is essentially identical for true and placebo dates (16.7% vs 16.8%);
within 90 days before the date the true rate exceeds the placebo only modestly, by 1.1pp (5.1% vs 3.9%,
t = 2.6) — confirming the match carries real but modest timing signal, consistent with the noisy automated lag.

## Returns robustness (`results/returns_robustness/`)
Pre-registered plan (`R0_preregistered_plan.json`) and event-study/return-treatment robustness
(`R1`–`R5`, BH-adjusted) at the audited dates.
