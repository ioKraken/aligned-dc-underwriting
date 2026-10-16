"""Universe completeness audit (Phase 2 section 30, 58, 59). AUDIT ONLY: nothing is inserted into the sample.

Optional inputs in data_raw/external_benchmarks/:
  annual_counts.csv     year, source, deal_count        (external tech M&A counts, comparable scope)
  league_tables.csv     year, rank, target_name, buyer_name, source   (largest tech deals per year)
  known_deals_audit.csv target_name, buyer_name, announcement_date, list_type (ai|non_ai), source

Outputs: results/coverage_audit.csv, results/missing_from_universe.csv

Deals found in an external list but absent from the universe are reported for manual follow-up. They are added
to the raw universe only if they meet the SAME frozen rules (period, geography, sector, control) as every
other deal, and the addition is logged in docs/deviations_log.md as a universe-repair entry.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa: E402


def main(root: Path) -> None:
    ext = root / "data_raw" / "external_benchmarks"
    x = pd.read_csv(root / "data_clean" / "deals_stage2.csv", parse_dates=["announcement_date"])
    x["norm_target"] = x["target_name"].map(U.normalize_name)
    x["year"] = x["announcement_date"].dt.year
    rows, missing = [], []

    p = ext / "annual_counts.csv"
    if p.exists():
        a = U.read_csv_safe(p)
        a["year"] = a["year"].astype(int)
        a["deal_count"] = a["deal_count"].astype(float)
        uni = x[x["in_period"] == 1].groupby("year").size().rename("universe_count")
        a = a.join(uni, on="year")
        a["coverage_rate"] = a["universe_count"].fillna(0) / a["deal_count"]
        for r in a.itertuples():
            rows.append({"check": "A_annual_counts", "year": r.year, "benchmark": r.source, "benchmark_n": r.deal_count,
                         "universe_n": r.universe_count, "coverage_rate": r.coverage_rate,
                         "note": "scope of external count may differ; interpret as indicative"})
    else:
        rows.append({"check": "A_annual_counts", "note": "NOT PERFORMED: no data_raw/external_benchmarks/annual_counts.csv"})

    def found(name, date_like):
        n = U.normalize_name(name)
        yr = pd.to_datetime(date_like, errors="coerce").year if date_like is not None else np.nan
        m = x[x["norm_target"] == n]
        if pd.notna(yr):
            m = m[(m["year"] - yr).abs() <= 1]
        return m

    p = ext / "league_tables.csv"
    if p.exists():
        lt = U.read_csv_safe(p)
        lt["year"] = lt["year"].astype(int)
        for yr, g in lt.groupby("year"):
            hits = 0
            for r in g.itertuples():
                m = found(r.target_name, f"{r.year}-06-30")
                if len(m):
                    hits += 1
                else:
                    missing.append({"list": "league_table_" + str(r.source), "target_name": r.target_name,
                                    "buyer_name": r.buyer_name, "year": yr, "list_type": "league",
                                    "action": "manual: verify rules (sector/geography/control) then add if eligible"})
            rows.append({"check": "B_league_tables", "year": yr, "benchmark": ";".join(sorted(g["source"].unique())),
                         "benchmark_n": len(g), "universe_n": hits, "coverage_rate": hits / len(g), "note": "top deals per year"})
    else:
        rows.append({"check": "B_league_tables", "note": "NOT PERFORMED: no league_tables.csv"})

    p = ext / "known_deals_audit.csv"
    if p.exists():
        kd = U.read_csv_safe(p)
        for lt_, g in kd.groupby("list_type"):
            hits = 0
            for r in g.itertuples():
                m = found(r.target_name, r.announcement_date)
                if len(m):
                    hits += 1
                else:
                    missing.append({"list": "known_" + lt_, "target_name": r.target_name, "buyer_name": r.buyer_name,
                                    "year": pd.to_datetime(r.announcement_date, errors="coerce").year, "list_type": lt_,
                                    "action": "manual: verify rules then add if eligible; log as universe repair"})
            rows.append({"check": "C_known_deals_" + lt_, "benchmark": "external known-deal list", "benchmark_n": len(g),
                         "universe_n": hits, "coverage_rate": hits / len(g),
                         "note": "AI vs non-AI coverage must be similar; a gap signals a screening bias"})
        ai = [r for r in rows if r["check"] == "C_known_deals_ai"]
        nai = [r for r in rows if r["check"] == "C_known_deals_non_ai"]
        if ai and nai:
            gap = ai[0]["coverage_rate"] - nai[0]["coverage_rate"]
            rows.append({"check": "C_ai_vs_nonai_coverage_gap", "coverage_rate": gap,
                         "note": "WARNING: universe may be AI-heavy" if gap > 0.10 else "gap within 10pp"})
    else:
        rows.append({"check": "C_known_deals", "note": "NOT PERFORMED: no known_deals_audit.csv"})

    cols = ["check", "year", "benchmark", "benchmark_n", "universe_n", "coverage_rate", "note"]
    out = pd.DataFrame(rows).reindex(columns=cols)
    out.to_csv(root / "results" / "coverage_audit.csv", index=False)
    pd.DataFrame(missing, columns=["list", "target_name", "buyer_name", "year", "list_type", "action"]).to_csv(
        root / "results" / "missing_from_universe.csv", index=False)
    performed = out["note"].astype(str).str.startswith("NOT PERFORMED").sum()
    print(out.to_string(index=False))
    print(f"\nchecks not performed: {performed}. Do not describe the data as a 'complete universe' unless A, B and C are performed "
          f"and coverage is documented; otherwise call it the 'research universe'.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    main(U.project_root(ap.parse_args().root))
