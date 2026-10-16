"""Shared helpers for the Phase 2 pipeline. Frozen Phase 1 rules live here as constants."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261006
PERIOD_START = pd.Timestamp("2015-01-01")
PERIOD_END = pd.Timestamp("2026-09-30")
GENAI_DATE = pd.Timestamp("2022-11-30")
EV_MIN_USD = 25_000_000
REV_MIN_USD = 5_000_000
STALE_DAYS = 365
FRESH_DAYS = 180
EV_RECON_TOL = 0.05          # 5% tolerance for EV reconciliation
PRICE_RECON_TOL = 0.05       # 5% tolerance for equity value vs offer x diluted shares
AUDIT_FRACTION = 0.20

MISSING_CODES = {"NA", "ND", "NF", "NR"}

# ---- geography -------------------------------------------------------------------------
EU27 = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
        "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
EEA_EXTRA = {"IS", "LI", "NO"}
REGION_MAP = {"US": "US", "CA": "Canada", "GB": "UK", "IL": "Israel", "CH": "EU_EEA_CH"}
for _c in EU27 | EEA_EXTRA:
    REGION_MAP[_c] = "EU_EEA_CH"
PRIMARY_COUNTRIES = set(REGION_MAP)

NAME_TO_ISO2 = {"united states": "US", "usa": "US", "us": "US", "canada": "CA",
                "united kingdom": "GB", "uk": "GB", "great britain": "GB", "israel": "IL",
                "switzerland": "CH", "germany": "DE", "france": "FR", "netherlands": "NL",
                "sweden": "SE", "ireland": "IE", "spain": "ES", "italy": "IT", "finland": "FI",
                "denmark": "DK", "norway": "NO", "belgium": "BE", "austria": "AT"}

PRIMARY_SECTORS = ["Application Software", "Infrastructure Software", "Cybersecurity",
                   "Internet / Digital Platform", "Semiconductors", "IT Services"]
SECTOR_ALIASES = {s.lower(): s for s in PRIMARY_SECTORS}
SECTOR_ALIASES.update({"internet": "Internet / Digital Platform", "internet platforms": "Internet / Digital Platform",
                       "digital platform": "Internet / Digital Platform", "software": "Application Software",
                       "security": "Cybersecurity", "semis": "Semiconductors", "it services": "IT Services"})
EXCLUDED_SECTORS = {"data center", "data-center real assets", "telecom", "hardware oem", "healthcare", "industrial"}

DEAL_STATUSES = ["announced", "definitive", "completed", "withdrawn", "rejected", "competing_bid", "terminated"]
PRIMARY_STATUSES = {"completed", "definitive"}
BUYER_TYPES = ["strategic", "sponsor", "consortium", "government_swf", "other"]

STRUCTURAL_EXCLUSION_CODES = {
    "minority": "Minority stake (<50%, no control)",
    "venture_round": "Venture / growth round",
    "pipe": "PIPE",
    "asset_only": "Asset-only purchase",
    "carveout_no_standalone": "Carve-out without standalone financials",
    "internal": "Internal restructuring / intra-group",
    "spac": "SPAC business combination",
    "distressed": "Distressed / insolvency sale",
    "acquihire": "Acqui-hire / licence-and-hire",
}

LEGAL_SUFFIXES = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
                  "llc", "lp", "llp", "ag", "sa", "nv", "bv", "gmbh", "ab", "as", "asa", "oyj", "spa",
                  "srl", "se", "the", "pte", "pty"}

# ---- AI candidate keyword screen (SCREEN ONLY, never the final ai_flag) -----------------
AI_KEYWORDS = [
    r"artificial intelligence", r"\bAI\b", r"machine[- ]learning", r"\bML\b", r"deep[- ]learning",
    r"generative", r"\bLLMs?\b", r"large language model", r"neural", r"computer vision",
    r"\bNLP\b", r"natural language", r"autonomous", r"predictive (ai|analytics|model)",
    r"foundation model", r"\bGPU\b", r"transformer model",
]
_AI_RE = [(k, re.compile(k, re.I if k not in (r"\bAI\b", r"\bML\b", r"\bNLP\b", r"\bGPU\b") else 0))
          for k in AI_KEYWORDS]

_MONEY_RE = re.compile(
    r"(US\$|USD|EUR|GBP|CAD|ILS|CHF|[$€£])\s?\d[\d,\.]*\s?(million|billion|bn|mn|m|b|k)?\b"
    r"|\b\d[\d,\.]*\s?(million|billion|bn|mn)\b|\b\d+(\.\d+)?x\b|\bEV\b|\bpremium\b|per share",
    re.I)


def ai_keyword_hits(text: str | float) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    return [k for k, rx in _AI_RE if rx.search(text)]


def redact_valuation(text: str | float) -> str:
    """Strip money amounts / multiples / price language from coder-facing text."""
    if not isinstance(text, str):
        return ""
    return _MONEY_RE.sub("[REDACTED]", text)


# ---- names -------------------------------------------------------------------------------
def normalize_name(name: str | float) -> str:
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t not in LEGAL_SUFFIXES]
    return " ".join(toks)


def iso2(country: str | float) -> str | None:
    if not isinstance(country, str):
        return None
    c = country.strip()
    if len(c) == 2:
        return c.upper()
    return NAME_TO_ISO2.get(c.lower())


def region_of(country_iso2: str | None) -> str | None:
    return REGION_MAP.get(country_iso2) if country_iso2 else None


# ---- missing-data codes ------------------------------------------------------------------
def split_missing_codes(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert columns that may hold ND/NF/NR/NA strings to numeric + <col>_missing_code."""
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
        raw = df[c].astype("string").str.strip()
        code = raw.where(raw.str.upper().isin(MISSING_CODES)).str.upper()
        df[c + "_missing_code"] = code
        df[c] = pd.to_numeric(raw.where(~raw.str.upper().isin(MISSING_CODES)), errors="coerce").astype("float64")
    return df


def read_csv_safe(path: Path, **kw) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], **kw)


def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def project_root(arg: str | None = None) -> Path:
    return Path(arg).resolve() if arg else Path(__file__).resolve().parents[1]
