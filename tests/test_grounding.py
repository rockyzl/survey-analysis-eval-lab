"""Answers may only contain numbers that the executor produced."""
from survey_lab import answer
from survey_lab.executor import Result
from survey_lab.spec import abstain, validate

SPEC = validate({"answerable": True, "indicator": "_RFHLTH", "response": "Fair or Poor Health", "geography": "WA",
                 "subgroup": {"category": "Age Group", "value": "65+"}})
RES = Result(estimate=17.3076, ci_low=16.637, ci_high=17.978, se=0.342, n_yes=3644, n_denom=19449)


def test_rendered_answer_is_grounded():
    text = answer.render(SPEC, RES)
    assert "17.3%" in text and "16.6" in text and "18.0" in text and "3,644" in text
    assert answer.check_grounding(text, SPEC, RES) == []


def test_fabricated_number_detected():
    text = answer.render(SPEC, RES).replace("17.3%", "21.4%")
    assert answer.check_grounding(text, SPEC, RES) == ["21.4"]


def test_extra_claim_detected():
    text = answer.render(SPEC, RES) + " This is up 2.1 points since 2019."
    assert set(answer.check_grounding(text, SPEC, RES)) == {"2.1", "2019"}


def test_median_answer_grounded():
    spec = validate({"answerable": True, "indicator": "_RFSMOK3", "response": "Yes", "geography": "US_MEDIAN",
                     "subgroup": None})
    res = Result(estimate=11.95, n_jurisdictions=50)
    text = answer.render(spec, res)
    assert "median" in text and "not a pooled national prevalence" in text
    assert answer.check_grounding(text, spec, res) == []


def test_abstention_has_no_numbers():
    s = abstain("wrong_year")
    assert answer.check_grounding(answer.render(s, None), s, None) == []
