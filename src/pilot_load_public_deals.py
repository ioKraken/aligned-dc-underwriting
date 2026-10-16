"""PILOT ONLY. Writes eight hand-picked, well-documented US public-target technology takeovers into data_raw/ so the real
pipeline can be exercised on real figures. Every number below was extracted by a research pass from SEC filings / press
releases / named secondary sources (see docs/source_register.csv). 'NF' = searched, not found. Nothing here is estimated by me
except where the notes column says so (LTM sums of filed figures).

THIS IS NOT THE STUDY UNIVERSE: the deals were picked by hand (selection bias), N=8. source_universe says so on every row.
"""
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa

root = U.project_root(None)
SRC = "pilot_hand_selected_NOT_SYSTEMATIC"
M = 1e6; B = 1e9
D = [
 dict(id="P01", t="Splunk Inc.", b="Cisco Systems", ann="2023-09-21", close="2024-03-18", bc="US", bt="strategic", sector="Infrastructure Software", sub="Data / observability / security analytics",
      tick="SPLK", exch="NASDAQ", head=28*B, htype="equity", offer=157.0, eq=28*B, ev=None, evq="C", debt=3879.386*M, cash=2448.988*M,
      un_date="2023-09-20", un_px=119.59, un_note="close per Benzinga (secondary); company-reported premium ~31% not in press release", p1w="NF", p1m="NF", vwap=None,
      rev=3843.3*M, rev_end="2023-07-31", rev_prior=3038.704*M, ebitda=69.665*M, ebitda_note="GAAP op income + cash-flow D&A, LTM to 2023-07-31: (-235.506-275.077+481.785) + (99.470+46.945-47.952); includes SBC expense (unadjusted)", fq="B", fin_note="LTM = FY23 3,654.0 (rounded) + 6M to 2023-07-31 1,662.093 - 6M to 2022-07-31 1,472.834",
      desc="Splunk helps customers build a safer and more resilient digital world. We deliver innovative solutions that enable organizations to harness the value of their data to help keep their digital systems secure, available and performant.",
      desc_src="Splunk 10-K FY ended 2023-01-31 (only Item 1 sentence retrieved)",
      url="https://www.sec.gov/Archives/edgar/data/1353283/000110465923102594/tm2326347d1_ex99-1.htm",
      notes="EV not stated by company; equity value ~$28bn rounded; debt = convertible notes carrying value; cash = cash + current investments at 2023-07-31 (10-Q). Premium and unaffected close from secondary press only."),
 dict(id="P02", t="Nuance Communications", b="Microsoft", ann="2021-04-12", close="2022-03-04", bc="US", bt="strategic", sector="Application Software", sub="Conversational AI / healthcare speech",
      tick="NUAN", exch="NASDAQ", head=19.7*B, htype="enterprise", offer=56.0, eq=None, ev=19.7*B, evq="B", debt=None, cash=None,
      un_date="2021-04-09", un_px=45.58, un_note="close per Benzinga (secondary); DEFM14A states premium ~22.9% to 2021-04-09 close, consistent", p1w="NF", p1m="NF", vwap=None,
      rev=1463.1*M, rev_end="2020-12-31", rev_prior=None, ebitda=223.852*M, ebitda_note="GAAP op income + D&A, LTM to 2020-12-31, continuing ops: (112.588+31.546-35.996)+(116.479+22.786-23.551); prior-year LTM NF (recast quarter 2018-12-31 not found)", fq="B", fin_note="LTM = FY20 1,478.9 + Q1FY21 345.753 - Q1FY20 361.509 (earnings releases)",
      desc="Nuance Communications, Inc. is a technology pioneer and market leader in conversational AI and ambient clinical intelligence.",
      desc_src="Nuance 10-K FY2020",
      url="https://www.sec.gov/Archives/edgar/data/1002517/000119312521112515/d22854dex991.htm",
      notes="EV $19.7bn stated by the company 'inclusive of net debt'; equity value not stated. Close date from secondary press (Windows Central)."),
 dict(id="P03", t="Anaplan Inc.", b="Thoma Bravo", ann="2022-03-20", close="2022-06-22", bc="US", bt="sponsor", sector="Application Software", sub="Connected planning SaaS",
      tick="PLAN", exch="NYSE", head=10.4*B, htype="consideration", offer=63.75, eq=10.4*B, ev=None, evq="C", debt=0.0, cash=299.371*M,
      un_date="2022-03-18", un_px=50.59, un_note="DEFA14A: premium ~26% to $50.59 closing price on 2022-03-18 (at $63.75); 30-day VWAP $46.46 per DEFA14A", p1w="NF", p1m="NF", vwap=46.46, dil=163e6,
      rev=592.176*M, rev_end="2022-01-31", rev_prior=447.8*M, ebitda=-172.199*M, ebitda_note="GAAP operating loss -200.710 + cash-flow D&A 28.511, FY ended 2022-01-31", fq="B", fin_note="LTM = FY22 (ended 2022-01-31); prior = FY21 447.8",
      desc="Anaplan is a cloud-native enterprise SaaS company and a market leader in Connected Planning, empowering global enterprises to orchestrate transformative business performance.",
      desc_src="Anaplan 10-K FY2021 (last 10-K before announcement)",
      url="https://www.thomabravo.com/press-releases/thoma-bravo-completes-acquisition-of-anaplan",
      notes="Price cut from $66.00 to $63.75 on 2022-06-06; final terms used. Value sources conflict ($10.4bn Thoma Bravo vs $9.6bn Techzine). Debt 0 inferred from absence of debt line items."),
 dict(id="P04", t="Alteryx Inc.", b="Clearlake Capital / Insight Partners", ann="2023-12-18", close="2024-03-19", bc="US", bt="sponsor", sector="Application Software", sub="Analytics automation",
      tick="AYX", exch="NYSE", head=4.4*B, htype="enterprise", offer=48.25, eq=3.46*B, ev=4.4*B, evq="B", debt=1237*M, cash=635*M,
      un_date="2023-09-05", un_px=None, un_note="company states 59% premium to unaffected close but price not found", p1w="NF", p1m="NF", vwap=None,
      rev=920*M, rev_end="2023-09-30", rev_prior=None, fq="B", fin_note="LTM = FY22 855 + 9M23 619 - 9M22 554 (rounded millions)",
      desc="We are a leader in analytics automation. The Alteryx Analytics Automation Platform empowers analytics for all by delivering easy, end-to-end automation of data engineering, analytics, reporting, machine learning, and data science processes, enabling enterprises to democratize data analytics across their organizations for a broad range of use cases.",
      desc_src="Alteryx 10-K FY2022",
      url="https://www.sec.gov/Archives/edgar/data/1689923/000119312523298609/d676158dex991.htm",
      notes="EV $4.4bn stated 'including debt'; equity $3.46bn from Reuters (media). Debt/cash at 2023-09-30 are carrying values (convertible notes + term debt; cash + ST investments). Competing-bid claim by TechCrunch not confirmed."),
 dict(id="P05", t="Juniper Networks", b="Hewlett Packard Enterprise", ann="2024-01-09", close="2025-07-02", bc="US", bt="strategic", sector="Hardware OEM", sub="Networking equipment and software",
      tick="JNPR", exch="NYSE", head=14*B, htype="equity", offer=40.0, eq=14*B, ev=None, evq="C", debt=1588.5*M, cash=1377.1*M,
      un_date="2024-01-08", un_px=30.22, un_note="DEFM14A: '32% over closing price of $30.22 on January 8, 2024'", p1w="NF", p1m="NF", vwap=29.45,
      rev=5648.5*M, rev_end="2023-09-30", rev_prior=5152.3*M, ebitda=747.6*M, ebitda_note="GAAP op income LTM 547.9 + cash-flow D&A and accretion LTM 199.7 (to 2023-09-30)", fq="B", fin_note="LTM = FY22 5,301.2 + 9M23 4,199.7 - 9M22 3,852.4",
      desc="Juniper Networks designs, develops, and sells products and services for high-performance networks to enable customers to build scalable, reliable, secure, and cost-effective networks for their businesses, while achieving agility and improved operating efficiency through automation.",
      desc_src="Juniper 10-K FY2022",
      url="https://hpe.com/us/en/newsroom/press-release/2024/01/hpe-to-acquire-juniper-networks-to-accelerate-ai-driven-innovation.html",
      notes="Sector set to Hardware OEM (networking equipment) = outside Phase 1 primary sectors; kept in raw data so the frozen exclusion rule is exercised. vwap_30 field holds the DEFM14A one-month VWAP 29.45. Equity value ~$14bn is HPE's rounded figure (shares x price ~ $12.97bn); long-term debt only."),
 dict(id="P06", t="Altair Engineering", b="Siemens", ann="2024-10-30", close="2025-03-26", bc="DE", bt="strategic", sector="Application Software", sub="Simulation, HPC and AI software",
      tick="ALTR", exch="NASDAQ", head=10.6*B, htype="equity", offer=113.0, eq=10.6*B, ev=10.0*B, evq="B", debt=226.812*M, cash=513.371*M,
      un_date="2024-10-21", un_px=None, un_note="company states 19% premium to unaffected close; price not stated", p1w="NF", p1m="NF", vwap=None,
      rev=644.66*M, rev_end="2024-09-30", rev_prior=601.631*M, ebitda=70.283*M, ebitda_note="GAAP op income LTM 29.310 + cash-flow D&A LTM 40.973 (to 2024-09-30)", fq="B", fin_note="LTM = FY23 612.7 + 9M24 473.157 - 9M23 441.198",
      desc="Altair Engineering Inc. is a global leader in computational science and artificial intelligence enabling organizations across broad industry segments to drive smarter decisions in an increasingly connected world.",
      desc_src="Altair 10-K FY2023",
      url="https://www.sec.gov/Archives/edgar/data/1701732/000119312524247631/d859065dex991.htm",
      notes="EV ~$10bn from Siemens release; equity $10.6bn from Altair release (different documents). Debt = convertible notes only."),
 dict(id="P07", t="Smartsheet Inc.", b="Blackstone / Vista Equity Partners", ann="2024-09-24", close="2025-01-22", bc="US", bt="sponsor", sector="Application Software", sub="Work management SaaS",
      tick="SMAR", exch="NYSE", head=8.4*B, htype="equity", offer=56.5, eq=8.4*B, ev=None, evq="C", debt=0.0, cash=706.6*M,
      un_date="2024-07-17", un_px=None, un_note="premium ~41% is to 90-day VWAP; close NF", p1w="NF", p1m="NF", vwap=None,
      rev=1042.2*M, rev_end="2024-07-31", rev_prior=867.37*M, ebitda=-44.213*M, ebitda_note="GAAP op loss LTM -71.647 + D&A LTM 27.434 (to 2024-07-31); FY24 D&A rounded", fq="B", fin_note="LTM = FY24 958.3 + 6M25 539.4 - 6M24 455.5",
      desc="Smartsheet, the enterprise work management platform, empowers organizations to innovate and achieve results quickly and securely at scale through effective collaboration and streamlined workflows.",
      desc_src="Smartsheet 10-K FY2024",
      url="https://www.blackstone.com/news/press/smartsheet-to-be-acquired-by-blackstone-and-vista-equity-partners-for-8-4-billion/",
      notes="Equity consideration ~$8.4bn; ADIA co-investor (sponsor consortium). Debt 0 inferred from absence of debt line items in 8-K summary."),
 dict(id="P08", t="Qualtrics International", b="Silver Lake / CPP Investments", ann="2023-03-13", close="2023-06-28", bc="US", bt="sponsor", sector="Application Software", sub="Experience management SaaS",
      tick="XM", exch="NASDAQ", head=12.5*B, htype="headline", offer=18.15, eq=12.4*B, ev=None, evq="C", debt=0.0, cash=719.9*M,
      un_date="2023-01-25", un_px=11.21, un_note="DEFM14C: close $11.21 on 2023-01-25, day before SAP announced it was exploring a sale of its stake (leak-adjacent; company premium 73% is to 30-day VWAP)", p1w="NF", p1m="NF", vwap=None,
      rev=1458.6*M, rev_end="2022-12-31", rev_prior=1075.7*M, ebitda=-951.435*M, ebitda_note="GAAP op loss -1,048.975 + D&A 97.540, FY2022; operating loss includes ~$1.03bn stock-based compensation", fq="B", fin_note="LTM = FY22; prior = FY21",
      desc="Qualtrics pioneered a new category of software, experience management, or XM, that enables organizations to find and fix broken experiences and drive operational improvements to improve customer loyalty, increase employee retention, and become a brand that people love.",
      desc_src="Qualtrics 10-K FY2022",
      url="https://www.sec.gov/Archives/edgar/data/1747748/000162828023007614/exhibit991-pressrelease1.htm",
      notes="Headline $12.5bn (press release) vs $12.4bn stated as equity value in an 8-K (summarised text); equity set to 12.4bn; treated as equity. Sources differ by one day on announcement (03-12 signing, 03-13 public). SAP was majority holder (DEFM14C). Debt 0 inferred."),
]
U_cols = list(pd.read_csv(root/"data_raw/templates/deal_universe_raw.csv", nrows=0).columns)
T_cols = list(pd.read_csv(root/"data_raw/templates/deal_terms_raw.csv", nrows=0).columns)
F_cols = list(pd.read_csv(root/"data_raw/templates/financials_raw.csv", nrows=0).columns)
S_cols = list(pd.read_csv(root/"data_raw/templates/descriptions_raw.csv", nrows=0).columns)
import json
_lite = root / "data_raw" / "lite_deals.json"
if _lite.exists():
    for _d in json.loads(_lite.read_text()):
        _d["_src"] = "lite_hand_selected_pilot_NOT_SYSTEMATIC"; D.append(_d)
