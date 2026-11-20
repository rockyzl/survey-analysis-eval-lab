"""Gate 0: reproduce CDC BRFSS P&T 2025 crude prevalence with deterministic, hand-specified code.

Writes results/gate0_cells.csv.gz (every compared cell) and results/gate0_summary.json.
Conventions (see docs/protocol.md addendum A1): v2 (default) drops records with a missing break-out value
and truncates CIs to [0, 100]. `--v1` reproduces the prespecified first run (full-design domain estimation
of break-outs, unclipped CIs); its archived output is in results/gate0_v1_prespecified/.
Note: the v1 archive also used _RACE instead of _RACEPRV for race (catalog fix A1.1).
"""
import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from survey_lab import catalog, data, reference, survey  # noqa: E402
from survey_lab.paths import RESULTS, ROOT  # noqa: E402

V1 = "--v1" in sys.argv
PROTO = json.loads((ROOT / "protocol.json").read_text())
TOL = PROTO["gate0"]["tolerance_pp"]
t0 = time.time()
df = data.load()
inds, subs = catalog.load()
fips = df["_STATE"].astype(int).values
state_codes = sorted(catalog.STATES)
sidx = np.full(100, -1); sidx[state_codes] = np.arange(len(state_codes))
st = sidx[fips]
w = df["_LLCPWT"].values; h = df["_STSTR"].values; psu = df["_PSU"].values

# passes: list of (category, {label: mask}) with disjoint masks inside each pass
passes = [("Overall", {"Overall": np.ones(len(df), bool)}, np.ones(len(df), bool))]
for cat, vals in subs.items():
    groups: dict[str, list] = {}
    for lab, sv in vals.items():
        groups.setdefault(sv.variable, []).append(sv)
    for var, svs in groups.items():
        universe = df[var].isin(svs[0].universe).values
        passes.append((cat, {sv.label: df[sv.variable].isin(sv.codes).values for sv in svs},
                       np.ones(len(df), bool) if V1 else universe))

rows = []
for qid, ind in inds.items():
    x = df[ind.variable]
    valid = x.isin(ind.valid).values
    for resp, codes in ind.responses.items():
        y = x.isin(codes).values.astype(float)
        for cat, masks, keep in passes:
            labels = list(masks)
            bo = np.full(len(df), -1)
            for j, lab in enumerate(labels):
                bo[masks[lab]] = j
            dom = np.where((st >= 0) & (bo >= 0), st * len(labels) + bo, -1)
            k = keep & valid
            est = survey.domain_proportions(y[k], valid[k], dom[k], w[k], h[k], psu[k], clip=not V1)
            for g, r in est.iterrows():
                s, j = divmod(int(g), len(labels))
                rows.append(dict(questionid=qid, response=resp, locationabbr=catalog.STATES[state_codes[s]][0],
                                 break_out_category=cat, break_out=labels[j], est=r.p * 100, se=r.se * 100,
                                 lo=r.ci_low * 100, hi=r.ci_high * 100, n_yes=int(r.n_yes), n_denom=int(r.n_denom),
                                 supp=survey.suppressed(r.p, r.se, int(r.n_denom), None if V1 else int(r.n_yes))))
    print(qid, round(time.time() - t0), "s", flush=True)

mine = pd.DataFrame(rows)
ref = reference.load()
key = ["questionid", "response", "locationabbr", "break_out_category", "break_out"]
cells = ref[ref.locationabbr.isin([a for a, _ in catalog.STATES.values()])].merge(mine, on=key, how="left")
cells["ref_published"] = cells.data_value.notna()
cells["d_point"] = cells.est - cells.data_value
cells["d_lo"] = cells.lo - cells.confidence_limit_low
cells["d_hi"] = cells.hi - cells.confidence_limit_high
cells["ok_point"] = cells.d_point.abs() <= TOL["point"] + 1e-9
cells["ok_ci"] = (cells.d_lo.abs() <= TOL["ci_low"] + 1e-9) & (cells.d_hi.abs() <= TOL["ci_high"] + 1e-9)
cells["reproduced"] = cells.ok_point & cells.ok_ci
cells["ok_n"] = cells.n_yes == cells.sample_size
cells["cdc_suppressed"] = ~cells.ref_published
cells["supp_agree"] = cells.supp.astype("boolean").fillna(True).astype(bool) == cells.cdc_suppressed

