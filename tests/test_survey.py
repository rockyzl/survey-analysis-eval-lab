"""Weighting / variance against a hand-computed example and against samplics."""
import math

import numpy as np
import pytest

from survey_lab import survey


def by_hand(y, w, h, psu, dom):
    """Literal textbook formula, loops only (independent of the vectorised implementation)."""
    W = sum(wi for wi, d in zip(w, dom) if d)
    p = sum(wi * yi for wi, yi, d in zip(w, y, dom) if d) / W
    z = {}
    for yi, wi, hi, ci, d in zip(y, w, h, psu, dom):
        z.setdefault(hi, {}).setdefault(ci, 0.0)
        if d:
            z[hi][ci] += wi * (yi - p) / W
    v = 0.0
    for hi, psus in z.items():
        nh = len(psus)
        if nh < 2:
            continue
        zbar = sum(psus.values()) / nh
        v += nh / (nh - 1) * sum((zz - zbar) ** 2 for zz in psus.values())
    return p, math.sqrt(v)


# 3 strata: stratum 1 has PSUs a(2 obs), b(1 obs); stratum 2 has three 1-obs PSUs; stratum 3 is a single PSU
Y = [1, 0, 1, 0, 1, 1, 0]
W = [10, 20, 30, 40, 50, 60, 70]
H = [1, 1, 1, 2, 2, 2, 3]
C = [1, 1, 2, 3, 4, 5, 6]


def test_hand_example_numbers():
    # p = (10+30+50+60)/280 = 150/280
    est = survey.domain_proportions(np.array(Y), np.ones(7, bool), np.zeros(7, int), np.array(W, float),
                                    np.array(H), np.array(C), clip=False)
    p, se = by_hand(Y, W, H, C, [True] * 7)
    assert est.p.iloc[0] == pytest.approx(150 / 280)
    assert p == pytest.approx(150 / 280)
    assert est.se.iloc[0] == pytest.approx(se, rel=1e-12)
    # explicit value: stratum 1 z-totals and stratum 2 z-totals computed by hand
    pp = 150 / 280
    z1 = [(10 * (1 - pp) + 20 * (0 - pp)) / 280, 30 * (1 - pp) / 280]
    z2 = [40 * (0 - pp) / 280, 50 * (1 - pp) / 280, 60 * (1 - pp) / 280]
    v = 2 * sum((z - np.mean(z1)) ** 2 for z in z1) + 1.5 * sum((z - np.mean(z2)) ** 2 for z in z2)
    assert est.se.iloc[0] == pytest.approx(math.sqrt(v), rel=1e-12)


def test_single_psu_stratum_contributes_zero():
    est_all = survey.domain_proportions(np.array(Y), np.ones(7, bool), np.zeros(7, int), np.array(W, float),
                                        np.array(H), np.array(C))
    # change the outcome in the single-PSU stratum 3: point moves but stratum 3 still adds no variance term
    _, se_hand = by_hand(Y, W, H, C, [True] * 7)
    assert est_all.se.iloc[0] == pytest.approx(se_hand)


def test_domain_estimation_keeps_full_design():
    dom = np.array([0, 0, -1, 0, -1, 0, 0])
    est = survey.domain_proportions(np.array(Y), np.ones(7, bool), dom, np.array(W, float), np.array(H), np.array(C))
    p, se = by_hand(Y, W, H, C, [d == 0 for d in dom])
    assert est.p.iloc[0] == pytest.approx(p)
    assert est.se.iloc[0] == pytest.approx(se)


def test_invalid_records_excluded_from_denominator():
    valid = np.array([True, True, True, False, True, True, True])
    est = survey.domain_proportions(np.array(Y), valid, np.zeros(7, int), np.array(W, float), np.array(H), np.array(C))
    assert est.p.iloc[0] == pytest.approx(150 / 240)
    assert est.n_denom.iloc[0] == 6 and est.n_yes.iloc[0] == 4


def test_ci_is_clipped():
    y = np.array([1, 1, 1, 1, 0]); w = np.ones(5); h = np.array([1, 1, 1, 1, 1]); c = np.arange(5)
    est = survey.domain_proportions(y, np.ones(5, bool), np.zeros(5, int), w, h, c)
    assert est.ci_high.iloc[0] <= 1.0
    raw = survey.domain_proportions(y, np.ones(5, bool), np.zeros(5, int), w, h, c, clip=False)
    assert raw.ci_high.iloc[0] > 1.0


def test_suppression_rule():
    assert survey.suppressed(0.2, 0.01, 49)
    assert not survey.suppressed(0.2, 0.01, 50)
    assert survey.suppressed(0.02, 0.0061, 500)       # RSE 0.305
    assert survey.suppressed(0.0, 0.0, 500, n_yes=0)


def test_matches_samplics_taylor():
    samplics = pytest.importorskip("samplics")
    from samplics.estimation import TaylorEstimator
    rng = np.random.default_rng(1)
    n = 600
    h = rng.integers(0, 12, n)
    psu = h * 100 + rng.integers(0, 6, n)
    w = rng.uniform(1, 10, n)
    y = (rng.uniform(size=n) < 0.3 + 0.02 * h).astype(float)
    ours = survey.domain_proportions(y, np.ones(n, bool), np.zeros(n, int), w, h, psu)
    from samplics.utils.types import PopParam
    est = TaylorEstimator(PopParam.mean)
    est.estimate(y=y, samp_weight=w, stratum=h, psu=psu, remove_nan=True)
    assert ours.p.iloc[0] == pytest.approx(float(est.point_est), rel=1e-10)
    assert ours.se.iloc[0] == pytest.approx(float(est.stderror), rel=1e-8)
