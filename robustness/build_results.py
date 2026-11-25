#!/usr/bin/env python3
"""Results note for the five requested analyses (Word, Times New Roman 12, black)."""
import numpy as np, pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

O = "/home/claude/w2/out"
doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12); st.font.color.rgb = RGBColor(0, 0, 0)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2); s.top_margin = s.bottom_margin = Cm(2.0)


def para(t, b=False, i=False, sz=12, al=None, after=6):
    p = doc.add_paragraph(); r = p.add_run(t); r.bold = b; r.italic = i; r.font.size = Pt(sz); r.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_after = Pt(after)
    if al == "c": p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if al == "j": p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def head(t):
    p = para(t, b=True, sz=13, after=4); p.paragraph_format.space_before = Pt(12)


def border(cell, edges):
    tcPr = cell._tc.get_or_add_tcPr(); b = OxmlElement("w:tcBorders")
    for e in edges:
        el = OxmlElement(f"w:{e}"); el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "8"); el.set(qn("w:color"), "000000"); b.append(el)
    tcPr.append(b)


def table(rows, widths, header_rows=1, sz=9.5, bold_rows=()):
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.autofit = False
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.width = Cm(widths[j]); c.text = ""
            p = c.paragraphs[0]; r = p.add_run(str(v)); r.font.size = Pt(sz); r.font.color.rgb = RGBColor(0, 0, 0)
            r.bold = (i < header_rows) or (i in bold_rows)
            p.paragraph_format.space_after = Pt(0)
            if j > 0: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            edges = []
            if i == 0: edges.append("top")
            if i == header_rows - 1: edges.append("bottom")
            if i == len(rows) - 1: edges.append("bottom")
            if edges: border(c, edges)
    return t


def note(t):
    p = para(t, sz=10, after=4, al="j"); p.paragraph_format.space_before = Pt(4)


def f(b, t, d=3):
    return "" if pd.isna(b) else f"{b:+.{d}f} ({t:.2f})".replace("-", "−")


def n0(x):
    return f"{int(x):,}"


para("Additional analyses requested on 31 October 2026", b=True, sz=15, al="c")
para("Results only; the draft has not been edited. Each table is followed by a three-line note.", i=True, al="c", after=10)

# ======================================================================= 1
A1 = pd.read_csv(f"{O}/A1_ownership_linked.csv")
FL = {"all": "All ESG-named funds", "idx": "MSCI-ESG index funds", "oth": "Other ESG-named funds"}
head("1. Holdings response to controversy-linked versus other downgrades")
for key, a, bnm, title in [("Def. 1", "dg_link1", "dg_not1", "Panel A. Linked = severe or very severe controversy logged by MSCI in the 12 months before the downgrade"),
                           ("Def. 2", "dg_link2", "dg_not2", "Panel B. Linked = as in Panel A, and the linked key issue's score fell between the onset and the downgrade")]:
    para(title, i=True, sz=10.5, after=2)
    rows = [["Funds", "h", "Linked downgrade (b₁)", "Other downgrade (b₂)", "b₁ − b₂", "Upgrade", "Mean level", "N / clusters", "Linked events"]]
    for fd in ["all", "idx", "oth"]:
        for h in (1, 2, 4):
            r = A1[(A1.spec.str.startswith(key)) & (A1.funds == fd) & (A1.h == h)].iloc[0]
            rows.append([FL[fd] if h == 1 else "", f"q+{h}", f(r[a], r[a + "_t"], 4), f(r[bnm], r[bnm + "_t"], 4),
                         f(r["diff"], r["diff_t"], 4), f(r.upgrade, r.upgrade_t, 4), f"{r.mean_level:.3f}%",
                         f"{n0(r.N)} / {n0(r.clusters)}", n0(r[a + "_n"])])
    table(rows, [3.3, 0.9, 2.6, 2.6, 2.0, 2.2, 1.5, 2.3, 1.4])
