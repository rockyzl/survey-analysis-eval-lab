"""Missing-code / denominator rules applied by the executor (synthetic data)."""
import numpy as np
import pytest

from survey_lab import executor
from survey_lab.spec import validate


def _wmean(df, mask, yes):
    return np.average(yes[mask], weights=df._LLCPWT[mask]) * 100


def test_dk_refused_blank_excluded(toy_df):
    spec = validate({"answerable": True, "indicator": "MEDCOST1", "response": "Yes", "geography": "WA", "subgroup": None})
    r = executor.execute(spec)
    wa = toy_df._STATE == 53
    valid = wa & toy_df.MEDCOST1.isin([1, 2])
    assert r.n_denom == int(valid.sum())
    assert r.n_denom < int(wa.sum())          # 7, 9 and blank really were present and dropped
    assert r.estimate == pytest.approx(_wmean(toy_df, valid, (toy_df.MEDCOST1 == 1).values))


def test_calculated_variable_code_9_excluded(toy_df):
    spec = validate({"answerable": True, "indicator": "_RFHLTH", "response": "Fair or Poor Health", "geography": "OR",
                     "subgroup": None})
    r = executor.execute(spec)
    m = (toy_df._STATE == 41) & toy_df._RFHLTH.isin([1, 2])
    assert r.n_denom == int(m.sum())
    assert r.n_yes == int(((toy_df._RFHLTH == 2) & m).sum())


def test_out_of_universe_blank_excluded(toy_df):
    spec = validate({"answerable": True, "indicator": "_FLSHOT7", "response": "Yes", "geography": "WA", "subgroup": None})
    r = executor.execute(spec)
    m = (toy_df._STATE == 53) & toy_df._FLSHOT7.isin([1, 2])
    assert r.n_denom == int(m.sum())


def test_subgroup_missing_breakout_dropped(toy_df):
    spec = validate({"answerable": True, "indicator": "_RFHLTH", "response": "Fair or Poor Health", "geography": "WA",
                     "subgroup": {"category": "Household Income", "value": "$200,000+"}})
    r = executor.execute(spec)
    m = (toy_df._STATE == 53) & toy_df._RFHLTH.isin([1, 2]) & (toy_df._INCOMG1 == 7)
    assert r.n_denom == int(m.sum())
    assert r.estimate == pytest.approx(_wmean(toy_df, m, (toy_df._RFHLTH == 2).values))
    assert "dropped" in r.trace["subgroup"]


def test_trace_shows_computation(toy_df):
    spec = validate({"answerable": True, "indicator": "MEDCOST1", "response": "Yes", "geography": "WA", "subgroup": None})
    t = executor.execute(spec).trace
    assert t["variable"] == "MEDCOST1" and t["numerator_codes"] == [1] and t["denominator_codes"] == [1, 2]
    assert t["weight"] == "_LLCPWT" and "Taylor" in t["variance"]
