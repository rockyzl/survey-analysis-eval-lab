"""System prompt for NL -> analysis spec. The static catalog comes first so the prefix is cacheable."""
from __future__ import annotations

import json
from functools import lru_cache

from . import catalog
from .spec import ABSTAIN_REASONS

PROMPT_VERSION = "v1"


@lru_cache(maxsize=4)
def system_prompt(version: str = PROMPT_VERSION) -> str:
    inds, subs = catalog.load()
    lines = ["INDICATOR CATALOG (indicator id: topic -> allowed response values):"]
    for i in inds.values():
        u = f" [universe: {i.universe}]" if i.universe else ""
        lines.append(f"- {i.id}: {i.topic}{u} -> {json.dumps(list(i.responses))}")
    lines.append("\nSUBGROUP CATALOG (category -> allowed values):")
    for cat, vals in subs.items():
        lines.append(f"- {cat} -> {json.dumps(list(vals))}")
    geos = ", ".join(f"{a}={n}" for a, n in sorted(catalog.STATES.values()))
    lines.append(f"\nGEOGRAPHIES (2025 data): {geos}")
    lines.append("Aggregates: US_MEDIAN = median across all states, DC and territories (use for 'US', 'national', "
                 "'nationwide', 'American adults'); STATES_DC_MEDIAN = median across the states and DC only "
                 "(use only when the question explicitly excludes territories or says states and DC).")
    lines.append(f"Not available: {', '.join(catalog.NOT_IN_2025.values())}, and any county, city or other sub-state area.")
    catalog_text = "\n".join(lines)
    rules = f"""
You translate a user's question about the CDC BRFSS 2025 survey into a JSON analysis spec. You never compute
numbers and never write code. A separate deterministic program executes the spec.

Return ONLY a JSON object with exactly these keys:
{{"answerable": true|false,
  "indicator": <indicator id from the catalog or null>,
  "response": <one allowed response value of that indicator, copied exactly, or null>,
  "geography": <state postal code, US_MEDIAN or STATES_DC_MEDIAN, or null>,
  "year": 2025,
  "subgroup": null or {{"category": <subgroup category>, "value": <allowed value copied exactly>}},
  "statistic": "crude_prevalence",
  "abstain_reason": null or one of {json.dumps(list(ABSTAIN_REASONS))},
  "confidence": "high" or "low",
  "notes": <one short sentence>}}

Rules:
1. The only statistic is crude prevalence (weighted percent) for 2025. Abstain with "wrong_year" for any other
   year, trends or forecasts; "unsupported_statistic" for age-adjusted rates, means/averages, medians of a
   variable, counts of people, rankings, significance tests, regressions or comparisons that need two estimates.
2. Abstain with "geography_unavailable" for California, Mississippi, Nevada, the Virgin Islands, counties, cities,
   or combinations of several geographies.
3. Abstain with "topic_not_in_catalog" if no catalog indicator measures the asked topic. Do not substitute a
   related indicator.
4. At most ONE subgroup. If the question restricts on two or more characteristics (e.g. Hispanic women,
   women aged 65+), abstain with "multiple_subgroups". If the restriction is not a catalog subgroup (e.g.
   veterans, rural, LGBT, children, pregnant women), abstain with "subgroup_not_in_catalog".
   Exception: an age restriction that is part of an indicator's universe (flu shot / pneumonia vaccine 65+,
   insurance 18-64) is not a subgroup.
5. Abstain with "causal_question" for why/cause/effect questions and "not_survey_question" for anything that is
   not a request for BRFSS estimates (including requests for code or raw data).
6. Pick the indicator that defines the asked measure most directly (e.g. current smoking -> _RFSMOK3 Yes;
   obesity -> _BMI5CAT Obese; physical inactivity -> _TOTINDA No; uninsured adults -> _HLTHPL2; uninsured
   adults aged 18-64 -> _HCVU654; high blood pressure -> _RFHYPE6 Yes; diabetes -> DIABETE4 Yes).
7. Set "confidence" to "low" if you are unsure which indicator, response, subgroup or geography is meant.
"""
    return catalog_text + "\n" + rules


def messages(question: str, version: str = PROMPT_VERSION) -> list[dict]:
    return [{"role": "system", "content": system_prompt(version)},
            {"role": "user", "content": question}]
