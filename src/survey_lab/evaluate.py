"""Scoring, abstention metrics, cost/latency summaries and the paired non-inferiority test."""
from __future__ import annotations

import math

import numpy as np

TOL_PP = 0.1


def score(item: dict, rec: dict) -> dict:
    gold = item["gold"]
    spec = rec["spec"]
    abstained = not spec["answerable"]
    if not gold["answerable"]:
        spec_match = abstained
        numeric = None
        correct = abstained
    else:
        g_sub = gold.get("subgroup")
        spec_match = (not abstained and spec["indicator"] == gold["indicator"] and spec["response"] == gold["response"]
                      and spec["geography"] == gold["geography"] and (spec["subgroup"] or None) == (g_sub or None))
        est = rec.get("estimate")
        numeric = est is not None and abs(est - item["reference"]["data_value"]) <= TOL_PP + 1e-9
        correct = bool(numeric)
    return {"spec_match": bool(spec_match), "numeric_ok": numeric, "correct": bool(correct), "abstained": abstained,
            "should_abstain": not gold["answerable"]}


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe_paired(a: np.ndarray, b: np.ndarray, z: float = 1.959963984540054) -> dict:
    """Newcombe (1998) method 10: CI for p_a - p_b with paired binary outcomes (a, b are 0/1 arrays)."""
    a = np.asarray(a, bool); b = np.asarray(b, bool)
    n = len(a)
    e = int((a & b).sum()); f = int((a & ~b).sum()); g = int((~a & b).sum()); h = int((~a & ~b).sum())
    p1, p2 = (e + f) / n, (e + g) / n
    l1, u1 = wilson(e + f, n, z); l2, u2 = wilson(e + g, n, z)
    d = p1 - p2
    den = (e + f) * (g + h) * (e + g) * (f + h)
    if den == 0:
        phi = 0.0
    else:
        num = e * h - f * g
        if num > 0:   # Newcombe's correction applies only when ad > bc
            num = max(num - n / 2, 0.0)
        phi = num / math.sqrt(den)
    lo = d - math.sqrt(max((p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2, 0.0))
    hi = d + math.sqrt(max((u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2, 0.0))
    return {"n": n, "p_a": p1, "p_b": p2, "diff": d, "ci_low": lo, "ci_high": hi,
            "discordant_a_only": f, "discordant_b_only": g}


def summarize(items: list[dict], recs: list[dict]) -> dict:
    sc = [score(i, r) for i, r in zip(items, recs)]
    n = len(sc)
    ans = [s for s in sc if not s["should_abstain"]]
    tp = sum(s["abstained"] and s["should_abstain"] for s in sc)
    fp = sum(s["abstained"] and not s["should_abstain"] for s in sc)
    fn = sum((not s["abstained"]) and s["should_abstain"] for s in sc)
    costs = np.array([r["cost_usd"] for r in recs]); secs = np.array([r["seconds"] for r in recs])
    calls = [c for r in recs for c in r["calls"]]
    k = sum(s["correct"] for s in sc)
    return {
        "n": n, "n_answerable": len(ans), "n_should_abstain": n - len(ans),
        "outcome_correct": k / n, "outcome_correct_ci": wilson(k, n),
        "spec_exact_match": sum(s["spec_match"] for s in sc) / n,
        "numeric_agreement_answerable": (sum(bool(s["numeric_ok"]) for s in ans) / len(ans)) if ans else None,
        "abstention_precision": tp / (tp + fp) if tp + fp else None,
        "abstention_recall": tp / (tp + fn) if tp + fn else None,
        "false_abstentions": fp, "missed_abstentions": fn,
        "cost_total_usd": float(costs.sum()), "cost_per_question_usd": float(costs.mean()),
        "latency_median_s": float(np.median(secs)), "latency_p95_s": float(np.percentile(secs, 95)),
        "llm_calls": len(calls), "prompt_tokens": int(sum(c["prompt_tokens"] for c in calls)),
        "completion_tokens": int(sum(c["completion_tokens"] for c in calls)),
        "cached_tokens_reported": int(sum(c["cached_tokens"] or 0 for c in calls)),
        "calls_reporting_cached_field": int(sum(c["cached_tokens"] is not None for c in calls)),
        "api_errors": int(sum(bool(c["error"]) for c in calls)),
        "guard_rejections": int(sum(len(r["guard_errors"]) for r in recs)),
        "ungrounded_answers": int(sum(bool(r["ungrounded"]) for r in recs)),
        "paths": _paths(recs),
    }


def _paths(recs):
    out: dict[str, int] = {}
    for r in recs:
        k = ">".join(r["path"])
        out[k] = out.get(k, 0) + 1
    return out
