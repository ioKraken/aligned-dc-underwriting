"""Build the Phase 2 data-entry workbook (Excel) and import a filled workbook back into the data_raw CSVs.

  python3 src/00_excel_workbook.py --build    -> data_raw/Phase2_Data_Entry_Workbook.xlsx (blank, with dropdowns + field guide)
  python3 src/00_excel_workbook.py --import F -> reads sheets deal_universe / deal_terms / financials / descriptions from F,
                                                 writes data_raw/*_raw.csv (existing non-empty files are backed up first)
Nothing is invented: rows come only from what the person types. Fully empty rows are skipped.
"""
from __future__ import annotations
import argparse, re, shutil, sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa: E402

SHEETS = {"deal_universe": "deal_universe_raw.csv", "deal_terms": "deal_terms_raw.csv", "financials": "financials_raw.csv", "descriptions": "descriptions_raw.csv"}
ENUMS = {
    "deal_status": "announced,definitive,completed,withdrawn,rejected,competing_bid,terminated",
    "deal_type": "control,minority,venture_round,pipe,asset_only,spac,distressed,acquihire,internal",
    "target_public_private": "public,private,subsidiary",
    "buyer_type": "strategic,sponsor,consortium,government_swf,other",
    "headline_value_type": "headline,equity,enterprise,consideration,implied_ev,undisclosed",
    "structural_exclusion": "minority,venture_round,pipe,asset_only,carveout_no_standalone,internal,spac,distressed,acquihire",
    "ev_quality": "A,B,C,D", "financials_quality": "A,B,C,D", "ebitda_definition": "reported,adjusted,database_normalized",
    "leak_flag": "0,1", "contingent_consideration": "0,1", "included_in_ev": "0,1", "mixed_consortium": "0,1", "financials_disclosed": "0,1"}
DATES = {"announcement_date", "close_date", "unaffected_date", "rumor_date", "revenue_period_end"}


def dictionary(root: Path) -> dict:
    out = {}
    p = root / "docs" / "data_dictionary.md"
    if p.exists():
        for line in p.read_text().splitlines():
            m = re.match(r"\|\s*([a-z0-9_]+)\s*\|(.+)", line)
            if m:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 7:
                    out[cells[0]] = {"definition": cells[1], "unit": cells[2], "null_allowed": cells[5], "example": cells[6]}
    return out


def build(root: Path) -> Path:
    tdir = root / "data_raw" / "templates"
    dd = dictionary(root)
    wb = Workbook()
    ws = wb.active; ws.title = "READ_ME"
    lines = [
        ("PHASE 2 DATA ENTRY WORKBOOK", True),
        ("One row per deal in each of the four data sheets. deal_id must be identical across sheets (any unique text, e.g. D001).", False),
        ("Missing numbers: type ND (not disclosed), NF (not found), NR (not relevant) or NA - never leave a number blank and never guess.", False),
        ("Dates: YYYY-MM-DD. Money: whole units of the stated currency (not millions) unless your column note says otherwise. Percentages: 0-100.", False),
        ("Window: announced 2015-01-01 to 2026-09-30. Include ALL technology control deals you can find - including ones that look unattractive for the study. Do not filter on AI or on valuation.", False),
        ("deal_universe: who bought whom. deal_terms: price, EV bridge, public-market prices. financials: target revenue/EBITDA (LTM). descriptions: neutral business descriptions as at announcement (no deal values, no prices).", False),
        ("In descriptions, do NOT paste deal values, multiples or premiums. Text is redacted automatically but clean input is better.", False),
        ("Field_Guide lists every column with its definition, allowed values and an example. Grey dropdown cells have fixed allowed values.", False),
        ("When done: save, then run  python3 src/00_excel_workbook.py --import <file.xlsx>  and  make phase2  (or send me the file).", False)]
    for i, (t, b) in enumerate(lines, 1):
        ws.cell(i, 1, t).font = Font(bold=b, size=14 if b else 11)
        ws.cell(i, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 140
    hdr_fill = PatternFill("solid", fgColor="DCE6F2")
    guide_rows = []
    for sheet, fn in SHEETS.items():
        cols = list(pd.read_csv(tdir / fn, nrows=0).columns)
        w = wb.create_sheet(sheet)
        for j, c in enumerate(cols, 1):
            cell = w.cell(1, j, c); cell.font = Font(bold=True); cell.fill = hdr_fill
            w.column_dimensions[get_column_letter(j)].width = max(14, min(36, len(c) + 4))
            g = dd.get(c, {})
            guide_rows.append([sheet, c, g.get("definition", ""), g.get("unit", ""), g.get("null_allowed", ""), ENUMS.get(c, ""), g.get("example", "")])
            if c in ENUMS:
                dv = DataValidation(type="list", formula1=f'"{ENUMS[c]}"', allow_blank=True, showErrorMessage=True,
                                    errorTitle="Allowed values", error="Pick a value from the list.")
                w.add_data_validation(dv); dv.add(f"{get_column_letter(j)}2:{get_column_letter(j)}2000")
            if c in DATES:
                w.cell(2, j).number_format = "yyyy-mm-dd"
                for r in range(2, 2001): w.cell(r, j).number_format = "@"
        w.freeze_panes = "B2"
    g = wb.create_sheet("Field_Guide")
    for j, h in enumerate(["sheet", "column", "definition", "unit", "blank allowed?", "allowed values", "example"], 1):
        g.cell(1, j, h).font = Font(bold=True); g.cell(1, j).fill = hdr_fill
    for r, row in enumerate(guide_rows, 2):
        for j, v in enumerate(row, 1):
            g.cell(r, j, v).alignment = Alignment(wrap_text=True, vertical="top")
    for j, wd in enumerate([16, 26, 70, 12, 14, 40, 22], 1):
        g.column_dimensions[get_column_letter(j)].width = wd
    out = root / "data_raw" / "Phase2_Data_Entry_Workbook.xlsx"
    wb.save(out)
    return out


def import_wb(root: Path, path: Path) -> int:
    wb = load_workbook(path, data_only=True)
    ok = True
    for sheet, fn in SHEETS.items():
        if sheet not in wb.sheetnames:
            print(f"sheet '{sheet}' missing"); ok = False; continue
        rows = list(wb[sheet].iter_rows(values_only=True))
        cols = [c for c in rows[0] if c]
        df = pd.DataFrame([r[:len(cols)] for r in rows[1:]], columns=cols)
        df = df.dropna(how="all")
        for c in df.columns:
            if c in DATES:
                df[c] = df[c].map(lambda v: v.strftime("%Y-%m-%d") if isinstance(v, datetime) else v)
        df = df.map(lambda v: v.strip() if isinstance(v, str) else v)
        if "deal_id" in df.columns:
            dup = df["deal_id"][df["deal_id"].duplicated()]
            if len(dup):
                print(f"{sheet}: duplicate deal_id {list(dup.unique())[:5]}"); ok = False
            if df["deal_id"].isna().any():
                print(f"{sheet}: rows without deal_id"); ok = False
        dest = root / "data_raw" / fn
        if dest.exists() and dest.stat().st_size > 400:
            shutil.copyfile(dest, dest.with_suffix(f".bak_{datetime.now():%Y%m%d%H%M%S}.csv"))
        df.to_csv(dest, index=False)
        print(f"{sheet}: {len(df)} rows -> {dest.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=None); ap.add_argument("--build", action="store_true"); ap.add_argument("--import", dest="imp", default=None)
    a = ap.parse_args(); root = U.project_root(a.root)
    if a.imp:
        sys.exit(import_wb(root, Path(a.imp)))
    print("wrote", build(root))
