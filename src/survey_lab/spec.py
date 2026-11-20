"""Analysis spec schema and guard.

The LLM (or the template matcher) may only emit a JSON object with the keys below. The guard rejects
unknown keys, wrong types, and any value that is not in the catalog allow-list. There is no field that
can carry code, SQL, variable names or numbers that end up in the answer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import catalog

ABSTAIN_REASONS = (
    "wrong_year", "geography_unavailable", "unsupported_statistic", "topic_not_in_catalog", "causal_question",
    "multiple_subgroups", "subgroup_not_in_catalog", "not_survey_question", "ambiguous",
)
ALLOWED_KEYS = {"answerable", "abstain_reason", "indicator", "response", "geography", "year", "subgroup",
                "statistic", "confidence", "notes"}
STATISTICS = ("crude_prevalence",)


class GuardError(ValueError):
    pass


@dataclass(frozen=True)
class Spec:
    answerable: bool
    indicator: str | None = None
    response: str | None = None
    geography: str | None = None
    subgroup: tuple[str, str] | None = None   # (category, value)
    abstain_reason: str | None = None
    confidence: str = "high"
    notes: str = field(default="", compare=False)

    def key(self) -> tuple:
        if not self.answerable:
            return ("ABSTAIN",)
        return (self.indicator, self.response, self.geography, self.subgroup)

    def to_dict(self) -> dict:
        return {"answerable": self.answerable, "indicator": self.indicator, "response": self.response,
                "geography": self.geography, "subgroup": list(self.subgroup) if self.subgroup else None,
                "abstain_reason": self.abstain_reason, "confidence": self.confidence}


def abstain(reason: str, notes: str = "") -> Spec:
    if reason not in ABSTAIN_REASONS:
        raise GuardError(f"unknown abstain_reason {reason!r}")
    return Spec(answerable=False, abstain_reason=reason, notes=notes)


def validate(obj) -> Spec:
    """Validate a parsed JSON object (or JSON string) against the schema and the catalog allow-list."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError as e:
            raise GuardError(f"not valid JSON: {e}") from None
    if not isinstance(obj, dict):
        raise GuardError("spec must be a JSON object")
    extra = set(obj) - ALLOWED_KEYS
    if extra:
        raise GuardError(f"unknown keys: {sorted(extra)}")
    ans = obj.get("answerable")
    if not isinstance(ans, bool):
        raise GuardError("'answerable' must be true or false")
    conf = obj.get("confidence", "high")
    if conf not in ("high", "low"):
        raise GuardError("'confidence' must be 'high' or 'low'")
    notes = obj.get("notes") or ""
    if not isinstance(notes, str) or len(notes) > 500:
        raise GuardError("'notes' must be a short string")
    if not ans:
        reason = obj.get("abstain_reason")
        if reason not in ABSTAIN_REASONS:
            raise GuardError(f"abstain_reason must be one of {ABSTAIN_REASONS}")
        return Spec(answerable=False, abstain_reason=reason, confidence=conf, notes=notes)

    inds, subs = catalog.load()
    ind = obj.get("indicator")
    if not isinstance(ind, str) or ind not in inds:
        raise GuardError(f"indicator {ind!r} is not in the catalog")
    resp = obj.get("response")
    if not isinstance(resp, str) or resp not in inds[ind].responses:
        raise GuardError(f"response {resp!r} is not a category of {ind}")
    geo = obj.get("geography")
    if not isinstance(geo, str) or geo not in catalog.geographies():
        raise GuardError(f"geography {geo!r} is not available in the 2025 data")
    year = obj.get("year", catalog.DATA_YEAR)
    if year != catalog.DATA_YEAR:
        raise GuardError(f"year {year!r} is not available (only {catalog.DATA_YEAR})")
    stat = obj.get("statistic", "crude_prevalence")
    if stat not in STATISTICS:
        raise GuardError(f"statistic {stat!r} is not supported")
    sg = obj.get("subgroup")
    sub = None
    if sg is not None:
        if not isinstance(sg, dict) or set(sg) != {"category", "value"}:
            raise GuardError("subgroup must be null or {category, value}")
        cat, val = sg["category"], sg["value"]
        if cat not in subs or val not in subs[cat]:
            raise GuardError(f"subgroup {cat!r}={val!r} is not in the catalog")
        sub = (cat, val)
    return Spec(answerable=True, indicator=ind, response=resp, geography=geo, subgroup=sub,
                confidence=conf, notes=notes)
