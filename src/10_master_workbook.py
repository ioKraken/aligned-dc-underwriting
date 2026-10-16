"""Builds deliverables/AI_Premium_Study_Master.xlsx: the full deal dataset with live formulas, AI coding, results and sources."""
from pathlib import Path
import numpy as np, pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

R = Path(__file__).resolve().parent.parent
S = pd.read_csv(R / "data_clean/deals_stage2.csv", low_memory=False)
A = pd.read_csv(R / "data_clean/deals_analysis_v1.csv", low_memory=False)
F = pd.read_csv(R / "data_clean/financials_stage2.csv", low_memory=False)[["deal_id", "revenue_prior_ltm"]]
d = S.merge(A[["deal_id", "ai_intensity", "ai_flag_strict", "ai_flag_broad", "in_evrev_final", "in_premium_final", "in_ebitda_final"]], on="deal_id", how="left").merge(F, on="deal_id", how="left")
d = d.sort_values(["announcement_date"]).reset_index(drop=True)
FONT = "Arial"; BLUE = Font(name=FONT, color="0000FF", size=10); BLK = Font(name=FONT, size=10); BOLD = Font(name=FONT, bold=True, size=10)
HDR = Font(name=FONT, bold=True, color="FFFFFF", size=10); HFILL = PatternFill("solid", fgColor="1F3864"); GREY = PatternFill("solid", fgColor="F2F2F2")
thin = Side(style="thin", color="BFBFBF")
wb = Workbook()

def header(ws, row, cols, widths=None):
    for j, c in enumerate(cols, 1):
        x = ws.cell(row, j, c); x.font = HDR; x.fill = HFILL; x.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        if widths: ws.column_dimensions[L(j)].width = widths[j - 1]
    ws.row_dimensions[row].height = 42

def num(v, scale=1.0):
    try:
        v = float(v)
        return None if np.isnan(v) else v / scale
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------- README
ws = wb.active; ws.title = "READ_ME"
lines = [("AI Acquisition Premium Study - Master Workbook", BOLD), ("Independent student research project, 2026. Hand-selected sample of 55 US public technology acquisitions (2015-2025) built from SEC filings and company press releases.", BLK), ("", BLK),
 ("Tabs", BOLD), ("Deal_Dataset: every deal, inputs in blue (from filings), multiples/growth/premium computed by live formulas in black.", BLK), ("AI_Coding: the 18 companies classified blind by two coders, plus the final adjudicated label.", BLK),
 ("Summary: sample counts and AI vs non-AI comparison (live formulas off Deal_Dataset).", BLK), ("Regression_Results: exploratory statistical results (computed in Python, pasted as values).", BLK), ("Sample_Waterfall: how 55 deals become the 35-deal EV/Revenue sample.", BLK), ("", BLK),
 ("Key result", BOLD), ("No evidence that AI-enabled targets traded at higher EV/Revenue multiples in this sample. Only 2-3 strict AI-native targets exist in the sample, so the pre-registered test could not be run; the result is exploratory, not definitive.", BLK), ("", BLK),
 ("Caveats", BOLD), ("1. Sample is hand-picked (well-known deals), not a systematic universe.  2. EV is used only when company-stated or bridgeable from filings; otherwise blank.  3. Blank = not found in filings (never estimated).  4. No causal claims.", BLK),
 ("Colour code: blue = hard-coded input from source; black = formula; grey rows = not in the EV/Revenue analysis sample.", BLK), ("Units: $mm unless stated. Multiples in x. Premiums and growth as %.", BLK)]
for i, (t, f) in enumerate(lines, 1):
    c = ws.cell(i, 1, t); c.font = f; c.alignment = Alignment(wrap_text=True)
ws.column_dimensions["A"].width = 140; ws["A1"].font = Font(name=FONT, bold=True, size=14)

# ---------------------------------------------------------------- Deal dataset
ws = wb.create_sheet("Deal_Dataset")
cols = ["Deal ID", "Target", "Buyer", "Announced", "Buyer type", "Sector", "Offer price ($/sh)", "Unaffected price ($/sh)", "Enterprise value ($mm)", "EV basis",
        "LTM revenue ($mm)", "Prior-year LTM revenue ($mm)", "LTM EBITDA ($mm)", "EV / Revenue (x)", "Revenue growth (%)", "EBITDA margin (%)", "EV / EBITDA (x)", "1-day premium (%)",
        "AI intensity (0-3)", "Broad AI (>=1)", "Strict AI (>=2)", "In EV/Rev sample", "In premium sample", "Data quality", "Source URL", "Notes"]
