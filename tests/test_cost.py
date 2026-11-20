"""Cost accounting from token usage and the documented price table."""
import json

import pytest

from survey_lab import llm, pipeline
from survey_lab.paths import ROOT


def test_price_table_documented():
    p = json.loads((ROOT / "docs" / "pricing.json").read_text())
    assert "developers.openai.com/api/docs/pricing" in p["openai"]["source"] and "2026-11-20" in p["openai"]["source"]
    m = p["openai"]["models"]
    assert (m["gpt-4.1"]["input"], m["gpt-4.1"]["cached_input"], m["gpt-4.1"]["output"]) == (2.0, 0.5, 8.0)
    assert m["gpt-4o"]["snapshot"] == "gpt-4o-2024-11-20" and m["gpt-4.1"]["snapshot"] == "gpt-4.1-2025-04-14"
    assert "Azure Retail Prices API" in p["azure"]["source"]


def test_cost_formula_with_and_without_cache():
    # gpt-4.1: 3000 prompt (1024 cached), 100 completion
    c = llm.cost_usd("gpt-4.1", 3000, 100, 1024)
    assert c == pytest.approx(((3000 - 1024) * 2.0 + 1024 * 0.5 + 100 * 8.0) / 1e6)
    assert llm.cost_usd("gpt-4.1", 3000, 100) == pytest.approx((3000 * 2.0 + 100 * 8.0) / 1e6)
    assert llm.cost_usd("gpt-4o", 1000, 50, 0) == pytest.approx((1000 * 2.5 + 50 * 10.0) / 1e6)
    # cached can never exceed prompt tokens
    assert llm.cost_usd("gpt-4o", 100, 0, 500) == pytest.approx(100 * 1.25 / 1e6)
    assert llm.cost_usd("gpt-4.1-mini", 3000, 100, 2048, "openai") == pytest.approx(
        ((3000 - 2048) * 0.40 + 2048 * 0.10 + 100 * 1.60) / 1e6)


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


def test_snapshots_pinned_and_cache_key_includes_provider(monkeypatch):
    monkeypatch.setenv("SURVEYLAB_LLM_PROVIDER", "openai")
    a = llm.LLM("gpt-4o")
    assert a.snapshot == "gpt-4o-2024-11-20" and llm.LLM("gpt-4.1").snapshot == "gpt-4.1-2025-04-14"
    m = [{"role": "user", "content": "x"}]
    monkeypatch.setenv("SURVEYLAB_LLM_PROVIDER", "azure")
    assert llm.LLM("gpt-4o").cache_key(m) != a.cache_key(m)   # provisional Azure responses are never reused


def test_spend_cap_blocks_live_calls(monkeypatch):
    monkeypatch.setenv("SURVEYLAB_LLM_PROVIDER", "openai")
    monkeypatch.setenv("SURVEYLAB_LLM_ENABLED", "1")
    monkeypatch.setenv("SURVEYLAB_SPEND_CAP_USD", "0")
    c = llm.LLM("gpt-4.1")
    with pytest.raises(llm.SpendCapReached):
        c.complete([{"role": "user", "content": "never-cached question 7b1c"}])
    assert c._client is None


def test_live_calls_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SURVEYLAB_LLM_ENABLED", raising=False)
    c = llm.LLM("gpt-4.1")
    with pytest.raises(llm.LLMDisabled):
        c.complete([{"role": "user", "content": "never-cached question 0f3a"}])
    assert c._client is None
