#!/usr/bin/env bash
# Reproduction driver (v26). Edit DATA paths at the top of each script if needed.
# Run in order. 02 builds the canonical valid-time panel (panel_fy_validtime.parquet);
# 01 and 03 read it, so 02 MUST run first. Steps 04-08 build 6-15M-row monthly/issue/
# event panels (run on >=8GB, or step-by-step on <=2GB).
# Construction: controversy counts are valid-time (START<=Dec31(t)<=END); SE clustered by
# ultimate parent. See docs/CONSTRUCTION_DOCUMENTATION.md and REPRODUCTION_LOG.txt.
set -e
python3 00_figure1_architecture.py           # Figure 1 (schematic)
python3 02_table2_table3_severity.py         # builds panel_fy_validtime.parquet; Table 2, Table 3, Appendix A2
python3 01_table1_table4_revfreq.py          # Table 1, Table 4, §6.1 (reads canonical panel)
python3 03_channel_passthrough.py            # §6.3 channel, §6.4 pass-through (reads canonical panel)
python3 04_figure2_monthly.py                # Figure 2 + tab_monthly.csv (Appendix A3)
python3 05_reclass_lead_hazard.py            # §6.6 reclassification & lead; §6.5 cloglog HR
python3 06_crossissue_downgradehorizon.py    # §6.6 cross-issue; Appendix A4 (parent-clustered)
python3 07_table5_pricing.py                 # Table 5 pricing (parent-clustered)
python3 08_table6_twoevent_and_industryFE.py # Table 5 industry-FE robustness + Table 6 two-event
python3 09_external_clock.py --synthetic     # offline estimator check; use --scrape/--estimate with data
python3 10_robustness_firstcoverage.py      # v33: 2015 screen note, first covered years, early lag, severity x Late, Section 6.5
echo "DONE — compare against REPRODUCTION_LOG.txt"