header(ws, 1, cols, [7, 26, 26, 11, 10, 20, 10, 11, 12, 16, 11, 11, 11, 10, 10, 10, 10, 10, 9, 8, 8, 9, 9, 8, 40, 60])
for i, r in d.iterrows():
    row = i + 2
    vals = [r.deal_id, r.target_name, r.buyer_name, r.announcement_date, r.buyer_type, r.sector_primary, num(r.offer_price), num(r.unaffected_price_1d), num(r.ev_usd, 1e6), r.ev_basis,
            num(r.revenue_ltm_usd, 1e6), num(r.revenue_prior_ltm, 1e6), num(r.ebitda_ltm_usd, 1e6)]
    for j, v in enumerate(vals, 1):
        c = ws.cell(row, j, v); c.font = BLUE if j >= 7 else BLK
    f = {14: f'=IF(AND(ISNUMBER(I{row}),ISNUMBER(K{row}),K{row}>0),I{row}/K{row},"")', 15: f'=IF(AND(ISNUMBER(K{row}),ISNUMBER(L{row}),L{row}>0),K{row}/L{row}-1,"")',
         16: f'=IF(AND(ISNUMBER(M{row}),ISNUMBER(K{row}),K{row}>0),M{row}/K{row},"")', 17: f'=IF(AND(ISNUMBER(I{row}),ISNUMBER(M{row}),M{row}>0),I{row}/M{row},"")',
         18: f'=IF(AND(ISNUMBER(G{row}),ISNUMBER(H{row}),H{row}>0),G{row}/H{row}-1,"")', 20: f'=IF(ISNUMBER(S{row}),IF(S{row}>=1,1,0),"")', 21: f'=IF(ISNUMBER(S{row}),IF(S{row}>=2,1,0),"")'}
    for j, v in f.items():
        ws.cell(row, j, v).font = BLK
    ws.cell(row, 19, num(r.ai_intensity)).font = BLUE
    for j, v in ((22, int(r.in_evrev_final == 1)), (23, int(r.in_premium_final == 1)), (24, r.data_quality_flag), (25, r.source_url), (26, r.notes)):
        ws.cell(row, j, v).font = BLK
    for j, fmt in ((7, '$#,##0.00'), (8, '$#,##0.00'), (9, '#,##0'), (11, '#,##0.0'), (12, '#,##0.0'), (13, '#,##0.0;(#,##0.0)'), (14, '0.0"x"'), (15, '0.0%;(0.0%)'), (16, '0.0%;(0.0%)'), (17, '0.0"x"'), (18, '0.0%;(0.0%)')):
        ws.cell(row, j).number_format = fmt
    if r.in_evrev_final != 1:
        for j in range(1, 25): ws.cell(row, j).fill = GREY
    for j in range(1, 27): ws.cell(row, j).border = Border(bottom=thin)
N = len(d) + 1
ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:Z{N}"