# medians (US = all 50 jurisdictions incl. territories; UW = states + DC)
med_rows = []
ov = mine[mine.break_out_category == "Overall"]
for (qid, resp), g in ov.groupby(["questionid", "response"]):
    if V1:
        g = g[~g.supp]   # v1: median over non-suppressed jurisdictions only
    for loc, sel in (("US", g), ("UW", g[~g.locationabbr.isin(["GU", "PR"])])):
        r = reference.lookup(qid, resp, loc)
        if r is None or pd.isna(r.data_value):
            continue
        med_rows.append(dict(questionid=qid, response=resp, locationabbr=loc, est=float(np.median(sel.est)),
                             n_juris=len(sel), ref=r.data_value, ref_n=r.sample_size))
med = pd.DataFrame(med_rows)
med["d_point"] = med.est - med.ref
med["reproduced"] = med.d_point.abs() <= TOL["point"] + 1e-9

RESULTS.mkdir(exist_ok=True)
COLS = key + ["data_value", "confidence_limit_low", "confidence_limit_high", "sample_size", "est", "lo", "hi", "se",
               "n_yes", "n_denom", "supp", "cdc_suppressed", "ok_point", "ok_ci", "ok_n", "reproduced", "supp_agree"]
cells[COLS].round(4).to_csv(RESULTS / "gate0_cells.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
med.to_csv(RESULTS / "gate0_median_cells.csv", index=False)


def summ(c):
    pub = c[c.ref_published]
    return {"cells_compared": int(len(pub)), "reproduced": int(pub.reproduced.sum()),
            "rate": round(float(pub.reproduced.mean()), 4), "point_ok_rate": round(float(pub.ok_point.mean()), 4),
            "ci_ok_rate": round(float(pub.ok_ci.mean()), 4), "sample_size_exact_rate": round(float(pub.ok_n.mean()), 4),
            "max_abs_point_diff_pp": round(float(pub.d_point.abs().max()), 4),
            "max_abs_ci_diff_pp": round(float(max(pub.d_lo.abs().max(), pub.d_hi.abs().max())), 4),
            "cdc_unpublished_cells": int((~c.ref_published).sum()),
            "suppression_agreement_rate_all_cells": round(float(c.supp_agree.mean()), 4),
            "missing_my_estimate": int(pub.est.isna().sum())}


prim = cells[cells.break_out_category == "Overall"]; bo = cells[cells.break_out_category != "Overall"]
per_ind = prim[prim.ref_published].groupby("questionid").reproduced.mean().round(4)
summary = {"G0_primary": summ(prim), "G0_breakout": summ(bo),
           "G0_median": {"cells_compared": int(len(med)), "reproduced": int(med.reproduced.sum()),
                         "rate": round(float(med.reproduced.mean()), 4),
                         "max_abs_point_diff_pp": round(float(med.d_point.abs().max()), 4)},
           "pass_criterion": PROTO["gate0"]["pass_criterion"],
           "flagged_indicators_primary_lt_95pct": per_ind[per_ind < 0.95].to_dict(),
           "per_indicator_primary_rate": per_ind.to_dict(),
           "runtime_s": round(time.time() - t0, 1)}
for k in ("G0_primary", "G0_breakout", "G0_median"):
    summary[k]["passed"] = summary[k]["rate"] >= PROTO["gate0"]["pass_criterion"][k]
(RESULTS / "gate0_summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps({k: summary[k] for k in ("G0_primary", "G0_breakout", "G0_median", "flagged_indicators_primary_lt_95pct")}, indent=1))
