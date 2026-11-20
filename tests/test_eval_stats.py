import numpy as np
import pytest

from survey_lab.evaluate import newcombe_paired, wilson


def _pairs(e, f, g, h):
    a = [1] * e + [1] * f + [0] * g + [0] * h
    b = [1] * e + [0] * f + [1] * g + [0] * h
    return np.array(a), np.array(b)


def test_newcombe_method10_published_example():
    # Newcombe (1998) Stat Med 17:2635, example (a): e=36 f=12 g=2 h=0 -> 0.0569 to 0.3404
    r = newcombe_paired(*_pairs(36, 12, 2, 0))
    assert r["diff"] == pytest.approx(0.2)
    assert r["ci_low"] == pytest.approx(0.0569, abs=5e-4)
    assert r["ci_high"] == pytest.approx(0.3404, abs=5e-4)


def test_wilson_bounds():
    lo, hi = wilson(10, 10)
    assert hi == pytest.approx(1.0) and 0.69 < lo < 0.73