_pp = root / "data_raw" / "prior_ltm_patch.json"
if _pp.exists():
    _patch = {x["id"]: x for x in json.loads(_pp.read_text()) if x.get("rev_prior")}
    for _d in D:
        if _d["id"] in _patch:
            _d["rev_prior"] = _patch[_d["id"]]["rev_prior"]; _d["fin_note"] = str(_d.get("fin_note", "")) + " | PRIOR LTM: " + str(_patch[_d["id"]].get("prior_note", ""))
u, t, f, s, reg, log = [], [], [], [], [], []
for d in D:
    u.append({**{c: "" for c in U_cols}, "deal_id": d["id"], "target_name": d["t"], "buyer_name": d["b"], "announcement_date": d["ann"], "close_date": d["close"],
              "deal_status": "completed", "target_country": "US", "buyer_country": d["bc"], "target_public_private": "public", "buyer_type": d["bt"],
              "sector": d["sector"], "subsector": d["sub"], "headline_transaction_value": d["head"], "source_universe": d.get("_src", SRC), "source_url": d["url"], "notes": d["notes"],
              "deal_type": "control", "ticker": d["tick"], "exchange": d["exch"], "headline_value_type": d["htype"], "offer_price": d["offer"], "mixed_consortium": 0})
    nf = lambda v: "NF" if v is None else v
    t.append({**{c: "" for c in T_cols}, "deal_id": d["id"], "currency_original": "USD", "fx_rate_announcement": 1.0, "headline_value": d["head"],
              "equity_value": nf(d["eq"]), "enterprise_value": nf(d["ev"]), "ev_basis": "reported" if d["ev"] else "calculated_from_bridge", "ev_quality": d["evq"],
              "debt_assumed": nf(d["debt"]), "cash_acquired": nf(d["cash"]), "preferred": 0 if d["debt"] is not None else "NF", "minority_interest": 0 if d["debt"] is not None else "NF",
              "other_ev_adjustments": 0, "contingent_consideration": 0, "included_in_ev": 0, "cash_pct": 100, "stock_pct": 0, "other_pct": 0, "offer_price": d["offer"],
              "diluted_shares": d.get("dil", "NF"), "unaffected_date": d["un_date"], "unaffected_reason": d["un_note"], "unaffected_price_1d": nf(d["un_px"]), "price_1w": "NF", "price_1m": "NF",
              "vwap_30": nf(d["vwap"]), "price_90d": "NF", "leak_flag": "", "predeal_market_cap": "NF", "standalone_financials": ""})
    f.append({**{c: "" for c in F_cols}, "deal_id": d["id"], "revenue_period_end": d["rev_end"], "revenue_ltm": d["rev"], "revenue_prior_ltm": nf(d["rev_prior"]),
              "ebitda_ltm": nf(d.get("ebitda")), "ebitda_definition": "reported" if d.get("ebitda") is not None else "", "currency": "USD", "fx_to_usd": 1.0, "source_revenue": d["fin_note"], "source_ebitda": d.get("ebitda_note", "NF: inputs incomplete"),
              "financials_quality": d["fq"], "financials_disclosed": 1})
    s.append({**{c: "" for c in S_cols}, "deal_id": d["id"], "target_description": d["desc"], "filing_description": d["desc"], "historical_description": d["desc"]})
    reg.append({"source_id": f"S-{d['id']}-1", "deal_id": d["id"], "field": "deal terms", "source_type": "press release / SEC filing", "source_tier": "A", "source_name": d["desc_src"] + " / deal release",
                "url": d["url"], "document_date": d["ann"], "retrieved_date": "2026-10-06", "value_supported": f"offer {d['offer']}; ann {d['ann']}", "conflict_flag": 0,
                "conflicting_values": "", "selected_value": d["offer"], "selection_reason": "company primary document", "notes": d["notes"]})
    log.append({"deal_id": d["id"], "field": "unaffected_price_1d / price_1w / price_1m / ebitda", "researcher": "Claude research pass", "search_date": "2026-10-06",
                "source_found": "partial", "source_quality": "see notes", "missing_code": "NF", "missing_reason": "not stated in filings/press retrieved; no price-history source reachable", "notes": d["un_note"]})
pd.DataFrame(u).to_csv(root/"data_raw/deal_universe_raw.csv", index=False)
pd.DataFrame(t).to_csv(root/"data_raw/deal_terms_raw.csv", index=False)
pd.DataFrame(f).to_csv(root/"data_raw/financials_raw.csv", index=False)
pd.DataFrame(s).to_csv(root/"data_raw/descriptions_raw.csv", index=False)
pd.DataFrame(reg).to_csv(root/"docs/source_register.csv", index=False)
pd.DataFrame(log).to_csv(root/"docs/collection_log.csv", index=False)
print("wrote pilot files:", len(D), "deals")
