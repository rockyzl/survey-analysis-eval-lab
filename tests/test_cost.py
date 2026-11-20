"""Cost accounting from token usage and the documented price table."""
import json

import pytest

from survey_lab import llm, pipeline
from survey_lab.paths import ROOT


def test_price_table_documented():
    p = json.loads((ROOT / "docs" / "pricing.json").read_text())
    assert "Azure Retail Prices API" in p["source"] and "2026-11-20" in p["source"]
    assert p["models"]["gpt-4.1"] == {**p["models"]["gpt-4.1"], "input": 2.0, "cached_input": 0.5, "output": 8.0}


def test_cost_formula_with_and_without_cache():
    # gpt-4.1: 3000 prompt (1024 cached), 100 completion
    c = llm.cost_usd("gpt-4.1", 3000, 100, 1024)
    assert c == pytest.approx(((3000 - 1024) * 2.0 + 1024 * 0.5 + 100 * 8.0) / 1e6)
    assert llm.cost_usd("gpt-4.1", 3000, 100) == pytest.approx((3000 * 2.0 + 100 * 8.0) / 1e6)
    assert llm.cost_usd("gpt-4o", 1000, 50, 0) == pytest.approx((1000 * 2.5 + 50 * 10.0) / 1e6)
    # cached can never exceed prompt tokens
    assert llm.cost_usd("gpt-4o", 100, 0, 500) == pytest.approx(100 * 1.25 / 1e6)


def test_outcome_cost_sums_calls():
    from survey_lab.spec import abstain
    calls = [llm.Call("gpt-4o", "{}", 1000, 10, 0, 1.0, llm.cost_usd("gpt-4o", 1000, 10), False),
             llm.Call("gpt-4.1", "{}", 1000, 10, 512, 1.0, llm.cost_usd("gpt-4.1", 1000, 10, 512), False)]
    o = pipeline.Outcome("ROUTER", abstain("ambiguous"), ["template", "gpt-4o", "gpt-4.1"], calls)
    assert o.cost == pytest.approx(sum(c.cost for c in calls))


def test_template_path_costs_nothing(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLM must not be called")
    monkeypatch.setattr(pipeline, "llm_spec", boom)
    o = pipeline.route("binge drinking rate wisconsin adults", "TEMPLATE")
    assert o.cost == 0 and o.path == ["template"]
