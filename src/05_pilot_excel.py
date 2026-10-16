"""Builds results/Phase2_Pilot_Results.xlsx from the Phase 2 outputs (pilot data)."""
import sys
from pathlib import Path
import pandas as pd
from openpyxl.styles import Font, PatternFill
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U
root = U.project_root(None)
d = pd.read_csv(root / "data_clean/deals_stage2.csv")
keep = {"deal_id": "deal_id", "target_name": "Target", "buyer_name": "Buyer", "announcement_date": "Announced", "close_date": "Closed", "sector_primary": "Sector (primary)", "buyer_type": "Buyer type",
        "equity_value_usd": "Equity value USD", "ev_usd": "EV USD", "ev_basis": "EV basis", "ev_quality": "EV quality", "ev_recon_diff_pct": "EV recon diff (reported vs bridge)", "offer_price": "Offer price",
        "unaffected_price_1d": "Unaffected close", "premium_1d": "Premium 1D", "revenue_ltm_usd": "LTM revenue USD", "revenue_period_end": "Revenue period end", "staleness_days": "Staleness (days)",
        "revenue_growth": "Revenue growth", "ebitda_margin": "EBITDA margin (GAAP OI + D&A)", "ev_revenue": "EV / LTM revenue", "ev_ebitda": "EV / EBITDA", "premium_vwap30": "Premium vs 30d VWAP", "in_primary_sample_ebitda": "In EV/EBITDA sample", "financials_quality": "Financials quality", "in_primary_sample_evrev": "In EV/Revenue sample",
        "in_primary_sample_premium": "In premium sample", "ai_candidate_flag": "Keyword screen candidate", "candidate_keyword_hits": "Keyword hits"}
t = d[list(keep)].rename(columns=keep).sort_values("deal_id")
wf = pd.read_csv(root / "results/sample_waterfall_phase2.csv")[["outcome", "stage", "step", "total_N", "removed_at_step"]]
q = pd.read_csv(root / "results/data_quality_report.csv")
src = pd.read_csv(root / "docs/source_register.csv")[["deal_id", "source_name", "url", "document_date", "notes"]]
cav = pd.DataFrame({"caveat": [
    "PILOT ONLY: 8 hand-picked, well-known US public-target deals. Not a systematic universe; selection bias by construction. Do not use for any AI vs non-AI conclusion.",
    "EV is company-stated for Nuance, Alteryx, Altair; for the others it is built from a rounded equity value plus balance-sheet debt and cash (quality C). 'No debt' for Anaplan, Smartsheet, Qualtrics is inferred from absent line items.",
    "Juniper (networking equipment) is classed Hardware OEM, outside the frozen primary sectors, so the Phase 1 rule excludes it from the EV/Revenue sample.",
    "Anaplan: price cut from $66.00 to $63.75 after signing; final terms used. Value sources conflict ($10.4bn vs $9.6bn).",
    "Premium is computed only where an unaffected CLOSE was found: Splunk, Nuance, Anaplan, Juniper, Qualtrics (Juniper is outside the sector rule). Alteryx, Altair, Smartsheet closes are NF (price-history sites were blocked); their company premiums reference VWAPs or an unstated close.",
    "Splunk and Nuance unaffected closes are from Benzinga (secondary), cross-checked to company-stated premiums. Anaplan, Juniper, Qualtrics closes are from SEC filings. No 1-week or 1-month closes were found for any deal.",
    "EBITDA = GAAP operating income + cash-flow D&A (unadjusted, includes stock-comp expense), computed from filed inputs, for 7 deals; Alteryx is NF. Splunk's EV/EBITDA (422x) and Altair's (142x) are extreme because EBITDA is near zero; do not read them as valuation signals.",
    "Growth exists for 7 deals (prior-year LTM revenue found); Nuance (basis mismatch in recast quarters) and Alteryx (prior-year inputs not found) are NF.",
    "Qualtrics equity set to $12.4bn (stated as equity value in an 8-K per summarised text) vs $12.5bn in the press release.",
    "AI classification has NOT been done (Phase 3 needs two blind human coders). Keyword hits are a screen only."]})
out = root / "results/Phase2_Pilot_Results.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    for name, df in (("READ_FIRST", cav), ("deals", t), ("waterfall", wf), ("data_quality", q), ("sources", src)):
        df.to_excel(w, sheet_name=name, index=False)
    for ws in w.book.worksheets:
        for c in ws[1]:
            c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="DCE6F2")
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col[:30]) + 2))
    ws = w.book["deals"]
    for row in ws.iter_rows(min_row=2):
        for c in row:
            h = ws.cell(1, c.column).value
            if not isinstance(c.value, (int, float)):
                continue
            if h in ("Equity value USD", "EV USD", "LTM revenue USD"): c.number_format = "#,##0"
            elif h in ("Premium 1D", "Premium vs 30d VWAP", "EBITDA margin (GAAP OI + D&A)", "Revenue growth", "EV recon diff (reported vs bridge)"): c.number_format = "0.0%"
            elif h == "EV / LTM revenue": c.number_format = '0.0"x"'
    w.book["READ_FIRST"].column_dimensions["A"].width = 150
print("wrote", out)
