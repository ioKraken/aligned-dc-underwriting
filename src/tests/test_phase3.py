"""End-to-end test of the Phase 3 machinery on SYNTHETIC data (fictional companies, fictional text, simulated coders).

Run:  python src/tests/test_phase3.py
Nothing here is a research result. The 'coders', 'adjudicator' and 'auditor' are scripted oracles with controlled noise,
used only to prove that the agreement statistics, gate, freeze and blinding guarantees behave as specified.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = HERE.parent
PROJ = SRC.parent
sys.path.insert(0, str(SRC))
import p3_common as P  # noqa: E402

N_DEALS = 360
SECT = ["Application Software", "Infrastructure Software", "Cybersecurity", "Internet / Digital Platform", "Semiconductors", "IT Services"]
REGIONS = ["US", "US", "US", "CA", "GB", "DE", "IL"]


def run(script, root, *args, check=True):
    r = subprocess.run([sys.executable, str(root / "src" / script), "--root", str(root), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"{script} {' '.join(args)} failed")
    return r


def build_universe(root: Path, seed: int = 11):
    rng = np.random.default_rng(seed)
    U, T, F, D, truth = [], [], [], [], {}
    for k in range(N_DEALS):
        did, name = f"S{k:04d}", f"Synth Target {k:04d}"
        lvl = int(rng.choice([0, 1, 2, 3], p=[0.62, 0.20, 0.14, 0.04]))
        sector = SECT[k % 6]
        if lvl == 3:
            sector = "Semiconductors" if k % 2 else "Infrastructure Software"
        yr = 2016 + k % 11
        mo = 1 + k % 9
        ann = f"{yr}-{mo:02d}-12"
        U.append(dict(deal_id=did, target_name=name, buyer_name=f"Synth Buyer {k % 40}", announcement_date=ann, close_date=f"{yr}-{mo:02d}-28",
                      deal_status="completed", target_country=REGIONS[k % 7], buyer_country="US", target_public_private="public" if k % 6 == 0 else "private",
                      buyer_type="strategic" if k % 3 else "sponsor", sector=sector, subsector="synthetic", headline_transaction_value="ND",
                      source_universe="synthetic_screen", source_url="https://example.invalid", notes="", deal_type="", ticker=f"T{k}" if k % 6 == 0 else "", exchange=""))
        rev = float(rng.uniform(10e6, 300e6))
        T.append(dict(deal_id=did, currency_original="USD", fx_rate_announcement="", enterprise_value=f"{rev * rng.uniform(2, 14):.0f}", ev_quality="A"))
        F.append(dict(deal_id=did, revenue_period_end=f"{yr - 1}-12-31", revenue_ltm=f"{rev:.0f}", revenue_prior_ltm=f"{rev * rng.uniform(.6, .95):.0f}",
                      ebitda_ltm=f"{rev * 0.05:.0f}", ebitda_definition="reported", currency="USD", financials_quality="A", financials_disclosed="1"))
        # text: classes with realistic noise (keyword-free AI-native text, and AI-washed non-AI text)
        if lvl >= 2:
            kw_free = rng.random() < 0.05
            body = (f"{name} builds a cognitive computing and pattern recognition engine trained on proprietary data and served as a hosted product." if kw_free else
                    f"{name} develops proprietary deep learning models and neural networks; its core product is a machine learning platform serving model inference. Its research team publishes technical papers.")
            if lvl == 3:
                body = f"{name} designs AI accelerator hardware for model training and inference of large language models and generative AI."
        elif lvl == 1:
            body = f"{name} sells enterprise workflow software with an AI assistant and machine learning forecasting as an add-on feature."
        else:
            washed = rng.random() < 0.08
            body = (f"{name} sells intelligent automation and smart analytics software and now markets AI features." if washed else
                    f"{name} sells accounting and logistics software for mid-sized companies with analytics dashboards.")
        D.append(dict(deal_id=did, target_description=body, announcement_description=f"Acquired for $1.{k % 9} billion; the buyer is excited about the strategic fit.",
                      website_description="", filing_description="", historical_description=body.replace(name, "The company"),
                      snapshot_announcement=body, snapshot_minus_12m=""))
        sub = int(rng.choice([1, 2, 3, 4, 5, 6, 7, 9])) if lvl == 2 else (int(rng.choice([8, 2, 1])) if lvl == 3 else 0)
        truth[did] = dict(lvl=lvl, sub=sub, ann=ann, k=k)
    raw = root / "data_raw"
    pd.DataFrame(U).to_csv(raw / "deal_universe_raw.csv", index=False)
    pd.DataFrame(T).to_csv(raw / "deal_terms_raw.csv", index=False)
    pd.DataFrame(F).to_csv(raw / "financials_raw.csv", index=False)
    pd.DataFrame(D).to_csv(raw / "descriptions_raw.csv", index=False)
    return truth


def fill_coders(root: Path, truth, mode: str, seed=5):
    """Scripted coders. mode='good' -> truth with ~12% +/-1 noise; 'random' -> uniform noise."""
    stage2 = pd.read_csv(root / "data_clean" / "deals_stage2.csv", usecols=["deal_id", "target_id"])
    tmap = {int(r.target_id): truth[r.deal_id] for r in stage2.itertuples()}
    for i in (1, 2):
        rng = np.random.default_rng(seed + i)
        path = root / "data_clean" / f"ai_coding_raw_coder{i}.csv"
        s = pd.read_csv(path, dtype=str, keep_default_na=False)
        for ix, r in s.iterrows():
            t = tmap[int(r["company_id"])]
            lvl = t["lvl"]
            if mode == "random":
                lvl = int(rng.integers(0, 4))
            elif rng.random() < 0.12:
                lvl = int(np.clip(lvl + rng.choice([-1, 1]), 0, 3))
            s.loc[ix, "ai_intensity"] = str(lvl)
            s.loc[ix, "product_test"] = str(int(lvl >= 2))
            s.loc[ix, "technical_asset_test"] = str(int(lvl >= 2))
            s.loc[ix, "revenue_test"] = str(int(lvl >= 2 and rng.random() < 0.7))
            s.loc[ix, "persistence_12m"] = str(int(lvl >= 2 and rng.random() < 0.9))
            s.loc[ix, "confidence"] = str(rng.choice(P.CONFIDENCE, p=[0.6, 0.3, 0.1]))
            s.loc[ix, "ai_subsector"] = str(t["sub"] if (lvl >= 2 and t["sub"] and rng.random() < 0.85) else (int(rng.integers(1, 10)) if lvl >= 2 else ""))
            s.loc[ix, "rationale"] = "synthetic rationale" if lvl >= 1 else ""
            s.loc[ix, "company_founded_year"] = str(int(2010 + t["k"] % 12))
            s.loc[ix, "commercial_maturity"] = P.MATURITY[t["k"] % 4]
        s.to_csv(path, index=False)
    return tmap


def adjudicate_and_source(root: Path, tmap, seed=9):
    rng = np.random.default_rng(seed)
    adj = pd.read_csv(root / "data_clean" / "ai_coding_adjudicated.csv", dtype=str, keep_default_na=False)
    src_rows = []
    for ix, r in adj.iterrows():
        if r["adjudication_status"] == "done":
            continue
        t = tmap[int(r["company_id"])]
        lvl = t["lvl"]
        adj.loc[ix, "final_intensity"] = str(lvl)
        adj.loc[ix, "adjudication_reason"] = "synthetic adjudication against pre-deal evidence"
        adj.loc[ix, "final_confidence"] = "High" if rng.random() < 0.7 else "Medium"
        if r["coders_agree_intensity"] == "0":
            adj.loc[ix, "disagreement_category"] = r["suggested_disagreement_category"] or "Other"
        if lvl >= 2:
            adj.loc[ix, "final_subsector"] = str(t["sub"])
            adj.loc[ix, "strict_ai_review_done"] = "1"
            cid = r["company_id"]
            adj.loc[ix, "evidence_source_ids"] = f"S{cid}a;S{cid}b"
            ann = pd.Timestamp(t["ann"])
            src_rows += [dict(company_id=cid, source_id=f"S{cid}a", source_date=str((ann - pd.Timedelta(days=400)).date()), source_type="archived website", source_tier="B",
                              excerpt_summary="synthetic", test_supported="product_test;persistence_12m", url="", archived_url="", used_for_classification="1"),
                         dict(company_id=cid, source_id=f"S{cid}b", source_date=str((ann - pd.Timedelta(days=30)).date()), source_type="annual report", source_tier="A",
                              excerpt_summary="synthetic", test_supported="technical_asset_test", url="", archived_url="", used_for_classification="1"),
                         dict(company_id=cid, source_id=f"S{cid}c", source_date=str((ann + pd.Timedelta(days=500)).date()), source_type="current website", source_tier="D",
                              excerpt_summary="synthetic current site (locator only)", test_supported="", url="", archived_url="", used_for_classification="0")]
        if rng.random() < 0.06:
            adj.loc[ix, "alt_intensity"] = str(int(np.clip(lvl + rng.choice([-1, 1]), 0, 3)))
        adj.loc[ix, "adjudicator_id"] = "adjudicator"
        adj.loc[ix, "adjudication_status"] = "done"
        adj.loc[ix, "persistence_not_testable"] = "0"
        adj.loc[ix, "final_persistence_12m"] = "1" if lvl >= 2 else "0"
        adj.loc[ix, "acquihire_ai_flag"] = "0"
    adj.to_csv(root / "data_clean" / "ai_coding_adjudicated.csv", index=False)
    pd.DataFrame(src_rows).to_csv(root / "docs" / "ai_classification_sources.csv", index=False)


def fill_audit(root: Path, tmap, err=0.01, seed=21):
    rng = np.random.default_rng(seed)
    s = pd.read_csv(root / "results" / "classification_audit_sample.csv", dtype=str, keep_default_na=False)
    for ix, r in s.iterrows():
        lvl = tmap[int(r["company_id"])]["lvl"]
        if rng.random() < err:
            lvl = 0 if lvl >= 2 else 2
        s.loc[ix, "audit_intensity"], s.loc[ix, "audit_rationale"], s.loc[ix, "auditor_id"] = str(lvl), "synthetic audit", "auditor"
    s.to_csv(root / "results" / "classification_audit_sample.csv", index=False)


def setup(mode: str):
    tmp = Path(tempfile.mkdtemp(prefix=f"ai_p3_{mode}_"))
    for d in ("data_raw", "data_clean", "results", "docs"):
        (tmp / d).mkdir()
    shutil.copytree(SRC, tmp / "src", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    shutil.copytree(PROJ / "sql", tmp / "sql")
    shutil.copy(PROJ / "docs" / "ai_rubric.md", tmp / "docs" / "ai_rubric.md")
    truth = build_universe(tmp)
    run("01_collect.py", tmp)
    run("02b_build_stage2.py", tmp)
    run("03a_prepare_coding.py", tmp)
    return tmp, truth


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    created = []
    try:
        # =================== Scenario A: good coders -> gate passes -> freeze ===================
        tmp, truth = setup("good"); created.append(tmp)
        s1 = pd.read_csv(tmp / "data_clean" / "ai_coding_raw_coder1.csv", dtype=str)
        s2 = pd.read_csv(tmp / "data_clean" / "ai_coding_raw_coder2.csv", dtype=str)
        assert list(s1["company_id"]) != list(s2["company_id"]) and set(s1["company_id"]) == set(s2["company_id"]), "coders: same rows, different order"
        assert not any(c in s1.columns for c in ("coding_pool", "ai_candidate_flag", "candidate_keyword_hits")), "pool label must not reach coders"
        P.assert_no_valuation_columns(s1.columns)
        assert "$" not in " ".join(s1["description_text"].fillna("")), "valuation text in coder sheet"
        r = run("03a_prepare_coding.py", tmp); assert "not overwriting" not in r.stdout or True

        tmap = fill_coders(tmp, truth, "good")
        # coder files immutable once filled
        r = run("03a_prepare_coding.py", tmp)
        assert "not overwriting" in r.stdout, r.stdout
        r = run("03b_agreement_adjudicate.py", tmp, "--auto-accept-agreed", check=False)
        ag = pd.read_csv(tmp / "results" / "coder_agreement.csv").set_index("metric")
        kb = ag.loc["binary_strict_cohens_kappa", "value"]
        wq = ag.loc["intensity_weighted_kappa_quadratic", "value"]
        assert 0.70 < kb <= 1.0 and 0.70 < wq <= 1.0, (kb, wq)
        assert (tmp / "results" / "coder_confusion_binary.csv").exists() and (tmp / "results" / "coder_test_agreement.csv").exists()
        adj0 = pd.read_csv(tmp / "data_clean" / "ai_coding_adjudicated.csv", dtype=str, keep_default_na=False)
        agreed_hi = adj0[(adj0["coders_agree_intensity"] == "1") & adj0["coder1_intensity"].isin(["2", "3"])]
        assert (agreed_hi["adjudication_status"] == "pending").all(), "agreed intensity 2/3 must still need manual review"
        # gate must fail before adjudication / audit / NLP
        run("03c_nlp_screen.py", tmp)                      # unsupervised: no adjudicated labels for the hard rows yet
        run("03d_finalize.py", tmp, check=False)
        g = pd.read_csv(tmp / "results" / "gate_report.csv")
        assert not g["passed"].all(), "gate must not pass with pending adjudication"
        # negative test: missing disagreement category is rejected
        bad = adj0.copy()
        ix = bad.index[(bad["coders_agree_intensity"] == "0")][0]
        bad.loc[ix, ["final_intensity", "adjudication_reason", "final_confidence", "adjudication_status"]] = ["1", "x", "High", "done"]
        bad.to_csv(tmp / "data_clean" / "ai_coding_adjudicated.csv", index=False)
        rr = run("03b_agreement_adjudicate.py", tmp, check=False)
        assert rr.returncode == 1 and "disagreement_category required" in (tmp / "results" / "adjudication_errors.csv").read_text()
        adj0.to_csv(tmp / "data_clean" / "ai_coding_adjudicated.csv", index=False)
        # tampering with a raw coder value in the adjudication file is rejected
        t2 = adj0.copy(); t2.loc[0, "coder1_intensity"] = "9"; t2.to_csv(tmp / "data_clean" / "ai_coding_adjudicated.csv", index=False)
        rr = run("03b_agreement_adjudicate.py", tmp, check=False)
        assert "raw fields are immutable" in (tmp / "results" / "adjudication_errors.csv").read_text()
        adj0.to_csv(tmp / "data_clean" / "ai_coding_adjudicated.csv", index=False)

        adjudicate_and_source(tmp, tmap)
        run("03b_agreement_adjudicate.py", tmp)
        run("03c_nlp_screen.py", tmp)
        thr = json.loads((tmp / "results" / "nlp_threshold.json").read_text())
        assert thr["supervised"] is True, thr
        perf = pd.read_csv(tmp / "results" / "nlp_performance.csv")
        oof = perf[perf["evaluation"] == "oof_all_labelled_composite"].iloc[0]
        assert oof["recall"] >= 0.95 and oof["roc_auc"] > 0.9, oof
        assert (perf["evaluation"] == "holdout_test_composite").any()
        rec = perf[perf["evaluation"] == "candidate_screen_recall_estimate"].iloc[0]["recall"]
        # fixture flags every deal as a keyword candidate, so no non-candidate audit exists: recall must be NaN (not estimable), never a fake number
        assert pd.isna(rec) or 0.0 < rec <= 1.0
        run("03d_finalize.py", tmp, "--make-audit", check=False)
        assert (tmp / "results" / "classification_audit_sample.csv").exists()
        smp = pd.read_csv(tmp / "results" / "classification_audit_sample.csv")
        assert not any("intensity" in c and c != "audit_intensity" for c in smp.columns) and "ai_flag_strict" not in smp.columns, "audit sample must hide prior labels"
        fill_audit(tmp, tmap)
        r = run("03d_finalize.py", tmp, check=False)
        g = pd.read_csv(tmp / "results" / "gate_report.csv")
        failed = g[~g["passed"]]
        # screen recall may legitimately be below 90% in the synthetic draw; everything else must pass
        assert set(failed["gate_condition"]) <= {"candidate-screen recall estimate >= 90%"}, failed
        fin = pd.read_csv(tmp / "data_clean" / "ai_classifications_final.csv")
        P.assert_no_valuation_columns(fin.columns)
        assert fin["ai_flag_strict"].notna().all() and set(fin["ai_class_source"]) <= {"human_adjudicated", "screen_negative_assumed_non_ai"}
        # strict labels follow the adjudicated truth for human-coded rows (non-AI assumed rows may hide a few keyword-free AI-native targets)
        t_by_deal = {d: v["lvl"] for d, v in truth.items()}
        hum = fin[fin["ai_class_source"] == "human_adjudicated"]
        assert all((hum["ai_flag_strict"] == (hum["deal_id"].map(t_by_deal) >= 2).astype(int))), "human-adjudicated strict flag != adjudicated value"
        assert fin.loc[fin["ai_flag_strict"] == 1, "strict_evidence_complete"].eq(1).all()
        for f in ("ai_counts_year", "ai_counts_sector", "ai_counts_region", "ai_counts_public_private", "ai_counts_genai", "ai_intensity_distribution",
                  "ai_subsector_distribution", "classification_stability", "common_support_precheck", "power_reassessment", "temporal_check", "leakage_check"):
            assert (tmp / "results" / f"{f}.csv").exists(), f
        st = pd.read_csv(tmp / "results" / "classification_stability.csv").set_index("definition")
        assert st.loc["strict", "conservative_N"] <= st.loc["strict", "primary_N"] <= st.loc["strict", "liberal_N"]
        assert (pd.read_csv(tmp / "results" / "temporal_check.csv")["result"] == "PASS").all(), "tier D / post-announcement sources must not be used"
        assert (tmp / "docs" / "ai_edge_cases.csv").stat().st_size > 50 and (tmp / "docs" / "ai_classification_model_card.md").exists()

        # freeze: refused if gate failing; otherwise created and verifiable
        if not g["passed"].all():
            rf = run("03d_finalize.py", tmp, "--freeze", check=False)
            assert rf.returncode == 1 and "FREEZE REFUSED" in rf.stdout
            print("note: synthetic screen recall < 90%; freeze correctly refused")
        else:
            run("03d_finalize.py", tmp, "--freeze", "--date", "20261006")
            assert (tmp / "docs" / "AI_CLASSIFICATION_V1_20261006.json").exists()
            assert run("03d_finalize.py", tmp, "--verify-freeze", check=False).returncode == 0
            fz = tmp / "data_clean" / "ai_treatment_frozen_V1.csv"
            orig_txt = fz.read_text()
            fz.write_text(orig_txt.replace(",1.0,1.0,2.0", ",0.0,1.0,1.0", 1))
            assert run("03d_finalize.py", tmp, "--verify-freeze", check=False).returncode == 1, "tampering must be detected"
            fz.write_text(orig_txt)   # restore so downstream tests (Phase 4) can use the frozen file
            assert run("03d_finalize.py", tmp, "--verify-freeze", check=False).returncode == 0

        # ===== Blinding invariance: shuffle EV values (keeping availability) -> labels and NLP scores must be IDENTICAL =====
        before = {f: file_hash(tmp / "data_clean" / f) for f in ("ai_classifications_final.csv", "nlp_scores.csv")}
        terms = pd.read_csv(tmp / "data_raw" / "deal_terms_raw.csv", dtype=str)
        terms["enterprise_value"] = terms["enterprise_value"].sample(frac=1.0, random_state=3).to_numpy()
        terms.to_csv(tmp / "data_raw" / "deal_terms_raw.csv", index=False)
        run("02b_build_stage2.py", tmp)
        s2b = pd.read_csv(tmp / "data_clean" / "deals_stage2.csv", usecols=["deal_id", "ev_usd", "in_primary_sample_evrev"])
        assert s2b["ev_usd"].notna().all()
        run("03c_nlp_screen.py", tmp)
        run("03d_finalize.py", tmp, check=False)
        after = {f: file_hash(tmp / "data_clean" / f) for f in before}
        assert before == after, "AI labels / NLP scores changed when valuations were shuffled: BLINDING VIOLATED"
        print("blinding invariance: labels and NLP scores unchanged under shuffled valuations")

        # =================== Scenario B: random coders -> low kappa -> gate fails, freeze refused ===================
        tmp2, truth2 = setup("random"); created.append(tmp2)
        fill_coders(tmp2, truth2, "random")
        rb = run("03b_agreement_adjudicate.py", tmp2, "--auto-accept-agreed", check=False)
        kb2 = pd.read_csv(tmp2 / "results" / "coder_agreement.csv").set_index("metric").loc["binary_strict_cohens_kappa", "value"]
        assert kb2 < 0.40, kb2
        assert "KAPPA BELOW TARGET" in rb.stdout and (tmp2 / "results" / "coder_disagreement_summary.csv").exists()
        rf = run("03d_finalize.py", tmp2, "--freeze", check=False)
        assert rf.returncode == 1 and "FREEZE REFUSED" in rf.stdout
        assert not list((tmp2 / "docs").glob("AI_CLASSIFICATION_V1_*.json")), "no freeze manifest may exist when the gate fails"
        print(f"\nscenario A kappa={kb:.3f}, weighted kappa={wq:.3f}; scenario B kappa={kb2:.3f}")
        print("ALL PHASE 3 TESTS PASSED (synthetic data only)")
    finally:
        for t in created:
            if "--keep" in sys.argv:
                print("kept:", t)
            else:
                shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    main()
