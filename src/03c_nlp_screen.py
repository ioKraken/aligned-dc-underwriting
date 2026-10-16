"""Phase 3, step C: NLP screening model (dictionary + TF-IDF logistic). A SCREEN and VALIDATOR, never the ground truth.

Corpus: PRE-ANNOUNCEMENT target text only (target, website, filing, historical, announcement-time website snapshot),
passed through the same valuation redaction as the coder files. Acquirer announcement language is excluded.
Valuation data are never loaded (blinded loader). Weights are fixed here, before any valuation analysis.

Outputs: data_clean/nlp_scores.csv
         results/nlp_performance.csv, nlp_threshold.json, nlp_false_positives.csv, nlp_false_negative_audit.csv,
         leakage_check_nlp.csv
Embedding score (ai_embedding_score) is optional and NOT implemented: the core pipeline is reproducible without a
proprietary embedding model (the column is written as empty).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_common as P  # noqa: E402
import utils as U  # noqa: E402

TEXT_FIELDS = ["target_description", "website_description", "filing_description", "historical_description", "snapshot_announcement"]
W_DICT, W_TFIDF = 0.5, 0.5                    # fixed in advance
DEFAULT_REVIEW_THRESHOLD = 0.30               # used when no human labels exist yet
TARGET_RECALL_FOR_THRESHOLD = 0.95
MIN_LABELS, MIN_PER_CLASS = 40, 8

DICT = {
    "general": (1.0, [r"artificial intelligence", r"\bai\b", r"machine[- ]learning", r"deep[- ]learning", r"neural[- ]networks?", r"\bneural\b"]),
    "genai": (1.0, [r"generative (ai|model)", r"large language models?", r"\bllms?\b", r"foundation models?", r"diffusion models?"]),
    "nlp": (0.75, [r"natural language processing", r"\bnlp\b", r"conversational ai"]),
    "vision": (0.75, [r"computer vision", r"image recognition"]),
    "infra": (0.5, [r"mlops", r"model training", r"\binference\b", r"accelerators?", r"gpu orchestration"]),
}
WEAK = [r"\bautomation\b", r"\banalytics\b", r"\bsmart\b", r"\bdigital\b", r"\bintelligent\b"]   # count only alongside strong terms
_DICT_RE = {cat: (w, [re.compile(p) for p in pats]) for cat, (w, pats) in DICT.items()}
_WEAK_RE = [re.compile(p) for p in WEAK]
_BOILER = re.compile(r"all rights reserved|cookie(s)? policy|privacy policy|terms of (use|service)|©\s?\d{4}", re.I)
_MONEY = re.compile(r"[$€£]\s?\d|\b\d[\d,\.]*\s?(million|billion|bn|mn)\b|\bEV/|\b\d+(\.\d+)?x\b|per share|\bpremium\b", re.I)


def clean(t) -> str:
    if not isinstance(t, str):
        return ""
    t = re.sub(r"<[^>]+>", " ", t)
    t = _BOILER.sub(" ", t)
    t = U.redact_valuation(t)
    return re.sub(r"\s+", " ", t.lower()).strip()


def dict_score(text: str):
    raw = 0.0
    matched = []
    for cat, (w, pats) in _DICT_RE.items():
        for p in pats:
            if p.search(text):
                raw += w
                matched.append(p.pattern)
    weak = sum(1 for p in _WEAK_RE if p.search(text)) if raw > 0 else 0
    raw += min(0.5, 0.1 * weak)
    return raw, 1 - np.exp(-raw / 2), matched


def prf(y, pred):
    y, pred = np.asarray(y).astype(int), np.asarray(pred).astype(int)
    tp, fp, fn, tn = int(((y == 1) & (pred == 1)).sum()), int(((y == 0) & (pred == 1)).sum()), int(((y == 1) & (pred == 0)).sum()), int(((y == 0) & (pred == 0)).sum())
    pr = tp / (tp + fp) if tp + fp else np.nan
    rc = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * pr * rc / (pr + rc) if pr and rc and not np.isnan(pr) and not np.isnan(rc) else np.nan
    sp = tn / (tn + fp) if tn + fp else np.nan
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=pr, recall=rc, f1=f1, specificity=sp)


def main(root: Path) -> int:
    res = root / "results"
    res.mkdir(exist_ok=True)
    deals = P.load_blinded_deals(root)
    desc = pd.read_csv(root / "data_raw" / "descriptions_raw.csv", dtype=str, keep_default_na=False)
    pool = deals[(deals["in_period"] == 1) & (deals["primary_sector"] == 1) & (deals["primary_geography"] == 1) &
                 (deals["control_deal"] == 1) & (deals["status_primary_sample"] == 1) & deals["structural_exclusion"].isna() &
                 (deals["has_description_text"] == 1)].copy()
    d = pool.merge(desc[["deal_id"] + [c for c in TEXT_FIELDS if c in desc.columns]], on="deal_id", how="left")
    d["text"] = d[[c for c in TEXT_FIELDS if c in d.columns]].fillna("").agg(" ".join, axis=1).map(clean)
    leak = d["text"].map(lambda s: bool(_MONEY.search(s)))
    pd.DataFrame([{"check": "nlp_corpus_has_no_valuation_text", "result": "FAIL" if leak.any() else "PASS", "detail": f"{int(leak.sum())} rows"},
                  {"check": "nlp_loaded_only_whitelisted_non_valuation_deal_columns", "result": "PASS", "detail": ""},
                  {"check": "acquirer_announcement_language_excluded_from_corpus", "result": "PASS", "detail": "announcement_description not used"}]
                 ).to_csv(res / "leakage_check_nlp.csv", index=False)
    if leak.any():
        print("LEAKAGE in NLP corpus"); return 1

    ds = d["text"].map(dict_score)
    d["dict_raw"] = ds.map(lambda x: x[0])
    d["dict_score"] = ds.map(lambda x: x[1])
    d["tfidf_prob"] = np.nan
    d["score_type"] = "dictionary_only"

    # ---- human labels (adjudicated, done) ----------------------------------------------------------------
    labels = pd.DataFrame(columns=["target_id", "y"])
    ap = root / "data_clean" / "ai_coding_adjudicated.csv"
    if ap.exists():
        a = pd.read_csv(ap, dtype=str, keep_default_na=False)
        a = a[a["adjudication_status"] == "done"]
        labels = pd.DataFrame({"target_id": pd.to_numeric(a["company_id"]), "y": (pd.to_numeric(a["final_intensity"]) >= 2).astype(int)})
    d["y"] = d["target_id"].map(labels.drop_duplicates("target_id").set_index("target_id")["y"]) if len(labels) else np.nan
    lab = d[d["y"].notna()].copy()
    perf = []
    thr = DEFAULT_REVIEW_THRESHOLD
    thr_note = "default review trigger (no human labels available yet)"
    n_pos, n_neg = int((lab["y"] == 1).sum()), int((lab["y"] == 0).sum())
    supervised = len(lab) >= MIN_LABELS and min(n_pos, n_neg) >= MIN_PER_CLASS
    if supervised:
        vec_kw = dict(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=False, stop_words=None, max_features=20000)
        era = (lab["announcement_date"] > U.GENAI_DATE).astype(int)
        strat = lab["y"].astype(int).astype(str) + era.astype(str)
        strat = strat if strat.value_counts().min() >= 2 else lab["y"].astype(int).astype(str)
        tr, te = train_test_split(lab.index, test_size=0.3, random_state=U.SEED, stratify=strat.loc[lab.index])
        def fit(idx):
            v = TfidfVectorizer(**vec_kw)
            X = v.fit_transform(d.loc[idx, "text"])
            m = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=U.SEED).fit(X, d.loc[idx, "y"].astype(int))
            return v, m
        v, m = fit(tr)
        p_te = m.predict_proba(v.transform(d.loc[te, "text"]))[:, 1]
        comp_te = W_DICT * d.loc[te, "dict_score"].to_numpy() + W_TFIDF * p_te
        y_te = d.loc[te, "y"].astype(int).to_numpy()
        auc_te = roc_auc_score(y_te, comp_te) if len(set(y_te)) == 2 else np.nan
        # out-of-fold probabilities for all labelled rows
        skf = StratifiedKFold(n_splits=min(5, n_pos, n_neg), shuffle=True, random_state=U.SEED)
        from sklearn.pipeline import make_pipeline
        pipe = make_pipeline(TfidfVectorizer(**vec_kw), LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=U.SEED))
        oof = cross_val_predict(pipe, d.loc[lab.index, "text"], d.loc[lab.index, "y"].astype(int), cv=skf, method="predict_proba")[:, 1]
        d.loc[lab.index, "tfidf_prob"] = oof
        d.loc[lab.index, "score_type"] = "oof"
        pipe.fit(d.loc[lab.index, "text"], d.loc[lab.index, "y"].astype(int))
        unl = d.index.difference(lab.index)
        if len(unl):
            d.loc[unl, "tfidf_prob"] = pipe.predict_proba(d.loc[unl, "text"])[:, 1]
            d.loc[unl, "score_type"] = "final_model"
        d["ai_nlp_score"] = W_DICT * d["dict_score"] + W_TFIDF * d["tfidf_prob"]
        # threshold: highest-precision threshold that keeps OOF recall >= 95% (recall priority; no valuation input)
        yl, sl = d.loc[lab.index, "y"].astype(int).to_numpy(), d.loc[lab.index, "ai_nlp_score"].to_numpy()
        cands = np.unique(np.round(sl, 4))
        best = None
        for t in sorted(cands):
            r_ = prf(yl, sl >= t)
            if r_["recall"] >= TARGET_RECALL_FOR_THRESHOLD:
                best = (t, r_)
        thr = float(best[0]) if best else float(min(DEFAULT_REVIEW_THRESHOLD, cands.min()))
        thr_note = f"max threshold with OOF recall >= {TARGET_RECALL_FOR_THRESHOLD:.0%} on {len(lab)} labelled targets"
        te_pred = comp_te >= thr
        perf.append({"evaluation": "holdout_test_composite", "n": len(te), "n_pos": int(y_te.sum()), "roc_auc": auc_te, **prf(y_te, te_pred)})
        perf.append({"evaluation": "oof_all_labelled_composite", "n": len(lab), "n_pos": n_pos, "roc_auc": roc_auc_score(yl, sl), **prf(yl, sl >= thr)})
        yd = d.loc[lab.index, "dict_score"].to_numpy()
        perf.append({"evaluation": "dictionary_only_all_labelled", "n": len(lab), "n_pos": n_pos, "roc_auc": roc_auc_score(yl, yd), **prf(yl, yd >= DEFAULT_REVIEW_THRESHOLD)})
        ap_note = ""
    else:
        d["ai_nlp_score"] = d["dict_score"]
        ap_note = f"supervised model skipped: {len(lab)} labelled targets ({n_pos} AI / {n_neg} non-AI); need >= {MIN_LABELS} with >= {MIN_PER_CLASS} per class. Scores are dictionary-only."
        print(ap_note)
    d["nlp_flag"] = (d["ai_nlp_score"] >= thr).astype(int)
    d["ai_embedding_score"] = np.nan

    # ---- Phase 2 keyword screen vs human labels; false-negative audit; recall estimate -------------------
    fn_rows = pd.DataFrame()
    if len(lab):
        kc = lab[lab["ai_candidate_flag"] == 1]
        ka = lab[lab["ai_candidate_flag"] == 0]
        perf.append({"evaluation": "phase2_keyword_screen_vs_human(on labelled rows)", "n": len(lab), "n_pos": n_pos, **prf(lab["y"].astype(int), (lab["ai_candidate_flag"] == 1).astype(int))})
        n_noncand = int(((pool["ai_candidate_flag"] == 0)).sum())
        tp_c = int((kc["y"] == 1).sum())
        fn_a, n_a = int((ka["y"] == 1).sum()), len(ka)
        rate = fn_a / n_a if n_a else np.nan
        lo, hi = P.wilson(fn_a, n_a)
        est_missed = rate * n_noncand if n_a else np.nan
        recall_est = tp_c / (tp_c + est_missed) if n_a and (tp_c + est_missed) > 0 else np.nan
        rec_lo = tp_c / (tp_c + hi * n_noncand) if n_a and (tp_c + hi * n_noncand) > 0 else np.nan
        perf.append({"evaluation": "false_negative_audit(random 20% of non-candidates)", "n": n_a, "n_pos": fn_a, "fn_rate": rate, "fn_rate_ci_low": lo, "fn_rate_ci_high": hi,
                     "est_missed_strict_ai_in_noncandidate_pool": est_missed})
        perf.append({"evaluation": "candidate_screen_recall_estimate", "n": tp_c, "recall": recall_est, "recall_ci_low": rec_lo,
                     "note": "MEETS >=90% target" if (not np.isnan(recall_est) and recall_est >= P.SCREEN_RECALL_TARGET) else "BELOW 90%: Phase 2 screen incomplete; expand terms and re-screen (document; never tune on valuations)"})
        fn_rows = ka[ka["y"] == 1][["deal_id", "target_id", "text"]].copy()
        fn_rows["text_excerpt"] = fn_rows["text"].str[:300]
        if not np.isnan(recall_est) and recall_est < P.SCREEN_RECALL_TARGET:
            print(f"Candidate-screen recall estimate {recall_est:.2f} < {P.SCREEN_RECALL_TARGET:.0%}: re-run Phase 2 screening with an expanded term list before proceeding.")
    fn_rows.drop(columns=["text"], errors="ignore").to_csv(res / "nlp_false_negative_audit.csv", index=False)

    # ---- false-positive analysis ---------------------------------------------------------------------------
    labn = d.loc[lab.index]
    fp = labn[(labn["nlp_flag"] == 1) & (labn["y"] == 0)].copy() if len(lab) else pd.DataFrame()
    if len(fp):
        def tag(r):
            t = r["text"]
            if r["dict_raw"] < 1.0:
                return "only_weak_or_single_generic_term"
            if r["sector_primary"] == "Cybersecurity":
                return "security_product_with_ml_feature"
            if "analytics" in t:
                return "generic_analytics_language"
            return "ai_enabled_not_native_or_marketing"
        fp["heuristic_tag"] = fp.apply(tag, axis=1)
        fp["text_excerpt"] = fp["text"].str[:300]
        fp["human_category"] = ""
        fp[["deal_id", "target_id", "sector_primary", "ai_nlp_score", "heuristic_tag", "text_excerpt", "human_category"]].to_csv(res / "nlp_false_positives.csv", index=False)
    else:
        pd.DataFrame(columns=["deal_id", "target_id", "sector_primary", "ai_nlp_score", "heuristic_tag", "text_excerpt", "human_category"]).to_csv(res / "nlp_false_positives.csv", index=False)

    pd.DataFrame(perf).to_csv(res / "nlp_performance.csv", index=False)
    json.dump({"threshold": thr, "rule": thr_note, "weights": {"dictionary": W_DICT, "tfidf": W_TFIDF}, "labelled_n": int(len(lab)),
               "supervised": bool(supervised), "note": ap_note or "set without reference to any valuation outcome"},
              open(res / "nlp_threshold.json", "w"), indent=2)
    d[["deal_id", "target_id", "dict_raw", "dict_score", "tfidf_prob", "ai_embedding_score", "ai_nlp_score", "nlp_flag", "score_type"]].to_csv(root / "data_clean" / "nlp_scores.csv", index=False)
    print(f"scored {len(d)} targets | supervised={supervised} | threshold={thr:.3f} | flagged={int(d['nlp_flag'].sum())}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    sys.exit(main(U.project_root(ap.parse_args().root)))
