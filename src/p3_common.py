"""Phase 3 shared definitions: rubric constants, agreement statistics, blinded data loader.

BLINDING RULE (enforced in code): no Phase 3 script may load a valuation column. Deal data are read only through
load_blinded_deals(), which uses a whitelist and asserts that no loaded column name looks like a valuation field.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

import utils as U

INTENSITY_LABELS = {0: "Non-AI", 1: "AI-enabled", 2: "AI-native", 3: "Frontier / core AI infrastructure"}
SUBSECTORS = {
    1: "Foundation Models / Generative AI",
    2: "AI Developer Tools / MLOps / AI Data Infrastructure",
    3: "Enterprise AI Software",
    4: "Vertical AI",
    5: "Computer Vision / NLP / Conversational AI",
    6: "Autonomous Systems / Robotics",
    7: "AI Cybersecurity",
    8: "AI Semiconductors / Accelerators / Infrastructure",
    9: "Traditional ML / Predictive Analytics",
}
PLANNED_GROUPS = {1: "Core AI Platform / Infrastructure", 2: "Core AI Platform / Infrastructure",
                  8: "Core AI Platform / Infrastructure", 3: "AI Applications", 4: "AI Applications",
                  5: "AI Applications", 9: "AI Applications", 6: "Specialized AI", 7: "Specialized AI"}
MIN_GROUP_N = 8
CONFIDENCE = ["High", "Medium", "Low"]
TEST_COLS = ["product_test", "technical_asset_test", "revenue_test", "persistence_12m"]
MATURITY = ["Pre-revenue", "Early revenue", "Scaling", "Mature"]
KAPPA_TARGET = 0.70
SCREEN_RECALL_TARGET = 0.90
AUDIT_FRAC_AI = 0.10
AUDIT_FRAC_NONAI = 0.05
AUDIT_ERROR_LIMIT = 0.05
SOURCE_TIERS = ["A", "B", "C", "D"]

CODER_IDENT_COLS = ["coder_row", "company_id", "target_name", "announcement_date", "sector", "description_text",
                    "historical_description", "website_snapshot_text", "filing_description"]
CODER_FILL_COLS = TEST_COLS + ["ai_intensity", "ai_subsector", "secondary_ai_subsector", "confidence", "rationale",
                               "counterevidence_notes", "evidence_source_ids", "acquihire_ai_flag",
                               "persistence_not_testable", "company_founded_year", "commercial_maturity", "coder_id"]
CODER_COLS = CODER_IDENT_COLS + CODER_FILL_COLS

# ---- blinded loader -------------------------------------------------------------------------------------
BLIND_OK = ["deal_id", "target_id", "buyer_id", "target_name", "announcement_date", "announce_year", "in_period", "post_genai",
            "target_region", "target_country", "sector_primary", "primary_sector", "primary_geography", "control_deal",
            "status_primary_sample", "structural_exclusion", "public_target", "buyer_type", "strategic_buyer",
            "sponsor_buyer", "revenue_ltm_usd", "revenue_growth", "ebitda_margin", "data_quality_flag",
            "in_primary_sample_evrev", "in_primary_sample_ebitda", "in_primary_sample_premium",
            "ai_candidate_flag", "candidate_keyword_hits", "n_keyword_hits", "has_description_text"]
STRUCTURAL_FLAGS = {"in_primary_sample_evrev", "in_primary_sample_ebitda", "in_primary_sample_premium"}  # availability flags, no values
FORBIDDEN_RE = re.compile(r"(^|_)(ev|equity|premium|offer|price|prices|multiple|vwap|unaffected|runup|predeal|fx)(_|$)|ev_revenue|ev_ebitda|enterprise", re.I)


def assert_no_valuation_columns(cols) -> None:
    bad = [c for c in cols if FORBIDDEN_RE.search(c) and c not in STRUCTURAL_FLAGS]
    if bad:
        raise AssertionError(f"valuation-like columns would be loaded in Phase 3: {bad}")


def load_blinded_deals(root: Path) -> pd.DataFrame:
    p = root / "data_clean" / "deals_stage2.csv"
    header = pd.read_csv(p, nrows=0).columns
    cols = [c for c in header if c in BLIND_OK]
    assert_no_valuation_columns(cols)
    d = pd.read_csv(p, usecols=cols, parse_dates=["announcement_date"])
    return d


# ---- agreement statistics ---------------------------------------------------------------------------------
def cohen_kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    n = len(a)
    if n == 0:
        return np.nan
    cats = np.union1d(a, b)
    po = (a == b).mean()
    pe = sum(((a == c).mean()) * ((b == c).mean()) for c in cats)
    return np.nan if np.isclose(pe, 1.0) else (po - pe) / (1 - pe)


def weighted_kappa(a, b, categories=(0, 1, 2, 3), weights: str = "quadratic") -> float:
    a, b = np.asarray(a), np.asarray(b)
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    obs = np.zeros((k, k))
    for x, y in zip(a, b):
        obs[idx[x], idx[y]] += 1
    n = obs.sum()
    if n == 0:
        return np.nan
    obs /= n
    exp = np.outer(obs.sum(1), obs.sum(0))
    i, j = np.meshgrid(range(k), range(k), indexing="ij")
    w = (i - j) ** 2 if weights == "quadratic" else np.abs(i - j)
    w = w / w.max()
    den = (w * exp).sum()
    return np.nan if np.isclose(den, 0) else 1 - (w * obs).sum() / den


def bootstrap_ci(fn, a, b, n_boot: int = 2000, seed: int = U.SEED):
    a, b = np.asarray(a), np.asarray(b)
    if len(a) < 5:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        ix = rng.integers(0, len(a), len(a))
        v = fn(a[ix], b[ix])
        if not np.isnan(v):
            vals.append(v)
    return (np.nan, np.nan) if len(vals) < 50 else (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def kappa_band(k: float) -> str:
    if k is None or np.isnan(k):
        return "undefined"
    return "weak (<0.40)" if k < 0.40 else "moderate (0.40-0.60)" if k < 0.60 else "substantial (0.60-0.80)" if k <= 0.80 else "strong (>0.80)"


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def vintage_of(year) -> str | float:
    if pd.isna(year):
        return np.nan
    y = int(year)
    return "pre_2015_established_ML" if y <= 2014 else "2015_2019_AI_wave" if y <= 2019 else "2020_2022" if y <= 2022 else "post_GenAI_2023plus"
