"""Design-based estimation of proportions for stratified cluster samples (Taylor linearization).

Estimator: ratio mean p_d = sum_i w_i y_i 1[i in d] / sum_i w_i 1[i in d] for domain d.
Linearized values: z_i = w_i 1[i in d] (y_i - p_d) / W_d.
Variance (with-replacement PSUs, as in SUDAAN/SAS SURVEYMEANS default):
    V(p_d) = sum_h n_h/(n_h - 1) * sum_j (z_hj - zbar_h)^2, z_hj = PSU totals of z, zbar_h = mean over the
    n_h PSUs of stratum h in the FULL sample (domain estimation keeps out-of-domain PSUs as zeros).
Single-PSU strata (n_h = 1) contribute zero variance (SAS default; documented in docs/methods.md).
CI: Wald, p +/- 1.96 SE (matches CDC P&T published limits; see Gate 0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z95 = 1.959963984540054


def domain_proportions(y: np.ndarray, valid: np.ndarray, domain: np.ndarray, w: np.ndarray,
                       stratum: np.ndarray, psu: np.ndarray, lonely: str = "zero") -> pd.DataFrame:
    """Estimate P(y=1) in every domain value (domain < 0 = not in any domain).

    y: 0/1 outcome (ignored where valid is False). valid: in the denominator (non-missing response).
    Returns one row per domain with p, se, CI (proportions, not percent), n numerator, n denominator.
    """
    y = np.asarray(y, dtype=float); valid = np.asarray(valid, dtype=bool)
    domain = np.asarray(domain); w = np.asarray(w, dtype=float)
    stratum = np.asarray(stratum); psu = np.asarray(psu)
    if lonely not in ("zero", "center"):
        raise ValueError(lonely)
    # PSU count per stratum from the full sample
    full = pd.DataFrame({"h": stratum, "psu": psu})
    n_h = full.drop_duplicates().groupby("h").size()

    m = valid & (domain >= 0)
    d = pd.DataFrame({"g": domain[m], "h": stratum[m], "psu": psu[m], "w": w[m], "y": y[m]})
    d["wy"] = d.w * d.y
    agg = d.groupby("g").agg(W=("w", "sum"), WY=("wy", "sum"), n=("w", "size"), n_yes=("y", "sum"))
    agg["p"] = agg.WY / agg.W
    d = d.join(agg[["W", "p"]], on="g")
    d["z"] = d.w * (d.y - d.p) / d.W
    zt = d.groupby(["g", "h", "psu"]).z.sum().reset_index()
    zt["z2"] = zt.z ** 2
    sh = zt.groupby(["g", "h"]).agg(S1=("z", "sum"), S2=("z2", "sum")).reset_index()
    sh["n_h"] = sh.h.map(n_h).astype(float)
    multi = sh.n_h > 1
    sh["v"] = 0.0
    sh.loc[multi, "v"] = (sh.n_h / (sh.n_h - 1) * (sh.S2 - sh.S1 ** 2 / sh.n_h))[multi]
    if lonely == "center":
        # centre single-PSU strata at the domain's grand mean PSU value (R survey 'adjust'-style)
        tot_psu = n_h.sum()
        gm = zt.groupby("g").z.sum() / tot_psu
        single = ~multi
        sh.loc[single, "v"] = ((sh.S1 - sh.g.map(gm)) ** 2)[single]
    var = sh.groupby("g").v.sum()
    agg["se"] = np.sqrt(var.reindex(agg.index).fillna(0.0).clip(lower=0))
    agg["ci_low"] = agg.p - Z95 * agg.se
    agg["ci_high"] = agg.p + Z95 * agg.se
    agg["n_yes"] = agg.n_yes.astype(int)
    return agg[["p", "se", "ci_low", "ci_high", "n_yes", "n"]].rename(columns={"n": "n_denom"})


def suppressed(p: float, se: float, n_denom: int) -> bool:
    """CDC P&T rule: not reported if unweighted denominator < 50 or RSE > 0.3."""
    if n_denom < 50:
        return True
    return p > 0 and (se / p) > 0.3
