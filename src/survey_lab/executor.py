"""Deterministic, guarded execution of a validated Spec. No code from the LLM is ever run."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from . import catalog, data, survey
from .spec import Spec


@dataclass
class Result:
    estimate: float | None            # percent
    ci_low: float | None = None
    ci_high: float | None = None
    se: float | None = None
    n_yes: int | None = None
    n_denom: int | None = None
    suppressed: bool = False
    n_jurisdictions: int | None = None
    trace: dict = field(default_factory=dict)


def _masks(df, spec: Spec):
    ind = catalog.indicators()[spec.indicator]
    x = df[ind.variable]
    valid = x.isin(ind.valid).values
    y = x.isin(ind.responses[spec.response]).values.astype(float)
    sub = np.ones(len(df), bool)
    keep = valid.copy()
    sub_trace = None
    if spec.subgroup:
        sv = catalog.subgroups()[spec.subgroup[0]][spec.subgroup[1]]
        sub = df[sv.variable].isin(sv.codes).values
        keep &= df[sv.variable].isin(sv.universe).values
        sub_trace = {"category": sv.category, "value": sv.label, "variable": sv.variable, "codes": list(sv.codes),
                     "dropped": "records with a missing value on the break-out variable (CDC P&T convention)"}
    trace = {
        "indicator": ind.id, "topic": ind.topic, "variable": ind.variable,
        "numerator_codes": list(ind.responses[spec.response]), "denominator_codes": list(ind.valid),
        "denominator_rule": "respondents with a code in denominator_codes; don't know/refused/missing/out-of-universe codes excluded",
        "universe": ind.universe, "subgroup": sub_trace,
        "weight": "_LLCPWT", "strata": "_STSTR", "psu": "_PSU",
        "variance": "Taylor linearization, full-design domain estimation, single-PSU strata contribute 0, Wald 95% CI",
        "year": catalog.DATA_YEAR,
    }
    return y, valid, sub, keep, trace


def execute(spec: Spec) -> Result:
    if not spec.answerable:
        raise ValueError("cannot execute an abstention")
    r = _execute_cached(spec.key())
    return Result(**{**r.__dict__, "trace": dict(r.trace)})


@lru_cache(maxsize=4096)
def _execute_cached(key: tuple) -> Result:
    ind, resp, geo, sub = key
    spec = Spec(answerable=True, indicator=ind, response=resp, geography=geo, subgroup=sub)
    df = data.load()
    y, valid, sub, keep, trace = _masks(df, spec)
    y, valid, sub = y[keep], valid[keep], sub[keep]
    fips = df["_STATE"].astype(int).values[keep]
    w, h, psu = df["_LLCPWT"].values[keep], df["_STSTR"].values[keep], df["_PSU"].values[keep]
    if spec.geography in catalog.MEDIAN_GEOS:
        juris = [f for f in catalog.STATES if spec.geography == "US_MEDIAN" or f not in catalog.TERRITORIES]
        dom = np.where(np.isin(fips, juris) & sub, fips, -1)
        est = survey.domain_proportions(y, valid, dom, w, h, psu)
        keep = list(est.index)   # CDC median uses every jurisdiction estimate, suppressed or not (Gate 0 finding)
        vals = est.loc[keep, "p"] * 100
        trace.update(geography=spec.geography, geography_rule=catalog.MEDIAN_GEOS[spec.geography]
                     + "; median of all jurisdiction estimates incl. ones CDC suppresses, no CI (CDC P&T convention)",
                     jurisdictions=sorted(catalog.STATES[int(g)][0] for g in keep))
        if len(vals) == 0:
            return Result(estimate=None, suppressed=True, trace=trace)
        return Result(estimate=float(np.median(vals)), n_jurisdictions=int(len(vals)), trace=trace)
    f = catalog.ABBR_TO_FIPS[spec.geography]
    dom = np.where((fips == f) & sub, 0, -1)
    est = survey.domain_proportions(y, valid, dom, w, h, psu)
    trace.update(geography=spec.geography, geography_rule=f"_STATE == {f} ({catalog.geo_label(spec.geography)})")
    if len(est) == 0:
        return Result(estimate=None, suppressed=True, n_denom=0, trace=trace)
    r = est.iloc[0]
    supp = survey.suppressed(r.p, r.se, int(r.n_denom), int(r.n_yes))
    res = Result(estimate=float(r.p * 100), ci_low=float(r.ci_low * 100), ci_high=float(r.ci_high * 100),
                 se=float(r.se * 100), n_yes=int(r.n_yes), n_denom=int(r.n_denom), suppressed=supp, trace=trace)
    if supp:
        res.estimate = res.ci_low = res.ci_high = None
    return res
