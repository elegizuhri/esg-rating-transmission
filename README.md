# Information Transmission in ESG Ratings — Replication

Replication code for *Information Transmission in ESG Ratings: Evidence from MSCI Controversies* (Zuhri & Michelon).

The whole pipeline — data acquisition, cleaning, variable construction, and every table, figure, and result — runs from one Google Colab notebook.

📄 **Paper:** [not yet available - will be updated soon]

This repository contains **code only** — not the manuscript. The paper is distributed separately at the link above.

## ▶️ Run it in Google Colab (one click)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/elegizuhri/esg-rating-transmission/blob/main/pipeline_colab.ipynb)

> `https://colab.research.google.com/github/elegizuhri/esg-rating-transmission/blob/main/pipeline_colab.ipynb`

Or, in Colab: **File → Open notebook → GitHub tab → paste the repo URL → open `pipeline_colab.ipynb`**.

## What's inside

| Path | What it is |
|---|---|
| `pipeline_colab.ipynb` | **Start here.** The full annotated pipeline, Section 0 → 4, every code cell commented. |
| `replication/` | The individual analysis scripts the notebook embeds (run directly via `replication/pipeline/run_all.sh` if you prefer). |
| `replication/docs/CONSTRUCTION_DOCUMENTATION.md` | Variable dictionary and the exact expected value for every table. |
| `replication/F1_daily_CAR_61_125.py` | Daily market-adjusted CAR (before/after windows) — the §7.2 reconciliation, on the same benchmark as Appendix H (needs the CRSP daily file). |
| `requirements.txt` | Python dependencies (the notebook installs these for you in Colab). |

## How the notebook is organised

0. **Setup** — install packages, mount Drive, set paths and credentials.
1. **Data acquisition** — raw MSCI, GDELT 2.0, WRDS (CRSP / Compustat / MF-holdings), Refinitiv/LSEG.
2. **Cleaning & matching** — point-in-time rule, ISIN↔ISSUERID and ultimate-parent keys, winsorisation.
3. **Variable construction** — the firm-year, monthly, issue-level, pricing and event-study panels.
4. **Tests, tables & figures** — every manuscript exhibit, each cell mapped to its table/figure.

## ⚠️ Data access

The four raw sources (MSCI ESG, GDELT, WRDS, Refinitiv/LSEG) are **licensed**. This repo contains **code only** — no raw data. Put the licensed files in your own Google Drive (Section 0 of the notebook shows the expected filenames) and supply your own WRDS login and Refinitiv app key. The `.gitignore` is set up to keep data and credentials out of the repository. Sections 2–4 run entirely on the files the Section 1 cells produce.

## Citation

If you use this code, please cite the paper. Standard errors are clustered by ultimate parent throughout; the letter-band width is 10/7 ≈ 1.4286 IAS points; 2020 is reported separately.
