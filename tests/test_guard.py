"""The guard only lets catalog values through; nothing executable can reach the executor."""
import pytest

from survey_lab import catalog
from survey_lab.spec import GuardError, validate

OK = {"answerable": True, "indicator": "_RFSMOK3", "response": "Yes", "geography": "KY", "subgroup": None,
      "year": 2025, "statistic": "crude_prevalence", "confidence": "high", "abstain_reason": None, "notes": "x"}


def test_valid_spec_passes():
    s = validate(OK)
    assert s.indicator == "_RFSMOK3" and s.geography == "KY"


@pytest.mark.parametrize("patch", [
    {"code": "import os; os.system('rm -rf /')"},
    {"sql": "SELECT * FROM t"},
    {"variable": "SEQNO"},
    {"indicator": "__import__('os')"},
    {"indicator": "SEQNO"},
    {"indicator": "SLEPTIM1"},                       # real BRFSS column, but not in the catalog
    {"response": "Yes; DROP TABLE"},
    {"geography": "CA"},
    {"geography": "Cook County"},
    {"year": 2019},
    {"statistic": "age_adjusted_prevalence"},
    {"statistic": "mean"},
    {"subgroup": {"category": "Veteran", "value": "Yes"}},
    {"subgroup": {"category": "Sex", "value": "Female", "extra": 1}},
    {"subgroup": [{"category": "Sex", "value": "Female"}, {"category": "Age Group", "value": "65+"}]},
    {"confidence": "medium"},
    {"answerable": "yes"},
])
def test_rejections(patch):
    with pytest.raises(GuardError):
        validate({**OK, **patch})


def test_not_json_rejected():
    with pytest.raises(GuardError):
        validate("print('hello')")


def test_abstain_requires_known_reason():
    assert not validate({"answerable": False, "abstain_reason": "wrong_year"}).answerable
    with pytest.raises(GuardError):
        validate({"answerable": False, "abstain_reason": "because"})


def test_executor_reads_only_catalog_variables():
    allowed = catalog.allowed_variables()
    inds, subs = catalog.load()
    assert {i.variable for i in inds.values()} <= allowed
    assert "SEQNO" not in allowed and "IDATE" not in allowed
