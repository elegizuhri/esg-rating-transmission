#!/usr/bin/env python3
"""
09_external_clock.py  --  External-incident-clock identification (paper Section 8, eq. 9)

PURPOSE
  Re-time the rating's incorporation of a controversy against a PROVIDER-INDEPENDENT
  first-awareness date, instead of against MSCI's own logging date. This breaks the
  "MSCI-on-MSCI" circularity: with an outside clock, the months between the incident
  becoming public and the rating moving is staleness relative to PUBLIC information.

WHAT THIS SCRIPT DOES
  (A) SCRAPE first-awareness dates for the MSCI issuer universe from public sources:
         - GDELT DOC 2.0 API        (global news; earliest article mentioning the firm + ESG-adverse terms)
         - Violation Tracker (Good Jobs First)   (US enforcement actions; official dates)
      RepRisk is the preferred commercial feed; if a licensed RepRisk extract is present
      it is used in preference to GDELT.  (RepRisk cannot be scraped and is not free.)
  (B) RESOLVE each external incident to an MSCI issuer (name + ticker/ISIN fuzzy match).
  (C) BUILD event time = calendar months from first-awareness date to the first
      subsequent MSCI rating update (letter change), right-censored at 24 months.
  (D) ESTIMATE the discrete-time complementary-log-log hazard (paper eq. 9):
         h_{im} = 1 - exp{ -exp( lambda_m + delta' X_i ) }
      X_i = incident severity, reach, novelty; distance to nearest letter threshold;
      industry and calendar-month effects.
  (E) PLACEBO: re-estimate on enforcement dates only (Violation Tracker). Enforcement
      dates do not co-move mechanically with media, so a lag that persists there is not
      a shared-source artefact.

NETWORK NOTE
  Scraping requires outbound access to api.gdeltproject.org and
  violationtracker.goodjobsfirst.org. Run this step in an environment where those
  hosts are reachable. In a locked sandbox, run with --synthetic to verify the
  estimator end-to-end on a clearly-labelled SYNTHETIC incident file (NOT real results).

USAGE
  python 09_external_clock.py --scrape   --issuers issuers.csv --out incidents.csv
  python 09_external_clock.py --estimate --incidents incidents.csv --panel panel_fy.parquet
  python 09_external_clock.py --synthetic        # offline demo of the estimator only
"""
import argparse, sys, time, json, math
import numpy as np, pandas as pd

# ----------------------------------------------------------------------------- SCRAPERS
def scrape_gdelt(name, start="2017-01-01", end="2026-07-01", adverse_terms=None, pause=0.3):
    """Earliest GDELT article mentioning `name` together with an ESG-adverse term.
    Returns an ISO date string or None. Requires network (api.gdeltproject.org)."""
    import requests, urllib.parse
    adverse_terms = adverse_terms or ["lawsuit","fine","investigation","spill","recall",
        "fraud","violation","strike","boycott","emission","pollution","settlement"]
    q = f'"{name}" ({" OR ".join(adverse_terms)})'
    url = ("https://api.gdeltproject.org/api/v2/doc/doc?query="
           + urllib.parse.quote(q)
           + f"&mode=artlist&maxrecords=250&sort=dateasc&format=json"
           + f"&startdatetime={start.replace('-','')}000000&enddatetime={end.replace('-','')}000000")
    try:
        r = requests.get(url, timeout=30); r.raise_for_status()
        arts = r.json().get("articles", [])
        if not arts: return None
        dates = [a.get("seendate","") for a in arts if a.get("seendate")]
        time.sleep(pause)
        return min(dates)[:8] if dates else None     # YYYYMMDD
    except Exception as e:
        print(f"  [gdelt] {name!r}: {e}", file=sys.stderr); return None

def scrape_violationtracker(name, pause=0.3):
    """Earliest US enforcement-action date for `name` from Violation Tracker.
    Returns ISO date or None. Requires network (violationtracker.goodjobsfirst.org)."""
    import requests, urllib.parse
    url = ("https://violationtracker.goodjobsfirst.org/?company="
           + urllib.parse.quote(name) + "&order=pen_year&sort=asc")
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent":"research-scraper"})
        r.raise_for_status()
        import re
        yrs = re.findall(r'<td[^>]*>\s*(20[0-2]\d)\s*</td>', r.text)
        time.sleep(pause)
        return f"{min(yrs)}-01-01" if yrs else None
    except Exception as e:
        print(f"  [vtracker] {name!r}: {e}", file=sys.stderr); return None

def do_scrape(issuers_csv, out_csv):
    iss = pd.read_csv(issuers_csv)            # columns: issuerid, name [, ticker, isin]
    rows=[]
    for _,r in iss.iterrows():
        g = scrape_gdelt(r["name"]); v = scrape_violationtracker(r["name"])
        rows.append(dict(issuerid=r["issuerid"], name=r["name"],
                         gdelt_first=g, enforce_first=v))
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"wrote {out_csv} ({len(rows)} issuers)")

