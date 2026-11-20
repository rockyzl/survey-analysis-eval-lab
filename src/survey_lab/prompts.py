"""System prompt for NL -> analysis spec. The static catalog comes first so the prefix is cacheable."""
from __future__ import annotations

import json
from functools import lru_cache

from . import catalog
from .spec import ABSTAIN_REASONS

PROMPT_VERSION = "v3"
# v1 -> v2 (dev-driven, 2026-11-20): rule 8 ('how many ... percent' is a prevalence question) and rule 9
# (demographic distribution indicators answer 'what share of adults are X'). See docs/protocol.md addendum A2.
# v2 -> v3: v2 made gpt-4o call single-subgroup questions 'multiple_subgroups'; rule 9 reworded and rule 10
# (geography is never a subgroup) added.


@lru_cache(maxsize=4)
def system_prompt(version: str = PROMPT_VERSION) -> str:
    if version not in ("v1", "v2", "v3"):
        raise ValueError(version)
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
8. "How many adults ... (percent/percentage/share/proportion)" asks for a prevalence, not a count. Abstain with
   "unsupported_statistic" only when the user wants a number of people, a count of respondents or an average.
9. Demographic indicators (EDUCA, INCOME1, RACE8, SEX, AGE, MARITAL, EMPLOY1, VETERAN3, _CHLDCNT) are used
   only when the question asks what share of ALL adults are in that group (e.g. "what share have a college
   degree" -> EDUCA College+; "served in the armed forces" -> VETERAN3 Yes). When the group restricts the
   population of another measure ("among college graduates, what share smoke"), use the subgroup instead.
10. The geography is never a subgroup. One geography plus one characteristic (e.g. "college graduates in
   Michigan", "adults aged 55-64 in Arizona", "adults earning $100,000-$199,999 in Massachusetts") is exactly
   ONE subgroup and is answerable.
"""
    if version == "v1":
        rules = rules[: rules.index("8. ")]
    elif version == "v2":
        rules = rules[: rules.index("9. ")] + V2_RULE9
    return catalog_text + "\n" + rules


V2_RULE9 = """9. Demographic indicators (EDUCA, INCOME1, RACE8, SEX, AGE, MARITAL, EMPLOY1, VETERAN3, _CHLDCNT) answer
   "what share of adults are/have X" (e.g. college degree -> EDUCA College+; served in the armed forces ->
   VETERAN3 Yes). They are indicators here, not subgroups.
"""


def messages(question: str, version: str = PROMPT_VERSION) -> list[dict]:
    return [{"role": "system", "content": system_prompt(version)},
            {"role": "user", "content": question}]