para("Panel C. Ownership change around controversy dates with no rating change in quarters q to q+4", i=True, sz=10.5, after=2).paragraph_format.space_before = Pt(8)
rows = [["Funds", "h", "MSCI logging date (severe/very severe)", "Events", "Public-report date (hand-checked, US)", "Events", "N / clusters"]]
for fd in ["all", "idx", "oth"]:
    for h in (1, 2, 4):
        c = A1[(A1.spec.str.startswith("MSCI logging")) & (A1.funds == fd) & (A1.h == h)].iloc[0]
        p = A1[(A1.spec.str.contains("public-report date, no rating")) & (A1.funds == fd) & (A1.h == h)].iloc[0]
        rows.append([FL[fd] if h == 1 else "", f"q+{h}", f(c.contro_nochg, c.contro_nochg_t, 4), n0(c.contro_nochg_n),
                     f(p.public_nochg, p.public_nochg_t, 4), n0(p.public_nochg_n), f"{n0(c.N)} / {n0(c.clusters)}"])
table(rows, [3.3, 0.9, 3.6, 1.4, 3.6, 1.4, 2.6])
note("Table R1. Change in ESG-mandated ownership (percentage points of market capitalisation) from quarter q−1 to q+h, US-listed "
     "shares, quarters from 2018Q1; quarter fixed effects; Compustat controls (log assets, leverage, ROA, log book-to-market); "
     "t-statistics clustered by firm (ultimate parent, one CRSP security per parent). Downgrades and upgrades are letter-band changes as "
     "in Table 10, which this code reproduces for the full period (q+4: −0.0201, t = −4.48). Onsets dated 2019-07-01 or 2017-08-31 are "
     "excluded. Panel C regressions also include downgrade and upgrade indicators. Linked events: firm-quarters with a linked "
     "downgrade and an observed ownership change.")
para("What it shows. (1) Downgrades that follow a severe controversy reduce ESG ownership as much as other downgrades: b₁ is "
     "negative and significant for all ESG-named funds (−0.026 to −0.034) and for MSCI-index funds at every horizon, and b₁ = b₂ is "
     "never rejected (p > 0.4). (2) MSCI-index funds do not move when a controversy is logged without a rating change "
     "(−0.001, t = −0.9 at q+1; −0.004, t = −1.9 at q+4), nor at the public report (n = 45, not significant). (3) Other ESG-named "
     "funds do drift down over four quarters after a logged controversy without a rating change (−0.013, t = −1.9; all funds −0.018, "
     "t = −2.3), so part of the discretionary ESG money responds to the controversy itself, not only to the rating.",
     sz=11, al="j")

# ======================================================================= 2
A2 = pd.read_csv(f"{O}/A2_table2_backfill.csv"); ov = pd.read_csv(f"{O}/A2_overlap.csv", index_col=0).iloc[:, 0]
head("2. Table 2 without backfilled and floored onsets")
S = ["Table 2 (all)", "Excl. backfill/floor onsets", "Excl. both"]
rows = [["Severity level", "Table 2: t", "Table 2: t+1", "Excl. backfill/floor: t", "Excl. backfill/floor: t+1",
         "Excl. backfill/floor and first covered year: t", "… : t+1"]]
for lv in ["Other (residual)", "Moderate", "Severe", "Very severe"]:
    rr = [lv]
    for s in S:
        x = A2[(A2["sample"] == s) & (A2.level == lv)].iloc[0]
        rr += [f(x.b_t, x.t_t, 4), f(x.b_t1, x.t_t1, 4)]
    rows.append(rr)
nrow = ["N (firm-years)"]; grow = ["N (ultimate-parent clusters)"]
for s in S:
    x = A2[A2["sample"] == s].iloc[0]; nrow += [n0(x.N_t), n0(x.N_t1)]; grow += [n0(x.G_t), n0(x.G_t1)]
rows += [nrow, grow]
table(rows, [3.2, 2.1, 2.1, 2.3, 2.3, 2.6, 2.1])
note(f"Table R2. OLS of ΔIAS (t) and ΔIAS (t+1) on the change in the count at each severity level, one level per regression as in "
     f"Table 2; paper sample (401,885 firm-years, IAS records from 2015); year fixed effects; standard errors clustered by ultimate "
     f"parent; t-statistics in brackets. Backfill/floor firm-years: issuer-years with a positive key-issue severity record starting on "
     f"2019-07-01 or 2017-08-31 ({n0(ov['backfill_any'])} firm-years, all in 2019, of which {n0(ov['backfill_with_change'])} have a "
     f"severity change; no 2017-08-31 record falls in a sample change-year). Overlap with the first-covered-year flag "
     f"(14,389 firm-years): {n0(ov['both'])} firm-years are in both, {n0(ov['backfill_not_first'])} only in the backfill flag, "
     f"{n0(ov['first_not_backfill'])} only in the first-covered flag; union {n0(ov['union'])}.")
