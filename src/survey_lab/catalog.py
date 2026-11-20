"""Analysis catalog: the allow-list of indicators, response categories, subgroups and geographies.

Everything the LLM may reference must appear here. The executor reads only variables listed here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from .paths import CATALOG

DATA_YEAR = 2025
DESIGN_VARS = ("_STATE", "_STSTR", "_PSU", "_LLCPWT")

# FIPS -> (postal abbreviation, name). Jurisdictions present in the 2025 LLCP file.
STATES = {
    1: ("AL", "Alabama"), 2: ("AK", "Alaska"), 4: ("AZ", "Arizona"), 5: ("AR", "Arkansas"),
    8: ("CO", "Colorado"), 9: ("CT", "Connecticut"), 10: ("DE", "Delaware"), 11: ("DC", "District of Columbia"),
    12: ("FL", "Florida"), 13: ("GA", "Georgia"), 15: ("HI", "Hawaii"), 16: ("ID", "Idaho"),
    17: ("IL", "Illinois"), 18: ("IN", "Indiana"), 19: ("IA", "Iowa"), 20: ("KS", "Kansas"),
    21: ("KY", "Kentucky"), 22: ("LA", "Louisiana"), 23: ("ME", "Maine"), 24: ("MD", "Maryland"),
    25: ("MA", "Massachusetts"), 26: ("MI", "Michigan"), 27: ("MN", "Minnesota"), 29: ("MO", "Missouri"),
    30: ("MT", "Montana"), 31: ("NE", "Nebraska"), 33: ("NH", "New Hampshire"), 34: ("NJ", "New Jersey"),
    35: ("NM", "New Mexico"), 36: ("NY", "New York"), 37: ("NC", "North Carolina"), 38: ("ND", "North Dakota"),
    39: ("OH", "Ohio"), 40: ("OK", "Oklahoma"), 41: ("OR", "Oregon"), 42: ("PA", "Pennsylvania"),
    44: ("RI", "Rhode Island"), 45: ("SC", "South Carolina"), 46: ("SD", "South Dakota"), 47: ("TN", "Tennessee"),
    48: ("TX", "Texas"), 49: ("UT", "Utah"), 50: ("VT", "Vermont"), 51: ("VA", "Virginia"),
    53: ("WA", "Washington"), 54: ("WV", "West Virginia"), 55: ("WI", "Wisconsin"), 56: ("WY", "Wyoming"),
    66: ("GU", "Guam"), 72: ("PR", "Puerto Rico"),
}
# States that exist but did not contribute 2025 data (used for explicit abstention messages).
NOT_IN_2025 = {"CA": "California", "MS": "Mississippi", "NV": "Nevada", "VI": "U.S. Virgin Islands"}
TERRITORIES = {66, 72}
ABBR_TO_FIPS = {a: f for f, (a, _) in STATES.items()}

# Aggregate geographies, following CDC P&T conventions (medians of jurisdiction estimates, no CI).
MEDIAN_GEOS = {
    "US_MEDIAN": "All States, DC and Territories (median)",   # P&T locationabbr 'US'
    "STATES_DC_MEDIAN": "All States and DC (median)",        # P&T locationabbr 'UW'
}
PT_LOCATION = {**{a: a for a in ABBR_TO_FIPS}, "US_MEDIAN": "US", "STATES_DC_MEDIAN": "UW"}


@dataclass(frozen=True)
class Indicator:
    id: str
    variable: str
    topic: str
    valid: tuple[int, ...]
    responses: dict[str, tuple[int, ...]]
    synonyms: tuple[str, ...]
    universe: str | None = None


@dataclass(frozen=True)
class SubgroupValue:
    category: str
    label: str
    variable: str
    codes: tuple[int, ...]


@lru_cache(maxsize=1)
def load() -> tuple[dict[str, Indicator], dict[str, dict[str, SubgroupValue]]]:
    raw = json.loads((CATALOG / "indicators.json").read_text())
    inds = {}
    for k, v in raw["indicators"].items():
        inds[k] = Indicator(id=k, variable=v["variable"], topic=v["topic"], valid=tuple(v["valid"]),
                            responses={r: tuple(c) for r, c in v["responses"].items()},
                            synonyms=tuple(v.get("synonyms", ())), universe=v.get("universe"))
    subs: dict[str, dict[str, SubgroupValue]] = {}
    for cat, s in raw["subgroups"].items():
        subs[cat] = {}
        for lab, val in s["values"].items():
            if isinstance(val, dict):
                subs[cat][lab] = SubgroupValue(cat, lab, val["variable"], tuple(val["codes"]))
            else:
                subs[cat][lab] = SubgroupValue(cat, lab, s["variable"], tuple(val))
    return inds, subs


def indicators() -> dict[str, Indicator]:
    return load()[0]


def subgroups() -> dict[str, dict[str, SubgroupValue]]:
    return load()[1]


def allowed_variables() -> set[str]:
    inds, subs = load()
    v = {i.variable for i in inds.values()} | {sv.variable for c in subs.values() for sv in c.values()}
    return v | set(DESIGN_VARS)


def geographies() -> list[str]:
    return list(ABBR_TO_FIPS) + list(MEDIAN_GEOS)


def geo_label(geo: str) -> str:
    if geo in MEDIAN_GEOS:
        return MEDIAN_GEOS[geo]
    return STATES[ABBR_TO_FIPS[geo]][1]
