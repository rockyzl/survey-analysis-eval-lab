"""Frozen CDC P&T 2025 reference values (gold/cdc_reference_2025.csv.gz)."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .paths import GOLD

REF_FILE = GOLD / "cdc_reference_2025.csv.gz"


@lru_cache(maxsize=1)
def load() -> pd.DataFrame:
    df = pd.read_csv(REF_FILE, dtype=str, keep_default_na=False)
    for c in ("data_value", "confidence_limit_low", "confidence_limit_high", "sample_size"):
        df[c] = pd.to_numeric(df[c].replace("", None), errors="coerce")
    return df


@lru_cache(maxsize=None)
def _index() -> dict:
    df = load()
    return {(r.questionid, r.response, r.locationabbr, r.break_out_category, r.break_out): r
            for r in df.itertuples(index=False)}


def lookup(question_id: str, response: str, location: str, category: str = "Overall", value: str = "Overall"):
    """Return the reference row (namedtuple) or None."""
    return _index().get((question_id, response, location, category, value))
