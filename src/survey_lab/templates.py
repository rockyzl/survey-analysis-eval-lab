"""Deterministic template matcher (path a: no LLM).

Returns a Spec only when it is confident. It needs exactly one geography, exactly one indicator pattern, at most
one subgroup pattern, and no "trap" wording (other years, age-adjusted, averages, counts, sub-state areas,
causal wording, comparisons, multiple restrictions). Otherwise it returns None, and the router falls through to
an LLM.
"""
from __future__ import annotations

import re

from . import catalog
from .spec import Spec

# (regex, indicator, response, exclusion regex or None); first match per indicator wins
INDICATOR_PATTERNS: list[tuple[str, str, str, str | None]] = [
    (r"\bobes(e|ity)\b", "_BMI5CAT", "Obese (BMI 30.0 - 99.8)", None),
    (r"\boverweight\b", "_BMI5CAT", "Overweight (BMI 25.0-29.9)", r"obes"),
    (r"\bunderweight\b", "_BMI5CAT", "Underweight (BMI 12.0-18.4)", None),
    (r"\bnormal weight\b", "_BMI5CAT", "Normal Weight (BMI 18.5-24.9)", None),
    (r"\b(current(ly)? (cigarette )?smok\w*|smok(ing|er)s? (rate|prevalence)|cigarette smoking|currently smoke|who smoke|smoke cigarettes|current smokers?)\b",
     "_RFSMOK3", "Yes", r"e-?cig|vap|never|former|every ?day|daily|some days|chew|smokeless"),
    (r"\bformer smokers?\b", "_SMOKER3", "Former smoker", None),
    (r"\bnever smoked\b", "_SMOKER3", "Never smoked", None),
    (r"\bfair or poor (general )?health\b|\bfair/poor health\b", "_RFHLTH", "Fair or Poor Health", None),
    (r"\b(high blood pressure|hypertension)\b", "_RFHYPE6", "Yes", None),
    (r"\bhigh cholesterol\b|\bcholesterol\b.*\bhigh\b", "_RFCHOL3", "Yes", None),
    (r"\b(pre-?diabetes|borderline diabetes)\b", "DIABETE4", "No, pre-diabetes or borderline diabetes", None),
    (r"\bdiabet(es|ic)\b", "DIABETE4", "Yes", r"pre-?diabet|borderline|pregnan|gestational"),
    (r"\b(depression|depressive disorder)\b", "ADDEPEV3", "Yes", None),
    (r"\bbinge (drink\w*)\b", "_RFBING6", "Yes", None),
    (r"\bheavy drink\w*\b", "_RFDRHV9", "Meet criteria for heavy drinking", None),
    (r"\b(physical(ly)? inactiv\w*|no leisure[- ]time (physical )?activity|no physical activity)\b", "_TOTINDA", "No", None),
    (r"\bcurrent asthma\b|\bcurrently (have|has) asthma\b", "_CASTHM1", "Yes", None),
    (r"\bever (been )?(told|diagnosed)\b.*\basthma\b", "_LTASTH1", "Yes", r"current"),
    (r"\bcopd\b|\bemphysema\b|\bchronic bronchitis\b", "CHCCOPD3", "Yes", None),
    (r"\barthritis\b", "_DRDXAR2", "Yes", None),
    (r"\bkidney disease\b", "CHCKDNY2", "Yes", None),
    (r"\bstroke\b", "CVDSTRK3", "Yes", None),
    (r"\bheart attack\b|\bmyocardial infarction\b", "CVDINFR4", "Yes", r"coronary|angina"),
    (r"\bflu (shot|vaccin\w*)\b|\binfluenza vaccin\w*\b", "_FLSHOT7", "Yes", None),
    (r"\bpneumonia (vaccin\w*|shot)\b|\bpneumococcal\b", "_PNEUMO3", "Yes", None),
    (r"\bhiv test\w*\b|\btested for hiv\b", "HIVTST7", "Yes", None),
    (r"\bveterans?\b|\bserved in the (armed forces|military)\b", "VETERAN3", "Yes", None),
    (r"\b(14|fourteen) or more days of poor mental health\b|\bfrequent mental distress\b|\b14\+ days of poor mental health\b",
     "_MENT14D", "14+ days when mental health not good", None),
    (r"\bfrequent physical distress\b|\b14\+ (bad |days of poor )?physical health\b", "_PHYS14D", "14+ days when physical health not good", None),
    (r"\b(could not|couldn't|could not afford to) see a doctor\b.*\bcost\b|\bcost\b.*\bbarrier\b", "MEDCOST1", "Yes", None),
    (r"\bno personal doctor\b|\bwithout a personal doctor\b", "PERSDOC3", "No", None),
]
UNINSURED = r"\b(uninsured|without (any )?health insurance|no health insurance|without health (care )?coverage)\b"