# ---------------------------------------------------------------- Summary (live)
ws = wb.create_sheet("Summary"); D = "Deal_Dataset"
ws["A1"] = "Summary - live formulas from Deal_Dataset"; ws["A1"].font = Font(name=FONT, bold=True, size=13)
rng = lambda c: f"{D}!${c}$2:${c}${N}"
rows = [("Deals in dataset", f"=COUNTA({rng('A')})", "0"), ("Deals in EV/Revenue sample", f"=SUM({rng('V')})", "0"), ("Deals in takeover-premium sample", f"=SUM({rng('W')})", "0"),
        ("Broad-AI deals in EV/Rev sample", f'=COUNTIFS({rng("V")},1,{rng("T")},1)', "0"), ("Strict-AI deals in EV/Rev sample", f'=COUNTIFS({rng("V")},1,{rng("U")},1)', "0"), ("", None, None),
        ("Mean EV/Revenue - broad AI (x)", f'=AVERAGEIFS({rng("N")},{rng("V")},1,{rng("T")},1)', '0.0"x"'), ("Mean EV/Revenue - non-AI (x)", f'=AVERAGEIFS({rng("N")},{rng("V")},1,{rng("T")},0)', '0.0"x"'),
        ("Mean EV/Revenue - all sample (x)", f'=AVERAGEIFS({rng("N")},{rng("V")},1)', '0.0"x"'), ("Mean revenue growth - broad AI", f'=AVERAGEIFS({rng("O")},{rng("V")},1,{rng("T")},1)', "0.0%"),
        ("Mean revenue growth - non-AI", f'=AVERAGEIFS({rng("O")},{rng("V")},1,{rng("T")},0)', "0.0%"), ("Mean 1-day premium - broad AI", f'=AVERAGEIFS({rng("R")},{rng("W")},1,{rng("T")},1)', "0.0%"),
        ("Mean 1-day premium - non-AI", f'=AVERAGEIFS({rng("R")},{rng("W")},1,{rng("T")},0)', "0.0%"), ("", None, None),
        ("Medians (computed in Python; values)", None, None), ("Median EV/Revenue - broad AI (x)", None, '0.0"x"'), ("Median EV/Revenue - non-AI (x)", None, '0.0"x"'), ("Median 1-day premium - broad AI", None, "0.0%"), ("Median 1-day premium - non-AI", None, "0.0%")]
E1 = A[A.in_evrev_final == 1]; P1 = A[A.in_premium_final == 1]
med = {"Median EV/Revenue - broad AI (x)": E1.loc[E1.ai_flag_broad == 1, "ev_revenue"].median(), "Median EV/Revenue - non-AI (x)": E1.loc[E1.ai_flag_broad == 0, "ev_revenue"].median(),
       "Median 1-day premium - broad AI": P1.loc[P1.ai_flag_broad == 1, "premium_1d"].median(), "Median 1-day premium - non-AI": P1.loc[P1.ai_flag_broad == 0, "premium_1d"].median()}
for i, (lab, fml, fmt) in enumerate(rows, 3):
    ws.cell(i, 1, lab).font = BOLD if fml is None and fmt is None and lab else BLK
    if fml: c = ws.cell(i, 2, fml); c.font = Font(name=FONT, color="008000", size=10); c.number_format = fmt
    elif lab in med: c = ws.cell(i, 2, float(med[lab])); c.font = BLUE; c.number_format = fmt
ws.cell(len(rows) + 4, 1, "Means are sensitive to outliers (e.g., Slack 36x); medians are the preferred comparison. Unadjusted - not an 'AI premium'.").font = Font(name=FONT, italic=True, size=9)
ws.column_dimensions["A"].width = 42; ws.column_dimensions["B"].width = 14

# ---------------------------------------------------------------- AI coding
ws = wb.create_sheet("AI_Coding")
c1 = pd.read_csv(R / "data_clean/ai_coding_raw_coder1.csv", dtype=str, keep_default_na=False); c2 = pd.read_csv(R / "data_clean/ai_coding_raw_coder2.csv", dtype=str, keep_default_na=False)
adj = pd.read_csv(R / "data_clean/ai_coding_adjudicated.csv", dtype=str, keep_default_na=False)
m = adj[["company_id", "target_name", "announcement_date"]].merge(c1[["company_id", "ai_intensity", "rationale"]].rename(columns={"ai_intensity": "c1", "rationale": "r1"}), on="company_id").merge(
    c2[["company_id", "ai_intensity", "rationale"]].rename(columns={"ai_intensity": "c2", "rationale": "r2"}), on="company_id").merge(adj[["company_id", "final_intensity", "final_subsector", "adjudication_reason"]], on="company_id")
header(ws, 1, ["Company", "Announced", "Coder 1", "Coder 2", "Agree?", "Final", "Subsector", "Coder 1 rationale", "Coder 2 rationale", "Adjudication"], [26, 11, 8, 8, 8, 8, 9, 60, 60, 50])
for i, r in enumerate(m.itertuples(), 2):
    for j, v in enumerate([r.target_name, r.announcement_date, num(r.c1), num(r.c2), f"=IF(C{i}=D{i},\"Yes\",\"No\")", num(r.final_intensity), r.final_subsector, r.r1, r.r2, r.adjudication_reason], 1):
        c = ws.cell(i, j, v); c.font = BLUE if j in (3, 4, 6) else BLK; c.alignment = Alignment(wrap_text=True, vertical="top")
