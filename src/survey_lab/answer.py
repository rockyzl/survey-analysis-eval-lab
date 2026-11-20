"""Deterministic answer rendering and the grounding check.

The answer text is produced only from the executed Result. check_grounding() verifies that every number
in an answer string is either an executed result value (as formatted) or an allowed constant.
"""
from __future__ import annotations

import re

from . import catalog
from .executor import Result
from .spec import Spec

ALLOWED_CONSTANTS = {"2025", "95", "50", "0.3", "30"}
_NUM = re.compile(r"(?<![A-Za-z_])\d[\d,]*(?:\.\d+)?")
REASON_TEXT = {
    "wrong_year": "only the 2025 BRFSS file is loaded",
    "geography_unavailable": "that geography is not available in the 2025 BRFSS file (state level only; CA, MS and NV did not contribute 2025 data)",
    "unsupported_statistic": "only crude prevalence (weighted percent) is supported, not age-adjusted rates, means, counts or trends",
    "topic_not_in_catalog": "that measure is not in the curated catalog of BRFSS indicators",
    "causal_question": "a descriptive survey cannot answer causal or 'why' questions",
    "multiple_subgroups": "only one subgroup filter is supported per question",
    "subgroup_not_in_catalog": "that subgroup is not one of the supported breakouts (sex, age group, race/ethnicity, education, income)",
    "not_survey_question": "the question is not about the BRFSS survey data",
    "ambiguous": "the question is ambiguous; please specify the measure, the geography and the subgroup",
}


def fmt(x: float) -> str:
    return f"{x:.1f}"


def render(spec: Spec, res: Result | None) -> str:
    if not spec.answerable:
        return f"I can't answer this from the data: {REASON_TEXT.get(spec.abstain_reason, spec.abstain_reason)}."
    ind = catalog.indicators()[spec.indicator]
    who = "adults"
    if spec.subgroup:
        who = f"adults in subgroup {spec.subgroup[0]} = {spec.subgroup[1]}"
    where = catalog.geo_label(spec.geography)
    if res is None or res.estimate is None:
        return (f"{where}, 2025 BRFSS, {ind.topic} = '{spec.response}' among {who}: the estimate is suppressed "
                f"(unweighted denominator below 50 or relative standard error above 0.3).")
    if spec.geography in catalog.MEDIAN_GEOS:
        return (f"{where}, 2025 BRFSS: the median across {res.n_jurisdictions} jurisdictions of the crude prevalence of "
                f"{ind.topic} = '{spec.response}' among {who} is {fmt(res.estimate)}%. "
                f"This is a median of jurisdiction estimates (CDC convention), not a pooled national prevalence, "
                f"and has no confidence interval.")
    return (f"{where}, 2025 BRFSS: {fmt(res.estimate)}% (95% CI {fmt(res.ci_low)}-{fmt(res.ci_high)}%) of {who} "
            f"reported {ind.topic} = '{spec.response}' (survey-weighted crude prevalence; {res.n_yes:,} of "
            f"{res.n_denom:,} respondents with a valid answer).")


def allowed_numbers(spec: Spec, res: Result | None) -> set[str]:
    nums = set(ALLOWED_CONSTANTS)
    if res is not None:
        for v in (res.estimate, res.ci_low, res.ci_high):
            if v is not None:
                nums.add(fmt(v))
        for v in (res.n_yes, res.n_denom, res.n_jurisdictions):
            if v is not None:
                nums.update({str(v), f"{v:,}"})
    # numbers that are part of catalog labels (e.g. '65+', '$50,000', 'BMI 30.0') are grounded in the catalog
    text = " ".join(filter(None, [spec.response or "", spec.subgroup[1] if spec.subgroup else "",
                                  catalog.indicators()[spec.indicator].topic if spec.indicator else ""]))
    nums.update(_NUM.findall(text))
    return nums


def check_grounding(text: str, spec: Spec, res: Result | None) -> list[str]:
    """Return the numbers in `text` that are not grounded in the executed result (empty list = grounded)."""
    allowed = allowed_numbers(spec, res)
    return [n for n in _NUM.findall(text) if n not in allowed and n.replace(",", "") not in allowed]