SUBGROUP_PATTERNS: list[tuple[str, str, str]] = [
    (r"\b(women|female)\b", "Sex", "Female"),
    (r"\b(men|male)\b", "Sex", "Male"),
    (r"\b(aged |ages )?(65 (and|or) older|65 years and older|65 or over)\b|\b65\+", "Age Group", "65+"),
    (r"\b(aged |ages )?18[- ]?(to|-)[- ]?24\b( year[- ]olds?)?", "Age Group", "18-24"),
    (r"\b(aged |ages )?25[- ]?(to|-)[- ]?34\b( year[- ]olds?)?", "Age Group", "25-34"),
    (r"\b(aged |ages )?35[- ]?(to|-)[- ]?44\b( year[- ]olds?)?", "Age Group", "35-44"),
    (r"\b(aged |ages )?45[- ]?(to|-)[- ]?54\b( year[- ]olds?)?", "Age Group", "45-54"),
    (r"\b(aged |ages )?55[- ]?(to|-)[- ]?64\b( year[- ]olds?)?", "Age Group", "55-64"),
    (r"(?<!non-)(?<!non )\bhispanic\b", "Race/Ethnicity", "Hispanic"),
    (r"\bblack\b", "Race/Ethnicity", "Black, non-Hispanic"),
    (r"\bwhite\b", "Race/Ethnicity", "White, non-Hispanic"),
    (r"\basian\b", "Race/Ethnicity", "Asian, non-Hispanic"),
    (r"\bcollege grad\w*\b", "Education Attained", "College graduate"),
    (r"\b(without a high school diploma|less than (a )?high school)\b", "Education Attained", "Less than H.S."),
    (r"\b(under|below|less than) \$15,000\b", "Household Income", "Less than $15,000"),
]
TRAPS = [
    r"\b(19|20)\d\d\b(?<!2025)", r"age[- ]adjusted", r"\baverage\b", r"\bmean\b", r"\bmedian\b", r"how many people",
    r"number of (people|adults|respondents)", r"\bcount(y|ies)\b", r"\bcity\b", r"\bwhy\b", r"\bcause", r"\btrend",
    r"\bchange", r"\bcompar", r"\bversus\b|\bvs\.?\b", r"\bsignifican", r"\bregression\b", r"\bpredict", r"\bforecast",
    r"\bhighest\b|\blowest\b|\brank", r"\bchildren\b|\bkids\b", r"\bpregnan", r"\bcode\b|\bpython\b|\bignore\b",
    r"\braw\b", r"\brural\b|\burban\b", r"\blgbt", r"\bsorry\b", r"\bdisabilit",
]
# restriction wording that must be fully explained by a recognised subgroup, otherwise the matcher defers
RESTRICTION = (r"\$\d|\bincome|\bearning|\bmultiracial|\bnative hawaiian|\bpacific islander|\bamerican indian|"
               r"\balaska(n)? native|\bsome college|\bhigh school|\bged\b|\bdegree|\b\d\d\+|\baged\b|\bages\b|"
               r"year[- ]olds?|\bolder\b|\byounger\b|\bwomen\b|\bmen\b|\bfemale|\bmale|\bhispanic|\bblack|\bwhite|"
               r"\basian|\bcollege|\bseniors?\b|\bveterans?\b")