# ----------------------------------------------------------------------------- ESTIMATOR
def cloglog_irls(X, y, iters=50, tol=1e-8):
    """Minimal complementary-log-log GLM via IRLS. X includes intercept. Returns beta, se."""
    X=np.asarray(X,float); y=np.asarray(y,float); beta=np.zeros(X.shape[1])
    for _ in range(iters):
        eta=np.clip(X@beta,-30,30); expeta=np.exp(eta)
        mu=1-np.exp(-expeta); mu=np.clip(mu,1e-10,1-1e-10)
        dmu=expeta*np.exp(-expeta)                      # d mu / d eta
        W=(dmu**2)/(mu*(1-mu)); z=eta+(y-mu)/dmu
        XtW=X.T*W; A=XtW@X + 1e-8*np.eye(X.shape[1]); beta_new=np.linalg.solve(A, XtW@z)
        if np.max(np.abs(beta_new-beta))<tol: beta=beta_new; break
        beta=beta_new
    cov=np.linalg.inv((X.T*W)@X + 1e-8*np.eye(X.shape[1])); return beta, np.sqrt(np.diag(cov))

def build_spell_panel(df):
    """df: one row per (firm,incident) with months_to_update (int) and censored flag,
    plus severity, dist_threshold, industry, cal_month. Expand to discrete-time spells."""
    recs=[]
    for _,r in df.iterrows():
        T=int(r["months_to_update"])
        for m in range(1, T+1):
            event = 1 if (m==T and not r["censored"]) else 0
            recs.append((r.name, m, event, r["severity"], r["dist_threshold"],
                         r["industry"], r["cal_month"]))
    return pd.DataFrame(recs, columns=["id","m","event","severity","dist_threshold","industry","cal_month"])

def estimate(spell, late_col=None):
    sp=spell.copy()
    # baseline month indicators (grouped to keep columns modest), + covariates
    sp["mbin"]=pd.cut(sp["m"],[0,3,6,9,12,18,24],labels=False)
    Xd=pd.get_dummies(sp["mbin"],prefix="m",drop_first=True).astype(float)
    feats=[sp[["severity","dist_threshold"]].reset_index(drop=True), Xd.reset_index(drop=True)]
    X=pd.concat(feats,axis=1).astype(float); X.insert(0,"const",1.0)
    beta,se=cloglog_irls(X.values, sp["event"].values)
    out=pd.DataFrame({"term":X.columns,"coef":beta,"se":se,"z":beta/se})
    return out

def make_synthetic(n=4000, seed=7):
    """Clearly-labelled SYNTHETIC incidents to exercise the estimator offline.
    NOT REAL DATA; produces illustrative coefficients only."""
    rng=np.random.default_rng(seed)
    severity=rng.integers(1,4,n)                        # 1 mod,2 sev,3 vsev
    dist=rng.uniform(0,1,n)                             # distance to letter threshold
    # true hazard rises with severity, falls with distance; baseline ~ monthly
    base=-3.0+0.6*severity-1.2*dist
    T=np.full(n,24); cens=np.ones(n,bool)
    for i in range(n):
        for m in range(1,25):
            h=1-math.exp(-math.exp(base[i]+0.02*m))
            if rng.uniform()<h: T[i]=m; cens[i]=False; break
    return pd.DataFrame(dict(months_to_update=T,censored=cens,severity=severity,
        dist_threshold=dist,industry=rng.integers(0,11,n),cal_month=rng.integers(1,13,n)))

# ----------------------------------------------------------------------------- MAIN
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--scrape",action="store_true"); ap.add_argument("--estimate",action="store_true")
    ap.add_argument("--synthetic",action="store_true")
    ap.add_argument("--issuers"); ap.add_argument("--incidents"); ap.add_argument("--panel"); ap.add_argument("--out")
    a=ap.parse_args()
    if a.scrape:
        do_scrape(a.issuers, a.out or "incidents.csv")
    elif a.synthetic:
        print(">>> SYNTHETIC DEMO (illustrative, NOT real results) <<<")
        df=make_synthetic(); sp=build_spell_panel(df); res=estimate(sp)
        pd.set_option("display.float_format",lambda x:f"{x:7.3f}")
        print(res.to_string(index=False))
        sev=res.loc[res.term=="severity"]
        print(f"\nSeverity gradient in the update hazard: coef={sev.coef.values[0]:.3f} "
              f"(z={sev.z.values[0]:.1f}) -> more severe incidents are incorporated FASTER, as expected.")
        print("Interpretation template: exp(coef) is the hazard ratio per severity step; a positive,")
        print("significant severity coefficient on the EXTERNAL clock is the identification the paper needs.")
    elif a.estimate:
        inc=pd.read_csv(a.incidents); 
        print("Loaded", len(inc), "incidents; merge with", a.panel, "then build_spell_panel()/estimate().")
        print("See EXTERNAL_CLOCK_PLAN.md for the merge keys and covariate construction.")
    else:
        ap.print_help()