para("What it shows. Dropping the 4,746 backfill firm-years (1.2% of the sample) leaves the moderate (−0.010, t = −2.7), severe "
     "(−0.054, t = −3.3) and very severe (−0.324, t = −3.6) contemporaneous coefficients essentially unchanged. The residual moves "
     "from a one-year-later effect (−0.006, t = −3.3) to a same-year effect (−0.010, t = −3.0; t+1 −0.003, t = −1.6), so the residual's "
     "lag in Table 2 comes from the 2019 backfill. The backfill flag and the first-covered-year flag mostly identify the same firm-years "
     "(3,927 of 4,746), and dropping both gives the same picture.", sz=11, al="j")

# ======================================================================= 3
A3 = pd.read_csv(f"{O}/A3_threshold_lpm.csv"); te = pd.read_csv(f"{O}/A3_tests.csv")
head("3. Distance to the letter threshold")
bins = ["<0.3", "0.3-0.6", "0.6-1.0", "1.0-1.43"]
rows = [["Controversy at t", "Very near (< 0.3)", "Near (0.3–0.6)", "Mid (0.6–1.0)", "Far (1.0–1.43)"]]
for s in ["none", "moderate", "severe", "very severe"]:
    rr = [s.capitalize() + (" †" if s == "very severe" else "")]
    for bn in bins:
        x = A3[(A3.severity == s) & (A3.bin == bn)].iloc[0]
        coef = "ref." if (s == "none" and bn == "1.0-1.43") else f(x.coef_pp / 100 * 100, x.t, 1).replace("(", "(t = ").replace(")", ")")
        rr.append(f"{coef}\n{x.raw_pct:.1f}% [{n0(x.N)}]")
    rows.append(rr)
get = lambda k: te[te.test == k].iloc[0]
rows.append(["Severe − none", f(get('severe minus none, <0.3').pp, get('severe minus none, <0.3').t, 1), "", "",
             f(get('severe minus none, 1.0-1.43').pp, get('severe minus none, 1.0-1.43').t, 1)])
rows.append(["Moderate − none", f(get('moderate minus none, <0.3').pp, get('moderate minus none, <0.3').t, 1), "", "",
             f(get('moderate minus none, 1.0-1.43').pp, get('moderate minus none, 1.0-1.43').t, 1)])
table(rows, [3.4, 3.2, 3.2, 3.2, 3.2], bold_rows=())
note("Table R3. Linear probability model of a letter downgrade by the next year-end (percentage points), on 16 distance-bin × "
     "severity cells (reference: no new controversy, far from the threshold) with year fixed effects; standard errors clustered by "
     "ultimate parent (432,677 firm-years, 28,061 clusters; firm-years 2018–2025 excl. 2020 with IAS records from 2015; CCC "
     "firm-years, which cannot be downgraded, excluded). Each cell: coefficient (t), then the raw downgrade rate [N]. Distance is the "
     "IAS minus the lower edge of its letter band (band width 1.43). Severity is the highest new key-issue onset in year t. "
     "Bottom rows: severe (moderate) minus none within the very-near and far bins. † Very severe cells are thin (47–65 firm-years) "
     "and not interpreted; the very-near very severe cell has no downgrades.")
para("What it shows. A severe controversy raises the probability of a downgrade within a year by about 20 points when the firm is "
     "within 0.3 of the threshold (t = 2.3) and by about 3 points when it is far (t = 2.7); the near-minus-far difference is 17 points "
     "(t = 2.0). Moderate controversies show the same pattern more precisely (12 against 3 points; difference 8.5, t = 3.8). The "
     "letter-stage attenuation result therefore holds in the LPM with parent clustering.", sz=11, al="j")