NATIONAL = r"\b(nationally|nationwide|national|in the (us|u\.s\.|united states)|us adults|american adults|across the us)\b"


def _geographies(q: str) -> set[str]:
    found = set()
    for abbr, name in [v for v in catalog.STATES.values()] + [(k, v) for k, v in catalog.NOT_IN_2025.items()]:
        if re.search(rf"\b{re.escape(name.lower())}\b", q):
            found.add(abbr)
    # 'Washington, DC' vs 'Washington'
    if "DC" in found and "WA" in found and "washington state" not in q:
        found.discard("WA")
    if re.search(r"\b(west virginia)\b", q):
        found.discard("VA")
    for abbr in list(catalog.ABBR_TO_FIPS) + list(catalog.NOT_IN_2025):
        if abbr in ("IN", "OR", "ME", "OK", "HI", "DE", "PA", "MA", "AL", "CO", "ID", "MO", "LA", "GA", "OH", "WA"):
            continue   # ambiguous as words; require the full name or an uppercase code in the original text
        if re.search(rf"\b{abbr.lower()}\b", q):
            found.add(abbr)
    if re.search(NATIONAL, q):
        found.add("US_MEDIAN")
    return found


def match(question: str) -> Spec | None:
    q = question.lower().strip()
    orig = question
    if any(re.search(t, q) for t in TRAPS):
        return None
    geos = _geographies(q)
    for abbr in ("IN", "OR", "ME", "OK", "HI", "DE", "PA", "MA", "AL", "CO", "ID", "MO", "LA", "GA", "OH", "WA", "NC", "SC", "DC"):
        if re.search(rf"\b{abbr}\b", orig):
            geos.add(abbr)
    if len(geos) != 1:
        return None
    geo = geos.pop()
    if geo in catalog.NOT_IN_2025:
        return None
    hits = set()
    for pat, ind, resp, excl in INDICATOR_PATTERNS:
        if re.search(pat, q) and not (excl and re.search(excl, q)):
            hits.add((ind, resp))
    if re.search(UNINSURED, q):
        hits.add(("_HCVU654" if re.search(r"18[- ]?(to|-)[- ]?64", q) else "_HLTHPL2",
                  "Do not have some form of health insurance"))
    if len(hits) != 1:
        return None
    ind, resp = hits.pop()
    subs = set()
    residual = q
    for pat, cat, val in SUBGROUP_PATTERNS:
        if re.search(pat, q):
            subs.add((cat, val))
            residual = re.sub(pat, " ", residual)
    # indicator wording that legitimately contains restriction words
    for pat, *_ in INDICATOR_PATTERNS:
        residual = re.sub(pat, " ", residual)
    residual = re.sub(r"\b(65\+|65 (and|or) older|18[- ]?(to|-)[- ]?64)\b|\b65\+", " ", residual) if ind in (
        "_FLSHOT7", "_PNEUMO3", "_HCVU654") else residual
    if sub_cats := {c for c, _ in subs}:
        if "Race/Ethnicity" in sub_cats:
            residual = re.sub(r"non-?\s?hispanic", " ", residual)
    if re.search(RESTRICTION, residual):
        return None
    if ("Sex", "Male") in subs and ("Sex", "Female") in subs:
        return None
    if ind in ("_FLSHOT7", "_PNEUMO3"):
        subs.discard(("Age Group", "65+"))
    if ind == "_HCVU654":
        subs = {s for s in subs if s[0] != "Age Group"}
    if len(subs) > 1:
        return None
    sub = subs.pop() if subs else None
    if sub and geo in catalog.MEDIAN_GEOS:
        return None   # median break-outs are not in scope for the template path
    return Spec(answerable=True, indicator=ind, response=resp, geography=geo, subgroup=sub, confidence="high",
                notes="template match")
