"""Phase 3, step D: final treatment variables, descriptive classification counts, audits, power update, freeze.

Reads (blinded): deals_stage2.csv through the whitelist loader (no valuation column is ever loaded),
                 ai_coding_adjudicated.csv, nlp_scores.csv, docs/ai_classification_sources.csv, agreement/NLP result files.
Writes: data_clean/ai_classifications_final.csv, ai_non_candidate_audit.csv, [ai_treatment_frozen_V1.csv on freeze]
        results/ai_counts_*.csv, ai_intensity_distribution.csv, ai_subsector_distribution.csv, classification_stability.csv,
                common_support_precheck.csv, sparse_cells.csv, power_reassessment.csv, leakage_check.csv,
                temporal_check.csv, gate_report.csv, classification_audit*.csv
        docs/ai_edge_cases.csv, docs/ai_classification_model_card.md, docs/AI_CLASSIFICATION_V1_<date>.json (freeze)

NO valuation multiple, premium, price or EV is read, computed, tabulated or compared by AI status in this script.

Modes:  (default) build everything and evaluate the decision gate
        --make-audit    draw the one-time random re-audit sample (10% of strict AI, 5% of non-AI), blind to prior labels
        --freeze        write the frozen treatment file + manifest, ONLY if the decision gate passes
        --verify-freeze check the frozen file against its recorded checksum (use at the start of Phase 4/5)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_common as P  # noqa: E402
import utils as U  # noqa: E402

TIER_RANK = {"A": 1, "B": 2, "C": 3, "D": 4}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_ids(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;,|]", str(s)) if x.strip()]


def source_evidence(adj: pd.DataFrame, src: pd.DataFrame) -> pd.DataFrame:
    """Per adjudicated company: usable sources, best tier, pre-announcement source, temporal violations."""
    rows = []
    src = src.copy()
    src["source_date"] = pd.to_datetime(src["source_date"], errors="coerce")
    src["used"] = pd.to_numeric(src.get("used_for_classification", 1), errors="coerce").fillna(1).astype(int)
    for r in adj.itertuples():
        ids = parse_ids(r.evidence_source_ids)
        s = src[(src["company_id"].astype(str) == str(r.company_id)) & (src["source_id"].astype(str).isin(ids))]
        ann = pd.to_datetime(r.announcement_date, errors="coerce")
        used = s[s["used"] == 1]
        viol = used[(used["source_date"] > ann) | used["source_date"].isna()]
        tierD = used[used["source_tier"].astype(str).str.upper() == "D"]
        good = used[(used["source_date"] <= ann) & (used["source_tier"].astype(str).str.upper() != "D")]
        tiers = [TIER_RANK.get(str(t).upper(), 9) for t in good["source_tier"]]
        rows.append({"company_id": r.company_id, "n_ids_listed": len(ids), "n_sources_found": len(s), "n_supporting_sources": len(good),
                     "has_preannouncement_source": int(len(good) > 0), "best_source_tier": ({1: "A", 2: "B", 3: "C"}.get(min(tiers)) if tiers else ""),
                     "has_tier_A_or_B": int(any(t <= 2 for t in tiers)), "n_temporal_violations": len(viol), "n_tierD_used": len(tierD)})
    return pd.DataFrame(rows)


def subsector_group(final_ai: pd.DataFrame) -> dict:
    counts = final_ai.assign(g=final_ai["ai_subsector"].map(P.PLANNED_GROUPS)).groupby("g").size()
    return {g: (g if counts.get(g, 0) >= P.MIN_GROUP_N else "Other AI") for g in set(P.PLANNED_GROUPS.values())}


def count_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    g = df.groupby(by, dropna=False)
    t = pd.DataFrame({"strict_AI": g["is_strict"].sum(), "AI_enabled_only(intensity1)": g["is_enabled"].sum(),
                      "non_AI_human_coded": g["is_nonai_human"].sum(), "non_AI_assumed_from_screen": g["is_nonai_assumed"].sum(),
                      "pending_or_unclassified": g["is_unclass"].sum()}).reset_index()
    cl = t["strict_AI"] + t["AI_enabled_only(intensity1)"] + t["non_AI_human_coded"] + t["non_AI_assumed_from_screen"]
    t["classified_N"] = cl
    t["strict_AI_share"] = np.where(cl > 0, t["strict_AI"] / cl, np.nan)
    t["broad_AI_N"] = t["strict_AI"] + t["AI_enabled_only(intensity1)"]
    return t


def main(root: Path, make_audit: bool, do_freeze: bool, verify: bool, date: str) -> int:
    res, dc, docs = root / "results", root / "data_clean", root / "docs"
    res.mkdir(exist_ok=True)
    version = f"AI_CLASSIFICATION_V1_{date}"
    if verify:
        mf = sorted(docs.glob("AI_CLASSIFICATION_V1_*.json"))
        if not mf:
            print("No freeze manifest found."); return 2
        m = json.loads(mf[-1].read_text())
        ok = sha256(dc / m["frozen_file"]) == m["frozen_file_sha256"]
        ok_r = sha256(docs / "ai_rubric.md") == m["rubric_sha256"]
        print(f"{m['version']}: frozen file {'INTACT' if ok else 'MODIFIED'}; rubric {'INTACT' if ok_r else 'MODIFIED'}")
        return 0 if ok and ok_r else 1

    deals = P.load_blinded_deals(root)
    struct = (deals["in_period"] == 1) & (deals["primary_sector"] == 1) & (deals["primary_geography"] == 1) & (deals["control_deal"] == 1) & \
             (deals["status_primary_sample"] == 1) & deals["structural_exclusion"].isna()
    d = deals[struct].copy()
    adj_p = dc / "ai_coding_adjudicated.csv"
    adj = pd.read_csv(adj_p, dtype=str, keep_default_na=False) if adj_p.exists() else pd.DataFrame(columns=["company_id", "adjudication_status"])
    adj["company_id_i"] = pd.to_numeric(adj["company_id"], errors="coerce")
    done = adj[adj["adjudication_status"] == "done"].copy()
    src_p = docs / "ai_classification_sources.csv"
    src = pd.read_csv(src_p, dtype=str, keep_default_na=False) if src_p.exists() else pd.DataFrame(columns=["company_id", "source_id", "source_date", "source_tier"])
    ev = source_evidence(done, src) if len(done) else pd.DataFrame(columns=["company_id"])
    ev["company_id_i"] = pd.to_numeric(ev["company_id"], errors="coerce")

    # ---- per-deal classification ---------------------------------------------------------------------------
    dn = done.set_index("company_id_i")
    pending_ids = set(adj.loc[adj["adjudication_status"] != "done", "company_id_i"])
    status = []
    for r in d.itertuples():
        if r.has_description_text != 1:
            status.append("no_description_unclassified")
        elif r.target_id in dn.index:
            status.append("human_adjudicated")
        elif r.target_id in pending_ids or r.ai_candidate_flag == 1:
            status.append("pending_adjudication")
        else:
            status.append("screen_negative_assumed_non_ai")
    d["ai_class_source"] = status
    h = d["ai_class_source"] == "human_adjudicated"
    a = dn.reindex(d["target_id"])
    a.index = d.index
    fi = pd.to_numeric(a["final_intensity"], errors="coerce")
    alt = pd.to_numeric(a["alt_intensity"], errors="coerce")
    d["ai_intensity"] = np.where(h, fi, np.where(d["ai_class_source"] == "screen_negative_assumed_non_ai", 0, np.nan))
    d["ai_flag_strict"] = np.where(d["ai_intensity"].notna(), (d["ai_intensity"] >= 2).astype(float), np.nan)
    d["ai_flag_broad"] = np.where(d["ai_intensity"].notna(), (d["ai_intensity"] >= 1).astype(float), np.nan)
    d["ai_subsector"] = np.where(h & (fi >= 2), pd.to_numeric(a["final_subsector"], errors="coerce"), np.nan)
    d["ai_secondary_subsector"] = np.where(h & (fi >= 2), pd.to_numeric(a["final_secondary_subsector"], errors="coerce"), np.nan)
    d["ai_subsector_name"] = d["ai_subsector"].map(P.SUBSECTORS)
    grp = subsector_group(d[d["ai_flag_strict"] == 1]) if (d["ai_flag_strict"] == 1).any() else {}
    d["ai_subsector_group"] = d["ai_subsector"].map(P.PLANNED_GROUPS).map(grp)
    d["ai_class_confidence"] = np.where(h, a["final_confidence"], np.where(d["ai_class_source"] == "screen_negative_assumed_non_ai", "Assumed", None))
    both = np.where(h, pd.to_numeric(a["coders_agree_intensity"], errors="coerce"), np.nan)
    d["coder_agreement"] = both
    d["adjudicated"] = np.where(h, (pd.to_numeric(a["coders_agree_intensity"], errors="coerce") == 0).astype(float), np.nan)
    d["persistence_12m"] = np.where(h, pd.to_numeric(a["final_persistence_12m"], errors="coerce"), np.nan)
    d["persistence_not_testable"] = np.where(h, pd.to_numeric(a["persistence_not_testable"], errors="coerce").fillna(0), np.nan)
    d["acquihire_ai_flag"] = np.where(h, pd.to_numeric(a["acquihire_ai_flag"], errors="coerce").fillna(0), np.nan)
    d["company_founded_year"] = np.where(h, pd.to_numeric(a["company_founded_year"], errors="coerce"), np.nan)
    d["ai_company_vintage"] = d["company_founded_year"].map(P.vintage_of)
    d["commercial_maturity"] = np.where(h, a["commercial_maturity"].where(a["commercial_maturity"].isin(P.MATURITY)), None)
    d["counterevidence_notes"] = np.where(h, a["counterevidence_notes"], "")
    d["ai_alt_intensity"] = np.where(h & alt.notna(), alt, np.where(h, fi, np.nan))
    d["ai_conservative_intensity"] = np.where(h, np.fmin(fi, d["ai_alt_intensity"]), d["ai_intensity"])
    d["ai_liberal_intensity"] = np.where(h, np.fmax(fi, d["ai_alt_intensity"]), d["ai_intensity"])
    d["ai_label_is_assumed"] = (d["ai_class_source"] == "screen_negative_assumed_non_ai").astype(int)
    d["ai_label_ambiguous"] = (h & (d["ai_alt_intensity"] != fi)).astype(int)
    d = d.merge(ev.drop(columns=["company_id"], errors="ignore").rename(columns={"company_id_i": "target_id"}), on="target_id", how="left")
    nlp_p = dc / "nlp_scores.csv"
    if nlp_p.exists():
        d = d.merge(pd.read_csv(nlp_p)[["deal_id", "ai_nlp_score", "nlp_flag", "ai_embedding_score"]], on="deal_id", how="left")
    else:
        d["ai_nlp_score"], d["nlp_flag"], d["ai_embedding_score"] = np.nan, np.nan, np.nan
    # strict-label evidence completeness (Phase 3 s.36) and temporal check (s.56)
    strict = d["ai_flag_strict"] == 1
    d["strict_evidence_complete"] = np.where(strict, ((d["has_preannouncement_source"] == 1) & (d["n_supporting_sources"] >= 1)).astype(float), np.nan)
    d["strict_single_source_flag"] = np.where(strict, (d["n_supporting_sources"] < 2).astype(float), np.nan)
    d["strict_no_tierAB_flag"] = np.where(strict, (d["has_tier_A_or_B"] != 1).astype(float), np.nan)
    d["is_strict"] = (d["ai_flag_strict"] == 1)
    d["is_enabled"] = (d["ai_intensity"] == 1)
    d["is_nonai_human"] = (d["ai_intensity"] == 0) & h
    d["is_nonai_assumed"] = d["ai_label_is_assumed"] == 1
    d["is_unclass"] = d["ai_intensity"].isna()
    d["announce_era"] = np.where(d["announcement_date"] > U.GENAI_DATE, "Post-30-Nov-2022", "Pre-30-Nov-2022")
    d["target_type"] = np.where(d["public_target"] == 1, "Public", "Private")

    keep = ["deal_id", "target_id", "target_name", "announcement_date", "announce_year", "sector_primary", "target_region", "target_type",
            "ai_class_source", "ai_flag_strict", "ai_flag_broad", "ai_intensity", "ai_subsector", "ai_subsector_name", "ai_secondary_subsector",
            "ai_subsector_group", "ai_nlp_score", "nlp_flag", "ai_embedding_score", "ai_class_confidence", "coder_agreement", "adjudicated",
            "persistence_12m", "persistence_not_testable", "acquihire_ai_flag", "company_founded_year", "ai_company_vintage", "commercial_maturity",
            "ai_conservative_intensity", "ai_liberal_intensity", "ai_label_is_assumed", "ai_label_ambiguous", "n_supporting_sources",
            "has_preannouncement_source", "best_source_tier", "strict_evidence_complete", "strict_single_source_flag", "strict_no_tierAB_flag",
            "counterevidence_notes"]
    for c in keep:
        if c not in d.columns:
            d[c] = np.nan
    P.assert_no_valuation_columns(keep)
    d[keep].to_csv(dc / "ai_classifications_final.csv", index=False)

    # ---- counts (descriptive prevalence only; no valuation outcomes anywhere) --------------------------------------
    count_table(d, "announce_year").to_csv(res / "ai_counts_year.csv", index=False)
    count_table(d, "sector_primary").to_csv(res / "ai_counts_sector.csv", index=False)
    count_table(d, "target_region").to_csv(res / "ai_counts_region.csv", index=False)
    count_table(d, "target_type").to_csv(res / "ai_counts_public_private.csv", index=False)
    count_table(d, "announce_era").to_csv(res / "ai_counts_genai.csv", index=False)
    classified = d[d["ai_intensity"].notna()]
    ci = classified["ai_intensity"].value_counts().reindex([0, 1, 2, 3], fill_value=0).rename_axis("intensity").rename("N").reset_index()
    ci["pct"] = ci["N"] / max(1, ci["N"].sum())
    ci["label"] = ci["intensity"].map(P.INTENSITY_LABELS)
    ci["note"] = ["incl. assumed from keyword-screen negatives" if i == 0 else "" for i in ci["intensity"]]
    ci.to_csv(res / "ai_intensity_distribution.csv", index=False)
    sa = d[d["is_strict"]]
    sd = sa["ai_subsector_name"].value_counts().rename_axis("subsector").rename("N").reset_index()
    sd["pct"] = sd["N"] / max(1, sd["N"].sum())
    sd.to_csv(res / "ai_subsector_distribution.csv", index=False)
    sa["ai_subsector_group"].value_counts().rename_axis("group").rename("N").reset_index().to_csv(res / "ai_subsector_groups.csv", index=False)
    cf = classified[classified["ai_class_confidence"].isin(P.CONFIDENCE + ["Assumed"])]
    cf.groupby("ai_class_confidence").agg(AI_N=("is_strict", "sum"), nonAI_N=("is_strict", lambda s: int((~s).sum()))).reset_index().to_csv(res / "ai_counts_confidence.csv", index=False)
    pers = sa.agg(n_strict=("is_strict", "sum"), n_persist=("persistence_12m", "sum"), n_not_testable=("persistence_not_testable", "sum"))
    pd.DataFrame([{"strict_AI_N": int(len(sa)), "persistence_12m_documented_N": int((sa["persistence_12m"] == 1).sum()),
                   "pct_strict_with_persistence": float((sa["persistence_12m"] == 1).mean()) if len(sa) else np.nan,
                   "persistence_not_testable_N": int((sa["persistence_not_testable"] == 1).sum()),
                   "strict_without_persistence_and_testable_N(review)": int(((sa["persistence_12m"] != 1) & (sa["persistence_not_testable"] != 1)).sum())}]
                 ).to_csv(res / "ai_persistence_summary.csv", index=False)

    # ---- stability under reasonable alternative decisions ------------------------------------------------------------
    hs = d[d["ai_class_source"] == "human_adjudicated"]
    base = (hs["ai_intensity"] >= 2)
    cons, lib = (hs["ai_conservative_intensity"] >= 2), (hs["ai_liberal_intensity"] >= 2)
    bbase, bcons, blib = (hs["ai_intensity"] >= 1), (hs["ai_conservative_intensity"] >= 1), (hs["ai_liberal_intensity"] >= 1)
    pd.DataFrame([
        {"definition": "strict", "conservative_N": int(cons.sum()), "primary_N": int(base.sum()), "liberal_N": int(lib.sum()),
         "labels_changed_conservative": int((cons != base).sum()), "labels_changed_liberal": int((lib != base).sum())},
        {"definition": "broad", "conservative_N": int(bcons.sum()), "primary_N": int(bbase.sum()), "liberal_N": int(blib.sum()),
         "labels_changed_conservative": int((bcons != bbase).sum()), "labels_changed_liberal": int((blib != bbase).sum())}]
    ).to_csv(res / "classification_stability.csv", index=False)

    # ---- balance / common-support pre-check (covariates only; no outcome) ------------------------------------------------
    cs = classified.copy()
    cs["year_bucket"] = pd.cut(cs["announce_year"], [2014, 2018, 2021, 2026], labels=["2015-18", "2019-21", "2022-26"]).astype(str)
    cell = cs.groupby(["year_bucket", "sector_primary", "target_region"]).agg(AI=("is_strict", "sum"), nonAI=("is_strict", lambda s: int((~s).sum()))).reset_index()
    cell["only_AI"], cell["only_nonAI"] = (cell["nonAI"] == 0) & (cell["AI"] > 0), (cell["AI"] == 0) & (cell["nonAI"] > 0)
    cell["sparse(<3 total)"] = (cell["AI"] + cell["nonAI"]) < 3
    cell.to_csv(res / "sparse_cells.csv", index=False)
    ai_tot, na_tot = int(cell["AI"].sum()), int(cell["nonAI"].sum())
    sup = []
    sup.append({"check": "year_bucket x sector x region cells", "value": len(cell)})
    sup.append({"check": "cells with only AI", "value": int(cell["only_AI"].sum())})
    sup.append({"check": "AI deals in cells with >=1 non-AI (common-support share)", "value": float(cell.loc[cell["nonAI"] > 0, "AI"].sum() / ai_tot) if ai_tot else np.nan})
    sup.append({"check": "non-AI deals in cells with >=1 AI", "value": float(cell.loc[cell["AI"] > 0, "nonAI"].sum() / na_tot) if na_tot else np.nan})
    ins = cs[(cs["in_primary_sample_evrev"] == 1) & cs["revenue_ltm_usd"].notna()].copy()
    if len(ins) >= 10 and ins["is_strict"].any() and (~ins["is_strict"]).any():
        for var in ("revenue_ltm_usd", "revenue_growth", "ebitda_margin"):
            v = ins[ins[var].notna()]
            if v["is_strict"].any() and (~v["is_strict"]).any():
                lo, hi = v.loc[~v["is_strict"], var].quantile([0.05, 0.95])
                sup.append({"check": f"share of AI deals with {var} inside non-AI P5-P95", "value": float(v.loc[v["is_strict"], var].between(lo, hi).mean())})
    pd.DataFrame(sup).to_csv(res / "common_support_precheck.csv", index=False)

    # ---- power reassessment (counts + ASSUMED residual SD; no observed outcome used) --------------------------------------
    pw = []
    ins_all = cs[(cs["in_primary_sample_evrev"] == 1)]
    n1, n0 = int(ins_all["is_strict"].sum()), int((~ins_all["is_strict"]).sum())
    z = 1.645 + 0.84
    for sd_ in (0.7, 0.9):
        if n1 and n0:
            se = sd_ * np.sqrt(1 / n1 + 1 / n0)
            pw.append({"test": "EV/Revenue AI main effect (ln)", "n_AI": n1, "n_nonAI": n0, "assumed_resid_sd": sd_, "SE": se, "MDE_log_points": z * se, "MDE_pct": np.exp(z * se) - 1})
    pp = cs[cs["in_primary_sample_premium"] == 1]
    m1, m0 = int(pp["is_strict"].sum()), int((~pp["is_strict"]).sum())
    if m1 and m0:
        se = 0.25 * np.sqrt(1 / m1 + 1 / m0)
        pw.append({"test": "Takeover premium AI main effect (pp)", "n_AI": m1, "n_nonAI": m0, "assumed_resid_sd": 0.25, "SE": se, "MDE_log_points": np.nan, "MDE_pct": z * se})
    for name, col in (("AI x Strategic", "strategic_buyer"), ("AI x PostGenAI", "post_genai"), ("AI x Public", "public_target")):
        c4 = [int(((ins_all["is_strict"]) & (ins_all[col] == g)).sum()) for g in (1, 0)] + [int((~ins_all["is_strict"] & (ins_all[col] == g)).sum()) for g in (1, 0)]
        if min(c4) > 0:
            for sd_ in (0.7, 0.9):
                se = sd_ * np.sqrt(sum(1 / c for c in c4))
                pw.append({"test": name + " interaction (ln EV/Rev)", "n_AI": c4[0] + c4[1], "n_nonAI": c4[2] + c4[3], "cells(AI1,AI0,non1,non0)": "/".join(map(str, c4)),
                           "assumed_resid_sd": sd_, "SE": se, "MDE_log_points": z * se, "MDE_pct": np.exp(z * se) - 1})
        else:
            pw.append({"test": name + " interaction", "note": f"an interaction cell is empty {c4}; not estimable"})
    pw.append({"test": "Phase 1 target", "note": f"strict AI N in EV/Rev sample = {n1} vs target 60" + (" -> REDUCED POWER (do not broaden the definition)" if n1 < 60 else "")})
    pd.DataFrame(pw).to_csv(res / "power_reassessment.csv", index=False)

    # ---- non-candidate audit file ---------------------------------------------------------------------------------------
    key_p = dc / "ai_coding_pool_key.csv"
    if key_p.exists():
        key = pd.read_csv(key_p)
        aud = key[key["coding_pool"] == "audit_random_20pct"].merge(d[["deal_id", "ai_class_source", "ai_intensity", "ai_flag_strict"]], on="deal_id", how="left")
        aud["false_negative_of_keyword_screen"] = (aud["ai_flag_strict"] == 1).astype(int)
        aud[["deal_id", "target_id", "candidate_keyword_hits", "ai_class_source", "ai_intensity", "ai_flag_strict", "false_negative_of_keyword_screen"]].to_csv(dc / "ai_non_candidate_audit.csv", index=False)

    # ---- edge-case register ----------------------------------------------------------------------------------------------
    ec_p = docs / "ai_edge_cases.csv"
    ec_cols = ["company_id", "company", "final_class", "alternative_class", "reason_ambiguous", "evidence_for", "evidence_against", "adjudication"]
    ec_old = pd.read_csv(ec_p, dtype=str, keep_default_na=False) if ec_p.exists() else pd.DataFrame(columns=ec_cols)
    new = []
    for r in done.itertuples():
        f_ = pd.to_numeric(r.final_intensity, errors="coerce")
        alt_ = pd.to_numeric(r.alt_intensity, errors="coerce")
        edge = (r.coders_agree_intensity == "0") or (pd.notna(alt_) and alt_ != f_) or r.final_confidence == "Low" or str(r.acquihire_ai_flag) == "1"
        if edge and str(r.company_id) not in set(ec_old["company_id"]):
            new.append({"company_id": r.company_id, "company": r.target_name, "final_class": f"{int(f_)} {P.INTENSITY_LABELS[int(f_)]}",
                        "alternative_class": "" if pd.isna(alt_) else f"{int(alt_)} {P.INTENSITY_LABELS[int(alt_)]}",
                        "reason_ambiguous": r.disagreement_category or ("low confidence" if r.final_confidence == "Low" else ""),
                        "evidence_for": r.adjudication_reason, "evidence_against": r.counterevidence_notes, "adjudication": f"coder1={r.coder1_intensity}, coder2={r.coder2_intensity}, final={int(f_)}"})
    pd.concat([ec_old, pd.DataFrame(new, columns=ec_cols)], ignore_index=True).to_csv(ec_p, index=False)

    # ---- random re-audit (one-time draw; blind to prior labels) ------------------------------------------------------------
    aud_s, aud_k = res / "classification_audit_sample.csv", dc / "audit_key.csv"
    if make_audit:
        if aud_s.exists():
            print("Audit sample already drawn; not redrawing (the draw is one-time to avoid selective auditing).")
        else:
            rng = np.random.default_rng(U.SEED + 99)
            ai_ids = d.loc[d["is_strict"] & h, "deal_id"].to_numpy()
            nai_ids = d.loc[(d["ai_flag_strict"] == 0), "deal_id"].to_numpy()
            pick = lambda arr, f: list(rng.choice(arr, size=max(1, int(np.ceil(f * len(arr)))), replace=False)) if len(arr) else []
            sel = pick(ai_ids, P.AUDIT_FRAC_AI) + pick(nai_ids, P.AUDIT_FRAC_NONAI)
            sel = list(rng.permutation(sel))
            desc = pd.read_csv(root / "data_raw" / "descriptions_raw.csv", dtype=str, keep_default_na=False).set_index("deal_id")
            tid = d.set_index("deal_id")["target_id"]
            samp = pd.DataFrame({"audit_row": range(1, len(sel) + 1), "company_id": [int(tid[x]) for x in sel],
                                 "description_text": [U.redact_valuation(desc.loc[x, "target_description"]) if x in desc.index else "" for x in sel],
                                 "historical_description": [U.redact_valuation(desc.loc[x, "historical_description"]) if x in desc.index else "" for x in sel],
                                 "audit_intensity": "", "audit_rationale": "", "auditor_id": ""})
            samp.to_csv(aud_s, index=False)
            d.set_index("deal_id").loc[sel, ["ai_flag_strict", "ai_intensity"]].reset_index().assign(audit_row=range(1, len(sel) + 1)).to_csv(aud_k, index=False)
            print(f"audit sample drawn: {len(sel)} targets -> results/classification_audit_sample.csv (labels hidden; key in data_clean/audit_key.csv)")
    audit_status = "not drawn"
    audit_err = np.nan
    if aud_s.exists() and aud_k.exists():
        s_ = pd.read_csv(aud_s, dtype=str, keep_default_na=False)
        k_ = pd.read_csv(aud_k)
        done_a = s_[s_["audit_intensity"].str.strip() != ""]
        if len(done_a) == len(s_) and len(s_):
            mm = s_.assign(audit_row=pd.to_numeric(s_["audit_row"])).merge(k_, on="audit_row")
            mm["audit_strict"] = (pd.to_numeric(mm["audit_intensity"]) >= 2).astype(int)
            mm["error"] = (mm["audit_strict"] != mm["ai_flag_strict"]).astype(int)
            audit_err = float(mm["error"].mean())
            out = mm.groupby("ai_flag_strict").agg(n=("error", "size"), errors=("error", "sum")).reset_index()
            out.loc[len(out)] = ["all", len(mm), int(mm["error"].sum())]
            out["error_rate"] = out["errors"] / out["n"]
            out["note"] = ["EXPAND AUDIT: error rate > 5%" if (r_ > P.AUDIT_ERROR_LIMIT) else "within 5%" for r_ in out["error_rate"]]
            out.to_csv(res / "classification_audit.csv", index=False)
            audit_status = "complete"
        else:
            audit_status = f"in progress ({len(done_a)}/{len(s_)} audited)"

    # ---- leakage and temporal checks ---------------------------------------------------------------------------------------
    lk = []
    for f_ in ("leakage_check_pre_coding.csv", "leakage_check_nlp.csv"):
        if (res / f_).exists():
            lk.append(pd.read_csv(res / f_))
    lk.append(pd.DataFrame([{"check": "phase3_scripts_load_only_whitelisted_non_valuation_deal_columns", "result": "PASS", "detail": "enforced by assert_no_valuation_columns()"},
                            {"check": "final_treatment_file_has_no_valuation_columns", "result": "PASS", "detail": ""}]))
    leak = pd.concat(lk, ignore_index=True)
    leak.to_csv(res / "leakage_check.csv", index=False)
    leak_pass = bool((leak["result"] == "PASS").all()) and len(lk) >= 2
    tv = int(ev["n_temporal_violations"].sum()) if "n_temporal_violations" in ev.columns else 0
    t4 = int(ev["n_tierD_used"].sum()) if "n_tierD_used" in ev.columns else 0
    pd.DataFrame([{"check": "sources_used_for_classification_dated_after_announcement", "violations": tv, "result": "PASS" if tv == 0 else "FAIL"},
                  {"check": "tier_D_sources_used_for_classification", "violations": t4, "result": "PASS" if t4 == 0 else "FAIL"}]).to_csv(res / "temporal_check.csv", index=False)

    # ---- decision gate (Phase 3 s.66) ---------------------------------------------------------------------------------------
    gate = []
    ag_p = res / "coder_agreement.csv"
    kb = np.nan
    if ag_p.exists():
        ag = pd.read_csv(ag_p).set_index("metric")
        kb = float(ag.loc["binary_strict_cohens_kappa", "value"])
    gate.append(("coder kappa (binary strict) >= 0.70", not np.isnan(kb) and kb >= P.KAPPA_TARGET, f"kappa={kb}"))
    rec = np.nan
    if (res / "nlp_performance.csv").exists():
        np_ = pd.read_csv(res / "nlp_performance.csv")
        r_ = np_[np_["evaluation"] == "candidate_screen_recall_estimate"]
        rec = float(r_["recall"].iloc[0]) if len(r_) else np.nan
    gate.append(("candidate-screen recall estimate >= 90%", not np.isnan(rec) and rec >= P.SCREEN_RECALL_TARGET, f"recall={rec}"))
    npend = int((d["ai_class_source"] == "pending_adjudication").sum())
    gate.append(("no pending adjudication", npend == 0 and len(done) > 0, f"pending={npend}"))
    n_strict = int(d["is_strict"].sum())
    inc = int((d.loc[d["is_strict"], "strict_evidence_complete"] != 1).sum())
    gate.append(("every strict-AI target has a pre-announcement source and >=1 supporting source (no NLP-only labels)", inc == 0 and n_strict > 0, f"incomplete={inc}"))
    gate.append(("no sources dated after announcement / no tier-D used", tv == 0 and t4 == 0, f"violations={tv}, tierD={t4}"))
    gate.append(("leakage check PASS", leak_pass, ""))
    gate.append(("random re-audit complete and error rate <= 5%", audit_status == "complete" and not np.isnan(audit_err) and audit_err <= P.AUDIT_ERROR_LIMIT, f"status={audit_status}, error={audit_err}"))
    aerr = res / "adjudication_errors.csv"
    n_aerr = len(pd.read_csv(aerr)) if aerr.exists() else 0
    gate.append(("no adjudication-file validation errors", n_aerr == 0 and aerr.exists(), f"errors={n_aerr}"))
    gdf = pd.DataFrame(gate, columns=["gate_condition", "passed", "detail"])
    gdf.to_csv(res / "gate_report.csv", index=False)
    all_pass = bool(gdf["passed"].all())

    # ---- model card ------------------------------------------------------------------------------------------------------------
    write_model_card(docs / "ai_classification_model_card.md", d, gdf, all_pass, kb, rec, version, audit_status, audit_err, root)

    # ---- freeze ------------------------------------------------------------------------------------------------------------------
    if do_freeze:
        if not all_pass:
            print("FREEZE REFUSED: decision gate not passed:\n" + gdf[~gdf["passed"]].to_string(index=False))
            return 1
        fz_cols = ["deal_id", "target_id", "ai_flag_strict", "ai_flag_broad", "ai_intensity", "ai_subsector", "ai_subsector_group", "ai_class_confidence",
                   "ai_class_source", "ai_label_is_assumed", "acquihire_ai_flag", "ai_conservative_intensity", "ai_liberal_intensity", "ai_company_vintage"]
        fz = d[[c for c in fz_cols if c in d.columns]].sort_values("deal_id")
        fz_name = "ai_treatment_frozen_V1.csv"
        fz.to_csv(dc / fz_name, index=False)
        man = {"version": version, "frozen_on": date, "frozen_file": fz_name, "frozen_file_sha256": sha256(dc / fz_name), "n_rows": int(len(fz)),
               "n_strict_ai": n_strict, "n_broad_ai": int(d["ai_flag_broad"].sum()), "rubric_sha256": sha256(docs / "ai_rubric.md"),
               "nlp_threshold_file_sha256": sha256(res / "nlp_threshold.json") if (res / "nlp_threshold.json").exists() else None,
               "rule": "No label may change after valuation analysis begins unless a factual classification error is found; log every change in deviations_log.md"}
        (docs / f"{version}.json").write_text(json.dumps(man, indent=2))
        print(f"FROZEN: {version} sha256={man['frozen_file_sha256'][:16]}... strict AI N={n_strict}")
    print(f"classified deals: {int(d['ai_intensity'].notna().sum())}/{len(d)} | strict AI: {n_strict} | broad AI: {int(d['ai_flag_broad'].sum())} "
          f"| pending: {npend} | gate: {'PASS' if all_pass else 'NOT PASSED'}")
    if not all_pass:
        print(gdf[~gdf["passed"]].to_string(index=False))
    return 0


def write_model_card(path: Path, d: pd.DataFrame, gdf: pd.DataFrame, all_pass: bool, kb, rec, version, audit_status, audit_err, root: Path) -> None:
    n = len(d)
    cl = int(d["ai_intensity"].notna().sum())
    n_s, n_b = int(d["is_strict"].sum()), int(d["ai_flag_broad"].sum()) if n else 0
    hum = int((d["ai_class_source"] == "human_adjudicated").sum())
    status = "DRAFT: no human coding data present yet; figures below are empty by construction." if hum == 0 else ("FROZEN-READY: decision gate passed." if all_pass else "DRAFT: decision gate NOT passed (see gate_report.csv).")
    L = [f"# AI Classification Model Card ({version})", "", f"**Status:** {status}", "",
         "## Purpose", "Produce the treatment variable for the study 'Is There an AI Acquisition Premium?': whether a target was AI-native at or before its acquisition announcement, constructed without reference to any transaction valuation.", "",
         "## Definition", "`ai_flag_strict = 1` iff final adjudicated intensity >= 2 (AI-native or frontier/core AI infrastructure); `ai_flag_broad = 1` iff intensity >= 1. Rubric: `docs/ai_rubric.md` (hash-pinned at freeze). Four evidence tests (product, technical asset, revenue/commercial, persistence >= 12 months) structure the evidence; the intensity rubric decides.", "",
         "## Input text", "Pre-announcement target text only (target, website, filing, historical descriptions and the announcement-time website snapshot), with money amounts, multiples and price language scrubbed. Buyer announcement language, current websites and post-deal descriptions are not used for classification.", "",
         "## Human coding procedure", "Two independent coders see every pooled row (keyword-screen candidates plus a fixed-seed random 20% sample of non-candidates) in different shuffled orders, and cannot tell which rows are candidates. A third reviewer adjudicates disagreements and manually reviews every intensity 2/3 target against source evidence (>= 1 pre-announcement source required). Raw coder fields are never overwritten.", "",
         "## NLP method", "Transparent dictionary score (fixed category weights; weak terms count only alongside strong terms) plus a TF-IDF (1-2 gram) logistic regression trained on adjudicated labels with a stratified hold-out and out-of-fold scoring; composite = 0.5 dictionary + 0.5 TF-IDF probability. The review threshold is the highest threshold keeping out-of-fold recall >= 95%, recorded in `results/nlp_threshold.json` before Phase 4. An embedding score is optional and not implemented. NLP screens candidates; it never sets a final label.", "",
         "## Performance"]
    npf = root / "results" / "nlp_performance.csv"
    if npf.exists() and npf.stat().st_size > 5:
        L += [pd.read_csv(npf).round(3).to_markdown(index=False) if hasattr(pd.DataFrame, "to_markdown") and _has_tabulate() else pd.read_csv(npf).round(3).to_string(index=False)]
    else:
        L += ["Not yet computed."]
    L += ["", f"Coder agreement: binary strict kappa = {kb if not pd.isna(kb) else 'n/a'}; candidate-screen recall estimate = {rec if not pd.isna(rec) else 'n/a'}. See `results/coder_agreement.csv`, `results/nlp_performance.csv`.", "",
          "## Counts", f"Deals in scope: {n}; classified: {cl} (human-adjudicated: {hum}; assumed non-AI from keyword-screen negatives: {int(d['ai_label_is_assumed'].sum())}); strict AI N = {n_s}; broad AI N = {n_b}.", "",
          "## Known errors", "- Targets that the keyword screen did not flag and the random audit did not sample are assumed non-AI; the false-negative audit estimates how many strict-AI targets this misses.",
          "- Misclassification in the treatment most likely attenuates (biases toward zero) a later AI coefficient; the stability table reports how many labels move under conservative/liberal resolution of ambiguous cases.",
          f"- Random re-audit status: {audit_status}" + ("" if pd.isna(audit_err) else f"; error rate {audit_err:.3f}"), "",
          "## Limitations", "Small coded samples give wide confidence intervals on kappa and recall. Historical evidence for private targets can be thin, so Low-confidence labels are flagged for a later robustness exclusion. Pre-2022 AI uses different vocabulary; the rubric judges product dependence on a trained model, not wording. Acqui-hire detection after coding (`acquihire_ai_flag`) extends the Phase 2 exclusion and is logged in `deviations_log.md`.", "",
          "## Decision gate", gdf.to_string(index=False), "", f"## Version\n{version}"]
    path.write_text("\n".join(L) + "\n")


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
        return True
    except Exception:
        return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--make-audit", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--verify-freeze", action="store_true")
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"))
    a = ap.parse_args()
    sys.exit(main(U.project_root(a.root), a.make_audit, a.freeze, a.verify_freeze, a.date))
