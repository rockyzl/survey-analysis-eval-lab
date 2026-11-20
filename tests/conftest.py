import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def toy_df(monkeypatch):
    """A tiny synthetic BRFSS-like file wired into survey_lab.data.load()."""
    from survey_lab import data, executor
    rng = np.random.default_rng(0)
    n = 2000
    df = pd.DataFrame({
        "_STATE": np.where(np.arange(n) < 1500, 53, 41).astype(float),          # WA, OR
        "_STSTR": (np.where(np.arange(n) < 1500, 53000, 41000) + (np.arange(n) % 4)).astype(float),
        "_PSU": (np.arange(n) // 2).astype(float),
        "_LLCPWT": rng.uniform(50, 500, n),
    })
    from survey_lab import catalog
    for v in catalog.allowed_variables() - set(df.columns):
        df[v] = 1.0
    # _RFHLTH: 1 good, 2 fair/poor, 9 missing
    df["_RFHLTH"] = rng.choice([1.0, 2.0, 9.0], n, p=[0.7, 0.2, 0.1])
    # MEDCOST1: 1 yes 2 no 7 DK 9 refused, blank
    df["MEDCOST1"] = rng.choice([1.0, 2.0, 7.0, 9.0, np.nan], n, p=[0.1, 0.7, 0.1, 0.05, 0.05])
    # _FLSHOT7: blank for age < 65
    df["_FLSHOT7"] = rng.choice([1.0, 2.0, 9.0, np.nan], n, p=[0.15, 0.1, 0.05, 0.7])
    df["_SEX"] = rng.choice([1.0, 2.0], n)
    df["_INCOMG1"] = rng.choice([1.0, 2.0, 7.0, 9.0], n, p=[0.3, 0.3, 0.2, 0.2])
    monkeypatch.setattr(data, "load", lambda: df)
    executor._execute_cached.cache_clear()
    yield df
    executor._execute_cached.cache_clear()
