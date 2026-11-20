"""Load the analysis subset of the BRFSS 2025 LLCP file (only catalog-allowed variables)."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from . import catalog
from .paths import LLCP_PARQUET, SLIM_PARQUET


def build_slim() -> pd.DataFrame:
    cols = sorted(catalog.allowed_variables())
    df = pd.read_parquet(LLCP_PARQUET, columns=cols)
    SLIM_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SLIM_PARQUET, index=False)
    return df


@lru_cache(maxsize=1)
def load() -> pd.DataFrame:
    if not SLIM_PARQUET.exists():
        build_slim()
    df = pd.read_parquet(SLIM_PARQUET)
    missing = catalog.allowed_variables() - set(df.columns)
    if missing:
        df = build_slim()
    return df