k = len(m) + 3
ag = pd.read_csv(R / "results/coder_agreement.csv").set_index("metric")["value"]
for lab, v in (("Cohen's kappa (strict AI, binary)", ag["binary_strict_cohens_kappa"]), ("Weighted kappa (0-3 intensity, quadratic)", ag["intensity_weighted_kappa_quadratic"])):
    ws.cell(k, 1, lab).font = BOLD; c = ws.cell(k, 3, float(v)); c.number_format = "0.00"; c.font = BLUE; k += 1
ws.cell(k, 1, "Intensity: 0 non-AI, 1 AI-enabled, 2 AI-native, 3 core AI infrastructure. Other 37 targets: not flagged by the AI keyword screen, assumed non-AI.").font = Font(name=FONT, italic=True, size=9)

# ---------------------------------------------------------------- Regression results
ws = wb.create_sheet("Regression_Results")
ws["A1"] = "Exploratory regressions - ln(EV/Revenue), HC3 robust standard errors (values from Python; not the pre-registered test)"; ws["A1"].font = BOLD
b = pd.read_csv(R / "results/p9_broad_ai_models.csv")
header(ws, 3, ["Specification", "Broad-AI coefficient (log pts)", "Approx. % difference", "95% CI low", "95% CI high", "Permutation p (2-sided)", "N", "AI N"], [36, 14, 12, 11, 11, 12, 6, 6])
for i, r in enumerate(b.itertuples(), 4):
    for j, (v, fm) in enumerate([(r.model, None), (r.beta, "0.00;(0.00)"), (f"=EXP(B{i})-1", "0.0%;(0.0%)"), (r.ci_lo, "0.00;(0.00)"), (r.ci_hi, "0.00;(0.00)"), (r.perm_p_two_sided, "0.00"), (r.N, "0"), (r.AI_N, "0")], 1):
        c = ws.cell(i, j, v); c.font = BLK if j == 3 else BLUE if j > 1 else BLK
        if fm: c.number_format = fm
g = pd.read_csv(R / "results/p9_precedent_growth_regression.csv"); s0 = 4 + len(b) + 2
ws.cell(s0, 1, "Precedent regression without AI label: ln(EV/Revenue) on growth, margin, size").font = BOLD
header(ws, s0 + 1, ["Term", "Coefficient", "HC3 SE", "p-value", "95% CI low", "95% CI high"])
for i, r in enumerate(g.itertuples(), s0 + 2):
    for j, v in enumerate([r.term, r.beta, r.hc3_se, r.p, r.ci_lo, r.ci_hi], 1):
        c = ws.cell(i, j, v); c.font = BLUE if j > 1 else BLK
        if j > 1: c.number_format = "0.00;(0.00)"
z = s0 + 2 + len(g)
ws.cell(z, 1, f"N = {int(g.N.iloc[0])}, adjusted R2 = {g.adj_r2.iloc[0]:.2f}").font = BLK
ws.cell(z + 2, 1, "Reading: no specification shows a positive AI association; CIs are wide because only 9 broad-AI deals have complete data. Growth/margin/size explain little of the multiple dispersion in this hand-picked set.").font = Font(name=FONT, italic=True, size=9)

# ---------------------------------------------------------------- Waterfall
ws = wb.create_sheet("Sample_Waterfall"); w = pd.read_csv(R / "results/p4_sample_waterfall.csv")
header(ws, 1, list(w.columns), [18, 7, 60, 9, 11, 9, 14])
for i, r in enumerate(w.itertuples(index=False), 2):
    for j, v in enumerate(r, 1): ws.cell(i, j, v).font = BLK

for s in wb.worksheets:
    for row in s.iter_rows():
        for c in row:
            if c.font and c.font.name != FONT: c.font = Font(name=FONT, size=c.font.size or 10, bold=c.font.bold, color=c.font.color, italic=c.font.italic)
out = R / "deliverables" / "AI_Premium_Study_Master.xlsx"; wb.save(out); print("saved", out)
