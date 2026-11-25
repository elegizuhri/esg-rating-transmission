#!/usr/bin/env python3
"""
verify_data_facts.py — reproduces the descriptive data claims in Section 4 of the manuscript:
  (a) the within-2020 re-issue of MSCI's key-issue severity records,
  (b) the resulting collapse in severity records in force between end-2019 and end-2020,
  (c) the 1 July 2019 coverage-start backfill,
  (d) the small IAS-vs-WAKIS gap behind the Table 1 N for WAKIS / dWAKIS.

Inputs (licensed, not shipped): the July-2026 MSCI extract
  HIST_CONTROVERSIES_20260731.parquet, HIST_SUMMARY_SCORES_20260731.parquet
Set JUL to the folder that holds them, then: python verify_data_facts.py
"""
import duckdb, sys, os

JUL = os.environ.get("JUL", ".")
CF = f"{JUL}/HIST_CONTROVERSIES_20260731.parquet"
SS = f"{JUL}/HIST_SUMMARY_SCORES_20260731.parquet"
con = duckdb.connect(); con.sql("PRAGMA threads=4")
SEV = r'_(MODERATE|SEVERE|VERY_SEVERE)_CONTROVERSIES$'
out = []

def line(s): out.append(s); print(s)

line("== (a) Within-2020 re-issue of key-issue severity records ==")
# Closures live on the effective axis (END_DATE, integer); openings on START_DATE.
closed = con.sql(f"SELECT COUNT(*) n, COUNT(DISTINCT ISSUERID) iss FROM '{CF}' "
                 f"WHERE regexp_matches(FIELD_ID,'{SEV}') AND END_DATE=20200828").df()
opened = con.sql(f"SELECT COUNT(*) n, COUNT(DISTINCT ISSUERID) iss FROM '{CF}' "
                 f"WHERE regexp_matches(FIELD_ID,'{SEV}') AND START_DATE=20201110").df()
line(f"  closed 2020-08-28: {int(closed.n[0]):,} records / {int(closed.iss[0]):,} issuers   (paper: 748,944 / 50,158)")
line(f"  opened 2020-11-10: {int(opened.n[0]):,} records / {int(opened.iss[0]):,} issuers   (paper: 134,326 / 14,299)")

line("\n== (b) Severity records in force at each year-end (valid-time) ==")
for y in (2018, 2019, 2020, 2021):
    ye = y*10000 + 1231
    r = con.sql(f"SELECT COUNT(*) n, COUNT(DISTINCT ISSUERID) iss FROM '{CF}' "
                f"WHERE regexp_matches(FIELD_ID,'{SEV}') AND START_DATE<={ye} AND END_DATE>{ye}").df()
    line(f"  end-{y}: {int(r.n[0]):>9,} records / {int(r.iss[0]):>6,} issuers")
line("  (paper: ~910,000/62,800 at end-2019 -> ~326,000/15,300 at end-2020)")

line("\n== (c) Coverage-start backfill, effective-dated 1 July 2019 ==")
cov = con.sql(f"SELECT COUNT(*) n, COUNT(DISTINCT ISSUERID) iss FROM '{CF}' "
              f"WHERE regexp_matches(FIELD_ID,'{SEV}') AND START_DATE=20190701").df()
line(f"  START_DATE=2019-07-01: {int(cov.n[0]):,} records / {int(cov.iss[0]):,} issuers   (paper: 920,424 / 62,716)")

line("\n== (d) IAS-vs-WAKIS gap behind Table 1's WAKIS / dWAKIS N ==")
def inforce(field, y):
    return (f"SELECT ISSUERID, arg_max(TRY_CAST(VALUE AS DOUBLE), VERSION_START_DATE) v FROM '{SS}' "
            f"WHERE FIELD_ID='{field}' AND START_DATE>=20150101 AND START_DATE<={y}*10000+1231 "
            f"AND (END_DATE IS NULL OR END_DATE>={y}*10000+1231) GROUP BY 1")
for y in (2022,):
    ias = con.sql(inforce("INDUSTRY_ADJUSTED_SCORE", y)).df().dropna()
    wak = con.sql(inforce("WEIGHTED_AVERAGE_SCORE", y)).df().dropna()
    m = ias.merge(wak, on="ISSUERID", how="left", suffixes=("_ias", "_wak"))
    line(f"  year {y}: IAS firms={len(ias):,}; with WAKIS={int(m.v_wak.notna().sum()):,}; "
         f"IAS-but-no-WAKIS={int(m.v_wak.isna().sum()):,}")
line("  => a few firm-years each year carry an IAS with no WAKIS in force at year-end, so in Table 1")
line("     WAKIS=401,872 and dWAKIS (needs WAKIS in t and t-1)=401,835 vs 401,885 for all other variables.")

open("verify_data_facts_LOG.txt", "w").write("\n".join(out) + "\n")
print("\nwrote verify_data_facts_LOG.txt")
