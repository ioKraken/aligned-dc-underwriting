"""Phase 3, step A: build independent coder sheets from the blind file and run the pre-coding leakage check.

Input : data_clean/ai_coding_blind.csv   (Phase 2; no valuation columns, text scrubbed)
Output: data_clean/ai_coding_raw_coder1.csv, ai_coding_raw_coder2.csv   (identity+text filled, judgement columns EMPTY)
        results/leakage_check.csv  (pre-coding part)
        docs/ai_classification_sources.csv (header only, if absent)

Both coders receive EVERY pooled row (candidates and the random audit sample) in different shuffled orders, so a coder
cannot tell from the file which rows the keyword screen flagged. Existing coder files are never overwritten.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_common as P  # noqa: E402
import utils as U  # noqa: E402

MONEY = re.compile(r"[$€£]\s?\d|\b\d[\d,\.]*\s?(million|billion|bn|mn)\b|\bEV/|\b\d+(\.\d+)?x\b|per share|\bpremium\b", re.I)


def main(root: Path) -> int:
    blind = pd.read_csv(root / "data_clean" / "ai_coding_blind.csv", dtype=str, keep_default_na=False)
    P.assert_no_valuation_columns(blind.columns)
    text_cols = ["business_description", "website_snapshot_text", "filing_description", "technical_description"]
    leaks = blind[text_cols].agg(" ".join, axis=1).map(lambda s: bool(MONEY.search(s)))
    rows = [{"check": "coder_file_has_no_valuation_columns", "result": "PASS", "detail": ""},
            {"check": "coder_text_has_no_money_or_multiple_phrases", "result": "FAIL" if leaks.any() else "PASS",
             "detail": f"{int(leaks.sum())} rows" if leaks.any() else ""}]
    pd.DataFrame(rows).to_csv(root / "results" / "leakage_check_pre_coding.csv", index=False)
    if leaks.any():
        print("LEAKAGE: money/multiple text found in coder-facing descriptions. Re-run Phase 2 redaction first.")
        return 1

    out = root / "data_clean"
    for i, seed_off in ((1, 0), (2, 1)):
        path = out / f"ai_coding_raw_coder{i}.csv"
        if path.exists() and path.stat().st_size > 0:
            existing = pd.read_csv(path, dtype=str)
            if existing[P.TEST_COLS + ["ai_intensity"]].notna().any().any():
                print(f"{path.name} already contains coder judgements: not overwriting (raw coder fields are immutable).")
                continue
        b = blind.sample(frac=1.0, random_state=U.SEED + seed_off).reset_index(drop=True)
        sheet = pd.DataFrame({
            "coder_row": np.arange(1, len(b) + 1), "company_id": b["company_id"], "target_name": b["target_name"],
            "announcement_date": b["announcement_date"], "sector": b["sector"],
            "description_text": b["business_description"], "historical_description": b["technical_description"],
            "website_snapshot_text": b["website_snapshot_text"], "filing_description": b["filing_description"]})
        for c in P.CODER_FILL_COLS:
            sheet[c] = ""
        sheet["coder_id"] = f"coder{i}"
        sheet[P.CODER_COLS].to_csv(path, index=False)
        print(f"wrote {path.name}: {len(sheet)} rows")

    src = root / "docs" / "ai_classification_sources.csv"
    if not src.exists():
        pd.DataFrame(columns=["company_id", "source_id", "source_date", "source_type", "source_tier", "excerpt_summary",
                              "test_supported", "url", "archived_url", "used_for_classification"]).to_csv(src, index=False)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    sys.exit(main(U.project_root(ap.parse_args().root)))