doc.add_picture(f"{O}/A3_bunching.png", width=Cm(16.5))
note("Figure R3. Distribution of year-end IAS around each letter cut-off (k × 10/7), firm-years 2018–2025 excl. 2020, IAS records from "
     "2015; 99.5% of year-end IAS values lie on the one-decimal grid, so bars are 0.1 wide; grey = below the cut-off (lower letter), "
     "blue = above. Counts are in A3_bunching_counts.csv.")
para("What it shows. The distribution is not smooth at the cut-offs. Mass piles up just above the CCC/B and B/BB cut-offs "
     "(2.9: 9,288 against 3,814 at 2.8) and just below the BB/BBB, BBB/A, A/AA and AA/AAA cut-offs (7.1: 16,801 against 2,749 at 7.2; "
     "4.2: 12,037 against 4,583 at 4.3). This is consistent with discretion at the thresholds of the kind Berg, Cornaggia, Foroni and "
     "Tripoli (2026) study, but on a 0.1 grid it is descriptive; whether the pattern matches the direction they report should be "
     "checked against their paper before it is cited.", sz=11, al="j")

# ======================================================================= 4
head("4. The hand-checked clock sample")
F4 = pd.read_csv(f"{O}/A4_funnel.csv")
rows = [["Stage", "N", "Dropped", "Reason for the drop"]] + [[r["stage"], n0(r["N"]), n0(r["dropped"]), r["reason for drop"]] for _, r in F4.iterrows()]
table(rows, [5.4, 1.4, 1.4, 8.4], sz=9)
note("Table R4a. Funnel from all US and UK onsets to the 223 verified controversies. The first-round rule that selected 670 of "
     "the 2,399 matched onsets is not recorded in the audit files; 638 of the 670 have a matched article dated 0–90 days before the "
     "MSCI date. 'Screen only' rows have a headline judged correct but no verified earliest report.")
R4 = pd.read_csv(f"{O}/A4_representativeness.csv")
rows = [["Variable", "Category", "Verified 223 (%)", "Other onsets (%)", "Test"]]
last = None
for r in R4.itertuples():
    rows.append([r.variable if r.variable != last else "", r.category,
                 f"{r.verified_pct:.1f}" if r.variable != "Onsets" else n0(r.verified_pct),
                 f"{r.other_pct:.1f}" if r.variable != "Onsets" else n0(r.other_pct), r.test])
    last = r.variable
table(rows, [4.0, 4.2, 2.6, 2.6, 3.0], sz=9)
note("Table R4b. The 223 verified controversies against the other 13,984 US/UK onsets. Sector from MSCI's parent file (GICS sector; "
     "'missing' where not recorded); log total assets from Compustat, available for 177 verified and 7,916 other onsets. Chi-square "
     "tests for categories, Welch t-test for log assets.")
RW = pd.read_csv(f"{O}/A4_reweighted_lag.csv"); MX = pd.read_csv(f"{O}/A4_severity_mix.csv", index_col=0)
rows = [["Weighting", "Median", "Mean", "P25–P75", "≤ 90 days"]] + [[r.weighting, f"{r.median:.0f}", f"{r.mean:.0f}", f"{r.p25:.0f}–{r.p75:.0f}", f"{r.le90:.0f}%"] for r in RW.itertuples()]
table(rows, [8.0, 1.8, 1.8, 2.4, 2.2])
note(f"Table R4c. Logging lag in days. Weights equal each severity's share among the 14,207 onsets divided by its share among the "
     f"223: moderate {MX.loc['moderate','share_all_onsets']*100:.1f}% vs {MX.loc['moderate','share_verified']*100:.1f}% (weight "
     f"{MX.loc['moderate','weight']:.2f}), severe {MX.loc['severe','share_all_onsets']*100:.1f}% vs {MX.loc['severe','share_verified']*100:.1f}% "
     f"({MX.loc['severe','weight']:.2f}), very severe {MX.loc['very_severe','share_all_onsets']*100:.1f}% vs "
     f"{MX.loc['very_severe','share_verified']*100:.1f}% ({MX.loc['very_severe','weight']:.2f}).")
