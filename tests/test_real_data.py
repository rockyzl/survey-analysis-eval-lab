"""Regression checks on the real 2025 file (skipped when data/raw is absent)."""
import pytest

from survey_lab import executor, reference
from survey_lab.paths import LLCP_PARQUET, SLIM_PARQUET
from survey_lab.spec import validate

pytestmark = pytest.mark.skipif(not (LLCP_PARQUET.exists() or SLIM_PARQUET.exists()), reason="BRFSS data not downloaded")


@pytest.mark.parametrize("spec,loc,cat,val", [
    ({"indicator": "_RFHLTH", "response": "Fair or Poor Health", "geography": "WA", "subgroup": None}, "WA", "Overall", "Overall"),
    ({"indicator": "ADDEPEV3", "response": "Yes", "geography": "FL",
      "subgroup": {"category": "Household Income", "value": "$200,000+"}}, "FL", "Household Income", "$200,000+"),
    ({"indicator": "RACE8", "response": "White, non-Hispanic", "geography": "WA", "subgroup": None}, "WA", "Overall", "Overall"),
])
def test_matches_cdc(spec, loc, cat, val):
    r = executor.execute(validate({"answerable": True, **spec}))
    ref = reference.lookup(spec["indicator"], spec["response"], loc, cat, val)
    assert abs(r.estimate - ref.data_value) <= 0.1
    assert abs(r.ci_low - ref.confidence_limit_low) <= 0.1 and abs(r.ci_high - ref.confidence_limit_high) <= 0.1
    assert r.n_yes == ref.sample_size
