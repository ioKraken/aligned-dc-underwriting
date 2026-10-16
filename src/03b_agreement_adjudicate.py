"""Phase 3, step B: validate independent coder sheets, compute agreement, build / validate the adjudication file.

Inputs : data_clean/ai_coding_raw_coder1.csv, ai_coding_raw_coder2.csv   (filled by the two independent coders)
Outputs: results/coder_agreement.csv, coder_confusion_binary.csv, coder_confusion_intensity.csv,
         coder_disagreements.csv, coder_disagreement_summary.csv, coder_test_agreement.csv,
         coder_validation_errors.csv, adjudication_status.csv
         data_clean/ai_coding_adjudicated.csv  (template created once; NEVER overwritten afterwards)

The raw coder files are never modified. Adjudicated values live only in ai_coding_adjudicated.csv.
If kappa < 0.70 the script reports which rules/tests/sectors drive the disagreement; it does not adjudicate it away.
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

ADJ_COLS = ["company_id", "target_name", "sector", "announcement_date", "coder1_intensity", "coder2_intensity",
            "coders_agree_intensity", "suggested_disagreement_category", "disagreement_category", "adjudication_reason",
            "final_intensity", "alt_intensity", "final_subsector", "final_secondary_subsector",
            "final_product_test", "final_technical_asset_test", "final_revenue_test", "final_persistence_12m",
            "persistence_not_testable", "final_confidence", "acquihire_ai_flag", "counterevidence_notes",
            "company_founded_year", "commercial_maturity", "evidence_source_ids", "strict_ai_review_done",
            "adjudicator_id", "adjudication_status"]


def load_coder(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in P.CODER_COLS if c not in d.columns]
    if missing:
        raise SystemExit(f"{path.name}: missing columns {missing}")
    return d


def validate(d: pd.DataFrame, who: str) -> list[dict]:
    errs = []
    coded = d[d["ai_intensity"].str.strip() != ""]
    partial = d[(d["ai_intensity"].str.strip() == "") & (d[P.TEST_COLS + ["ai_subsector", "confidence", "rationale"]].apply(lambda c: c.str.strip() != "").any(axis=1))]
    for r in partial.itertuples():
        errs.append({"coder": who, "company_id": r.company_id, "error": "partially filled row: ai_intensity missing"})
    for r in coded.itertuples():
        i = pd.to_numeric(r.ai_intensity, errors="coerce")
        if i not in (0, 1, 2, 3):
            errs.append({"coder": who, "company_id": r.company_id, "error": f"ai_intensity invalid: {r.ai_intensity!r}"}); continue
        for t in P.TEST_COLS:
            if getattr(r, t).strip() not in ("0", "1"):
                errs.append({"coder": who, "company_id": r.company_id, "error": f"{t} must be 0/1"})
        if r.confidence.strip() not in P.CONFIDENCE:
            errs.append({"coder": who, "company_id": r.company_id, "error": "confidence must be High/Medium/Low"})
        if i >= 2 and pd.to_numeric(r.ai_subsector, errors="coerce") not in P.SUBSECTORS:
            errs.append({"coder": who, "company_id": r.company_id, "error": "ai_subsector (1-9) required for intensity >= 2"})
        if (i >= 1 or any(getattr(r, t).strip() == "1" for t in P.TEST_COLS)) and not r.rationale.strip():
            errs.append({"coder": who, "company_id": r.company_id, "error": "rationale required for intensity >= 1 or any passed test"})
        if r.coder_id.strip() != who:
            errs.append({"coder": who, "company_id": r.company_id, "error": f"coder_id is {r.coder_id!r}, expected {who!r}"})
    return errs


def suggest_category(r) -> str:
    a, b = int(r.i1), int(r.i2)
    lo, hi = min(a, b), max(a, b)
    txt = " ".join([str(r.rat1), str(r.rat2), str(r.ce1), str(r.ce2)]).lower()
    if re.search(r"after (the )?acquisition|post[- ]deal|post[- ]acquisition|pivot", txt):
        return "AI was core only after acquisition"
    if r.sector == "Semiconductors":
        return "Semiconductor AI exposure ambiguity"
    if {str(r.sub1), str(r.sub2)} & {"2", "8"} and hi >= 2 and r.sector in ("Infrastructure Software", "IT Services"):
        return "Software vs AI infrastructure"
    if str(r.per1) != str(r.per2) and (str(r.per1) == "0" or str(r.per2) == "0") and hi >= 2:
        return "Persistence evidence unavailable"
    if lo == 0 and hi >= 1:
        return "Marketing vs core technology"
    if (lo, hi) in ((1, 2),):
        return "AI-enabled vs AI-native"
    if (lo, hi) in ((2, 3),):
        return "Software vs AI infrastructure"
    return "Other"


def main(root: Path, auto_accept: bool) -> int:
    res = root / "results"
    res.mkdir(exist_ok=True)
    c1, c2 = load_coder(root / "data_clean" / "ai_coding_raw_coder1.csv"), load_coder(root / "data_clean" / "ai_coding_raw_coder2.csv")
    errs = validate(c1, "coder1") + validate(c2, "coder2")
    pd.DataFrame(errs, columns=["coder", "company_id", "error"]).to_csv(res / "coder_validation_errors.csv", index=False)
    if errs:
        print(f"{len(errs)} coder-sheet validation errors (see results/coder_validation_errors.csv). Fix before agreement is computed.")
        return 1
    k1, k2 = c1[c1["ai_intensity"].str.strip() != ""].copy(), c2[c2["ai_intensity"].str.strip() != ""].copy()
    if k1.empty or k2.empty:
        print("No coded rows yet in one or both coder sheets; nothing to compare."); return 2
    for k in (k1, k2):
        for c in P.TEST_COLS + ["ai_intensity"]:
            k[c] = pd.to_numeric(k[c])
    m = k1.merge(k2, on="company_id", suffixes=("_1", "_2"))
    single = set(k1["company_id"]) ^ set(k2["company_id"])
    n = len(m)
    a1, a2 = m["ai_intensity_1"].to_numpy(), m["ai_intensity_2"].to_numpy()
    s1, s2 = (a1 >= 2).astype(int), (a2 >= 2).astype(int)
    b1, b2 = (a1 >= 1).astype(int), (a2 >= 1).astype(int)
    rows = []

    def add(metric, val, ci=(np.nan, np.nan), nn=n, note=""):
        rows.append({"metric": metric, "value": val, "ci95_low": ci[0], "ci95_high": ci[1], "n": nn, "note": note})
    add("double_coded_n", n)
    add("single_coded_n (need adjudication)", len(single))
    kb = P.cohen_kappa(s1, s2)
    add("binary_strict_raw_agreement", float((s1 == s2).mean()))
    add("binary_strict_disagreement_n", int((s1 != s2).sum()))
    add("binary_strict_cohens_kappa", kb, P.bootstrap_ci(P.cohen_kappa, s1, s2), note=P.kappa_band(kb))
    add("binary_broad_cohens_kappa", P.cohen_kappa(b1, b2), P.bootstrap_ci(P.cohen_kappa, b1, b2), note=P.kappa_band(P.cohen_kappa(b1, b2)))
    wq, wl = P.weighted_kappa(a1, a2, weights="quadratic"), P.weighted_kappa(a1, a2, weights="linear")
    add("intensity_exact_agreement", float((a1 == a2).mean()))
    add("intensity_weighted_kappa_quadratic", wq, P.bootstrap_ci(lambda x, y: P.weighted_kappa(x, y, weights="quadratic"), a1, a2), note=P.kappa_band(wq))
    add("intensity_weighted_kappa_linear", wl, note=P.kappa_band(wl))
    both_ai = m[(m["ai_intensity_1"] >= 2) & (m["ai_intensity_2"] >= 2)]
    if len(both_ai):
        add("subsector_raw_agreement (both coders strict AI)", float((both_ai["ai_subsector_1"] == both_ai["ai_subsector_2"]).mean()), nn=len(both_ai))
    add("phase1_kappa_target", P.KAPPA_TARGET, note="MET" if (not np.isnan(kb) and kb >= P.KAPPA_TARGET) else "NOT MET: investigate rules; do not adjudicate away")
    pd.DataFrame(rows).to_csv(res / "coder_agreement.csv", index=False)

    # confusion tables
    cb = pd.crosstab(pd.Series(np.where(s1 == 1, "Coder1 AI", "Coder1 Non-AI")), pd.Series(np.where(s2 == 1, "Coder2 AI", "Coder2 Non-AI")))
    cb.to_csv(res / "coder_confusion_binary.csv")
    ci = pd.crosstab(pd.Series(a1, name="coder1_intensity"), pd.Series(a2, name="coder2_intensity")).reindex(index=range(4), columns=range(4), fill_value=0)
    ci.to_csv(res / "coder_confusion_intensity.csv")

    # per-test agreement: which evidence test drives inconsistency
    trows = []
    for t in P.TEST_COLS:
        x1, x2 = m[t + "_1"].to_numpy(), m[t + "_2"].to_numpy()
        trows.append({"test": t, "raw_agreement": float((x1 == x2).mean()), "cohens_kappa": P.cohen_kappa(x1, x2), "disagree_n": int((x1 != x2).sum())})
    pd.DataFrame(trows).to_csv(res / "coder_test_agreement.csv", index=False)

    # disagreements
    dis = m[a1 != a2].copy()
    dis["i1"], dis["i2"] = dis["ai_intensity_1"].astype(int), dis["ai_intensity_2"].astype(int)
    dd = pd.DataFrame({"company_id": dis["company_id"], "target_name": dis["target_name_1"], "sector": dis["sector_1"],
                       "announcement_date": dis["announcement_date_1"], "i1": dis["i1"], "i2": dis["i2"],
                       "sub1": dis["ai_subsector_1"], "sub2": dis["ai_subsector_2"], "per1": dis["persistence_12m_1"],
                       "per2": dis["persistence_12m_2"], "rat1": dis["rationale_1"], "rat2": dis["rationale_2"],
                       "ce1": dis["counterevidence_notes_1"], "ce2": dis["counterevidence_notes_2"]})
    dd["suggested_category"] = [suggest_category(r) for r in dd.itertuples()]
    dd["strict_flag_disagree"] = ((dd["i1"] >= 2) != (dd["i2"] >= 2)).astype(int)
    dd.to_csv(res / "coder_disagreements.csv", index=False)
    summ = dd.groupby("suggested_category").agg(n=("company_id", "count"), strict_flag_disagreements=("strict_flag_disagree", "sum")).reset_index()
    summ.to_csv(res / "coder_disagreement_summary.csv", index=False)
    if not np.isnan(kb) and kb < P.KAPPA_TARGET:
        by_sec = dd.groupby("sector").size().rename("disagreements").reset_index()
        print("\nKAPPA BELOW TARGET. Disagreements by suggested rule category:\n" + summ.to_string(index=False))
        print("\nBy sector:\n" + by_sec.to_string(index=False))
        print("\nPer-test agreement:\n" + pd.DataFrame(trows).to_string(index=False))
        print("\nRefine docs/ai_rubric.md for the dominant category and re-code BEFORE any valuation analysis.")

    # ---- adjudication file ----------------------------------------------------------------------------
    adj_path = root / "data_clean" / "ai_coding_adjudicated.csv"
    ids = sorted(set(m["company_id"]) | single, key=lambda x: int(x))
    raw1, raw2 = k1.set_index("company_id"), k2.set_index("company_id")
    sugg = dict(zip(dd["company_id"], dd["suggested_category"]))
    new_rows = []
    existing = pd.read_csv(adj_path, dtype=str, keep_default_na=False) if adj_path.exists() else pd.DataFrame(columns=ADJ_COLS)
    have = set(existing["company_id"])
    for cid in ids:
        if cid in have:
            continue
        r1 = raw1.loc[cid] if cid in raw1.index else None
        r2 = raw2.loc[cid] if cid in raw2.index else None
        i1 = int(r1["ai_intensity"]) if r1 is not None else ""
        i2 = int(r2["ai_intensity"]) if r2 is not None else ""
        base = r1 if r1 is not None else r2
        row = {c: "" for c in ADJ_COLS}
        row.update(company_id=cid, target_name=base["target_name"], sector=base["sector"], announcement_date=base["announcement_date"],
                   coder1_intensity=i1, coder2_intensity=i2, coders_agree_intensity=int(i1 == i2) if i1 != "" and i2 != "" else 0,
                   suggested_disagreement_category=sugg.get(cid, ""), adjudication_status="pending")
        if auto_accept and i1 != "" and i1 == i2 and i1 in (0, 1):    # intensity 2/3 always need a manual final review
            row.update(final_intensity=i1, adjudication_reason="coders_agree_auto_accepted", adjudication_status="done",
                       final_confidence=r1["confidence"], adjudicator_id="auto",
                       final_product_test=r1["product_test"], final_technical_asset_test=r1["technical_asset_test"],
                       final_revenue_test=r1["revenue_test"], final_persistence_12m=r1["persistence_12m"],
                       acquihire_ai_flag=r1["acquihire_ai_flag"], company_founded_year=r1["company_founded_year"],
                       commercial_maturity=r1["commercial_maturity"], evidence_source_ids=r1["evidence_source_ids"])
        new_rows.append(row)
    adj = pd.concat([existing, pd.DataFrame(new_rows, columns=ADJ_COLS)], ignore_index=True)[ADJ_COLS]
    adj.to_csv(adj_path, index=False)

    # validate adjudication (never allow raw coder values to be altered)
    aerr = []
    for r in adj.itertuples():
        cid = r.company_id
        for k, raw in (("coder1_intensity", raw1), ("coder2_intensity", raw2)):
            exp = str(int(raw.loc[cid, "ai_intensity"])) if cid in raw.index else ""
            if str(getattr(r, k)) != exp:
                aerr.append({"company_id": cid, "error": f"{k} differs from raw coder file (raw fields are immutable)"})
        if r.adjudication_status == "done":
            fi = pd.to_numeric(r.final_intensity, errors="coerce")
            if fi not in (0, 1, 2, 3):
                aerr.append({"company_id": cid, "error": "final_intensity invalid"}); continue
            if not r.adjudication_reason.strip():
                aerr.append({"company_id": cid, "error": "adjudication_reason required"})
            if r.final_confidence not in P.CONFIDENCE:
                aerr.append({"company_id": cid, "error": "final_confidence invalid"})
            if r.coders_agree_intensity == "0" and r.disagreement_category.strip() == "" and r.coder1_intensity != "" and r.coder2_intensity != "":
                aerr.append({"company_id": cid, "error": "disagreement_category required where coders disagree"})
            if fi >= 2:
                if pd.to_numeric(r.final_subsector, errors="coerce") not in P.SUBSECTORS:
                    aerr.append({"company_id": cid, "error": "final_subsector required for intensity >= 2"})
                if str(r.strict_ai_review_done) != "1":
                    aerr.append({"company_id": cid, "error": "strict_ai_review_done must be 1 for every intensity 2/3 target"})
                if not r.evidence_source_ids.strip():
                    aerr.append({"company_id": cid, "error": "evidence_source_ids required for strict AI"})
    pd.DataFrame(aerr, columns=["company_id", "error"]).to_csv(res / "adjudication_errors.csv", index=False)
    st = adj["adjudication_status"].value_counts().rename_axis("status").rename("n").reset_index()
    st.to_csv(res / "adjudication_status.csv", index=False)
    print(f"double-coded: {n} | kappa(binary strict): {kb:.3f} | weighted kappa: {wq:.3f} | adjudication rows: {len(adj)} "
          f"| pending: {int((adj['adjudication_status'] != 'done').sum())} | adjudication errors: {len(aerr)}")
    return 1 if aerr else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--auto-accept-agreed", action="store_true",
                    help="auto-fill final labels for rows where both coders agree on intensity 0 or 1 (never for 2/3)")
    a = ap.parse_args()
    sys.exit(main(U.project_root(a.root), a.auto_accept_agreed))