para("What it shows. The verified sample is not representative: it over-weights very severe cases (25% against 1.5%), 2021–2025, "
     "Energy and Financials, and much larger firms (log assets 12.3 against 10.9). Reweighting to the population severity mix leaves "
     "the median lag at 80 days and lowers the mean from 108 to 104 days, so the 80-day headline does not come from the severity "
     "over-weighting; the size and sector differences cannot be reweighted away and should be stated as a scope limit.", sz=11, al="j")
para("Audit protocol (draft appendix paragraph, to be checked against how the audit was actually done).", b=True, sz=11)
para("For each controversy, the auditor identified the firm-specific incident that MSCI most plausibly logged under the stated key "
     "issue, searching the period up to about one year before the MSCI date (and up to seven days after it). Sources were searched in "
     "order of priority: primary documents (regulator and enforcement releases such as DOJ, SEC, FTC, CFPB, OCC, EPA, OSHA, FCA, CMA, "
     "SFO and ICO; court filings; company filings and RNS announcements), then the first news report, using GDELT-matched articles, "
     "Google News and NGO trackers as leads. The earliest public report is the earliest dated, publicly accessible document that names "
     "the firm and describes the incident; later coverage, opinion pieces and generic sector stories do not qualify. Each verified "
     "row records the date, a source link and a confidence grade (high, medium or low); rows whose incident could not be identified, "
     "or whose earliest date could not be confirmed, are classed as unresolved or screen-only and excluded from the lag sample.",
     sz=11, al="j")
para("Two points before this paragraph goes into the draft. First, the audit file's 'Checked by' field records 'Claude research "
     "audit' for all 727 rows (and 'Claude (web audit)' or 'Claude (headline screen)' in the matched file), while the draft calls the "
     "clock hand-audited; the paper should state who dated the cases and how AI-assisted searches were checked. Second, I cannot "
     "act as the independent second coder. A random draw of 30 of the 223 (seed 20261031) is in A4_second_coder_30.xlsx, with the "
     "first coder's dates on a separate sheet to keep hidden; agreement within 7 days can be computed once a second person fills it in.",
     sz=11, al="j")

# ======================================================================= 5
A5 = pd.read_csv(f"{O}/A5_implied.csv")
head("5. Methodology-implied effect (robustness)")
rows = [["Sample", "Slope on implied ΔWAKIS: observed ΔWAKIS", "Slope: observed ΔIAS", "Mean implied ΔWAKIS", "N / clusters"]]
lab = {0: "All firm-years (implied = 0 if no change)", 1: "Firm-years with a weighted key-issue severity change",
       2: "  with a net implied decline (new or escalated cases)", 3: "  with a single changed key issue"}
for i, r in A5.iterrows():
    rows.append([lab[i], f(r.slope_dWAKIS, r.t_dWAKIS, 3), f(r.slope_dIAS, r.t_dIAS, 3), f"{r.mean_implied:+.3f}".replace("-", "−"), f"{n0(r.N)} / {n0(r.clusters)}"])
table(rows, [5.8, 3.3, 2.8, 2.4, 2.4])
note("Table R5. OLS of the observed change in WAKIS (and IAS) on the implied change Σₖ wₖ·Δdeductionₖ; year fixed effects; standard "
     "errors clustered by ultimate parent; paper sample without first covered years. Deductions are the midpoints of MSCI's "
     "non-structural/structural ranges for the highest severity in the key issue (moderate 1.05, severe 2.1, very severe 4.0 points), "
     "as summarised from the controversy-deduction exhibit of MSCI's ESG Ratings Methodology (edition to be confirmed); weights are the "
     "key-issue weights in force at year-end; business-ethics issues, which enter through governance Key Metrics, are excluded.")
para("What it shows. Where the implied score falls because of new or escalated cases, about 30% of the implied deduction appears "
     "in WAKIS (slope 0.30, t = 3.9) and almost none survives to the IAS (0.13, t = 0.7). The approximation assumes: the deduction "
     "lands one-for-one on the key-issue score (no floor at zero, no censoring of the management score), the midpoint is the right "
     "deduction (structural status is unobserved), the highest-severity case binds, nothing else in the issue changes in the same "
     "year, and no Company-Specific Key Issue is added. Each assumption biases the slope towards zero, so read 0.30 as a lower bound.",
     sz=11, al="j")
doc.save(f"{O}/Additional_Analyses_Results.docx"); print("saved")
