# survey-analysis-eval-lab

This is a public-health-survey AI evaluation prototype. Users ask plain-English questions about the **CDC BRFSS
2025** survey. The tool answers with **survey-weighted** crude prevalence and design-based 95% CIs, and shows the
exact computation it ran. Answers are scored against **values CDC itself published** (BRFSS Prevalence & Trends,
data.cdc.gov `dttw-5yxu`).

**Headline results.**

- **Gate 0 passed.** Deterministic, hand-specified code reproduces 100% of CDC's 7,897 overall and 157,897
  break-out cells within 0.1 pp. It failed on the first, prespecified attempt.
- **Primary non-inferiority test failed.** The prespecified router (template → gpt-4o → gpt-4.1) was **not shown
  non-inferior** to the expert-specified pipeline: −4.8 pp, 95% CI [−9.2, −1.6], margin −7.5 pp.
- **Secondary comparison passed.** gpt-4.1 alone met the margin: −2.4 pp [−6.0, +0.3].

## How it works

```
question ─► TEMPLATE matcher (regex, no LLM) ── confident? ──► spec
         └► else LLM (gpt-4o / gpt-4.1) ─► JSON spec only
spec ─► guard (catalog allow-list; unknown keys, variables, years, geographies, statistics rejected)
     ─► deterministic executor (weights _LLCPWT, strata _STSTR, PSU _PSU; Taylor linearization)
     ─► deterministic answer text ─► grounding check (every number in the text must come from the executor)
```

- **The LLM can only choose catalog values.** It picks an indicator id, a response category, a geography and at
  most one subgroup, or it abstains with a reason code. It never writes code or numbers. Every scored answer passed the grounding
  check, including the 791 that involved an LLM call (`ungrounded_answers` = 0 in every summary).
- **Each answer shows its trace.** The trace lists the variable, the numerator and denominator codes, the
  denominator rule, the subgroup filter, the weight and design variables, and the variance method.
- **National questions** use CDC's convention: the US value is a median of jurisdiction estimates, not a pooled
  prevalence. The answer says so.
- **Catalog.**
  - `catalog/codebook.json` is parsed from the CDC codebook, with administrative variables dropped.
  - `catalog/indicators.json` is the hand-specified mapping of 55 CDC P&T questions to LLCP variables and codes,
    plus 5 break-out categories.

## Prespecified protocol and addenda

`docs/protocol.md` and `protocol.json` were committed (`570cead`) **before** Gate 0 and before any LLM call.

| Addendum | What it records |
|---|---|
| A1 | Gate 0 convention fixes |
| A2 | Dev-phase prompt and matcher changes, frozen at `cd68f2b` |
| A3 | Live calls stopped mid held-out run; Azure results marked provisional |
| A4 | Provider switched to the OpenAI API with the same model snapshots, written before any OpenAI call |
| A5 | First OpenAI attempt blocked by zero credits |

The held-out and stress runs below ran once, at commit `c6e13c6` (`code_dirty: false`), on the OpenAI API:

| Model | Snapshot |
|---|---|
| gpt-4o | `gpt-4o-2024-11-20` |
| gpt-4.1 | `gpt-4.1-2025-04-14` |
| gpt-4.1-mini (exploratory arm only) | `gpt-4.1-mini-2025-04-14` |

Every logged call records the snapshot the API returned. Earlier provisional Azure results are superseded and
kept only in `results/azure_provisional/`.

## Results

All tables are generated into `results/tables.md` by `scripts/make_tables.py`.

### Gate 0: deterministic code vs CDC published values

Tolerance is |Δ| ≤ 0.1 pp on the point estimate and on both CI limits. Numbers come from
`results/gate0_summary.json` and `results/gate0_v1_prespecified/gate0_summary.json`.

| Cell set | Run 1 (prespecified conventions) | Run 2 (after addendum A1) |
|---|---|---|
| Overall: 55 questions × all responses × 50 jurisdictions | 97.7% (7,715 / 7,897) | **100.0% (7,897 / 7,897)** |
| Break-outs (sex, age, race/ethnicity, education, income) | 90.2% (142,384 / 157,897), **failed the 95% bar** | **100.0% (157,897 / 157,897)** |
| CDC US / UW median rows (point only) | 96.9% (310 / 320) | **99.4% (318 / 320)** |

- **Run 2 precision.** The maximum point difference was 0.005 pp, which is CDC's 2-decimal rounding. The maximum
  CI difference was 0.019 pp. CDC's numerator `sample_size` matched exactly in 100% of compared cells.
- **What run 1 exposed.** Run 1 surfaced four CDC conventions (`docs/gate0-investigation.md`):
  1. race comes from `_RACEPRV`, not `_RACE`;
  2. CIs are truncated to [0, 100];
  3. records missing the break-out variable are **dropped before** domain estimation, which changes the
     per-stratum PSU counts and hence the variance;
  4. the medians include suppressed jurisdictions.
- **Still unexplained (not tuned away).** Two NHPI median cells, and 135 of about 215k suppression decisions at
  the RSE ≈ 0.3 boundary.

### Held-out test split: 166 items (119 answerable, 47 should-abstain), run once

Numbers come from `results/test_summary.json` and `results/test_exploratory_summary.json`.

| Policy | Outcome correct [95% CI] | Numeric agreement (answerable) | Abstain P / R | Cost total (per q) | Latency p50 / p95 | LLM calls | Cached / prompt tokens |
|---|---|---|---|---|---|---|---|
| EXPERT (gold spec → executor) | 100.0% [97.7, 100] | 100.0% | 1.00 / 1.00 | $0 | 0.06 / 0.12 s | 0 | n/a |
| TEMPLATE (no LLM) | 62.0% [54.5, 69.1] | 49.6% | 0.42 / 0.94 | $0 | <0.01 s | 0 | n/a |
| GPT4O | 95.8% [91.6, 97.9] | 95.0% | 0.88 / 0.98 | $0.895 ($0.0054) | 0.94 / 1.19 s | 166 | 459,264 / 520,134 |
| GPT41 | **97.6% [94.0, 99.1]** | 98.3% | 0.96 / 0.96 | $0.515 ($0.0031) | 0.85 / 1.10 s | 166 | 438,656 / 520,134 |
| **ROUTER** (primary; template → 4o → 4.1) | 95.2% [90.8, 97.5] | 95.8% | 0.90 / 0.94 | $0.563 ($0.0034) | 0.85 / 1.10 s | 104 | 285,568 / 325,921 |
| ROUTER_T41 (exploratory, A2; template → 4.1) | 97.0% [93.1, 98.7] | 99.2% | 0.98 / 0.91 | $0.325 ($0.0020) | 0.79 / 1.06 s | 104 | 273,792 / 325,921 |
| ROUTER_MINI (**post-hoc exploratory**, A4; template → 4.1-mini → 4.1) | 94.0% [89.3, 96.7] | 97.5% | 0.95 / 0.85 | **$0.077 ($0.00046)** | 1.01 / 1.75 s | 108 | 300,288 / 338,454 |

- **TEMPLATE alone** answers 62 items, 59 correctly, and defers the rest. In TEMPLATE-only mode a deferral
  counts as an abstention, which is why its abstention precision is low.
- **ROUTER never escalated to gpt-4.1.** gpt-4o never reported `confidence: "low"` and never failed the guard.
  ROUTER_MINI escalated 4 of 104 items.
- **Prompt caching was measured from the API usage fields, not assumed.** 84–89% of prompt tokens on the held-out
  split and 83–94% on the stress set were reported as cached.
- **Latency** is per-call API latency logged at call time, plus local execution. Router arms reuse the logged
  latency of identical cached calls.

#### Prespecified non-inferiority decision (protocol §8; `results/noninferiority.json`)

| Comparison (paired, Newcombe method 10) | Difference vs EXPERT | 95% CI | Margin −7.5 pp |
|---|---|---|---|
| **ROUTER vs EXPERT (primary)** | **−4.8 pp** | **[−9.2, −1.6]** | **not shown non-inferior** |
| GPT41 vs EXPERT (prespecified secondary) | −2.4 pp | [−6.0, +0.3] | non-inferior |
| GPT4O vs EXPERT (exploratory) | −4.2 pp | [−8.5, −1.1] | not shown |
| ROUTER_T41 vs EXPERT (exploratory) | −3.0 pp | [−6.9, −0.2] | meets margin (exploratory, not a decision) |
| ROUTER_MINI vs EXPERT (post-hoc exploratory) | −6.0 pp | [−10.7, −2.5] | not shown |

- **The decision.** The prespecified primary result is a **fail**. The router made 8 errors, and EXPERT was
  correct on every one of them.
- **Post-hoc sensitivity, not part of the decision.** Item q101 ("flu vaccination among women 65+") was relabeled
  as answerable, because 65+ is the flu-shot indicator's own universe and so only one subgroup is involved. With
  that relabel:
  - ROUTER moves to −4.2 pp [−8.5, −1.1], still not shown non-inferior;
  - GPT41 moves to −1.8 pp [−5.2, +0.8].

### Stress set: 39 items written after the first held-out results, reported separately

Numbers come from `results/stress_summary.json` and `results/stress_exploratory_summary.json`.

| Policy | Outcome correct [95% CI] | Abstain P / R | Cost |
|---|---|---|---|
| EXPERT | 100% [91.0, 100] | 1.00 / 1.00 | $0 |
| TEMPLATE | 53.8% [38.6, 68.4] | 0.52 / 0.75 | $0 |
| GPT4O | 89.7% [76.4, 95.9] | 0.83 / 0.94 | $0.202 |
| GPT41 | 92.3% [79.7, 97.3] | 0.93 / 0.88 | $0.117 |
| ROUTER | 71.8% [56.2, 83.5] | 0.79 / 0.69 | $0.119 |
| ROUTER_T41 | 74.4% [58.9, 85.4] | 0.91 / 0.63 | $0.066 |
| ROUTER_MINI (post-hoc) | 76.9% | 1.00 / 0.63 | $0.020 |

On adversarial wording, the template front end is the weakest link. When it is confidently wrong, the router
inherits the error.

### What the results say

1. **The deterministic analysis is the strong part.** It reproduces CDC exactly, and every LLM answer is
   grounded in it.
2. **The best policy is the simplest LLM policy.** gpt-4.1 alone was the most accurate, and it met the
   non-inferiority margin as the prespecified secondary.
3. **The prespecified router lost on both accuracy and cost.**
   - **Accuracy.** Its template tier silently misread questions it was confident about: "among veterans" became
     the veteran indicator, and "caregivers" was ignored. Its gpt-4o tier over-abstained.
   - **Cost.** gpt-4.1 is cheaper per call than gpt-4o at list price with caching. So routing through gpt-4o cost
     more ($0.563) than always using gpt-4.1 ($0.515).
4. **Cheap tiers trade accuracy for cost.**
   - ROUTER_T41: template → gpt-4.1 cost 37% less than GPT41 and lost 0.6 pp.
   - ROUTER_MINI (post-hoc): cost 85% less than GPT41 and lost 3.6 pp, mostly from missed abstentions.

## Failure modes observed

- **Template: unknown restriction words are dropped silently.**
  - "Among veterans in Virginia, what percent smoke?" answered VETERAN3 = Yes.
  - "Among caregivers in Iowa…" answered for all adults.
  - In the stress set, "ladies" and "Latino" were not recognized.
  - Denominator shifts ("of adults who drink alcohol…"), compounds ("obese or overweight") and negation
    ("Virginia (not West Virginia)") were all answered wrongly.
  - A regex matcher can only defer on words it knows.
- **gpt-4o: over-abstention.** It answered `topic_not_in_catalog` for prediabetes, share aged 65+, pregnancy-only
  diabetes and self-employed. It answered `multiple_subgroups` for single income and education subgroups.
- **gpt-4.1: a few distinct failure types.**
  - It abstained `geography_unavailable` on "18–24 year olds in New York".
  - It treated "75+ flu shot" as two subgroups.
  - It answered "HIV prevalence in DC" with *HIV testing*, a semantic substitution that the guard cannot catch.
  - In the stress set it answered an explicit "pooled national, not median" request with the state median. The
    answer text does label it a median.
- **gpt-4.1-mini (post-hoc arm): misses multi-subgroup traps.** It answered "college-educated women", "Black
  men" and "women aged 18–24" with one subgroup dropped.
- **A debatable gold label.** q101 is discussed above. The gold label was not edited.

## Spend

Total spend on the OpenAI key was **$1.80** at list price, over 538 unique API calls (`results/spend.json`):

| Model | Calls | Spend |
|---|---|---|
| gpt-4o | 205 | $1.10 |
| gpt-4.1 | 205 | $0.63 |
| gpt-4.1-mini | 128 | $0.07 |

- **Cap.** The USD 8 cap was enforced in the client.
- **Prices.** OpenAI Standard-tier list prices, retrieved 2026-11-20, are in `docs/pricing.json`.
- **Not counted.** The superseded provisional Azure calls (637 calls, about $2.54 at Azure list price) were a
  separate, superseded run and are not part of this total.

## Limitations and what was NOT done

- **The same author wrote everything that is scored.** The questions, the gold specs, the template matcher and the
  prompts were all written by the same AI agent. Prompts and matcher were tuned on dev only, but the author had
  seen the test wording. The sample is small: 166 held-out items and 39 stress items.
- **EXPERT is near-perfect by construction.** It executes the gold spec. The comparison tests NL interpretation
  and abstention, not arithmetic; Gate 0 tests the arithmetic.
- **Dev was not re-run on the OpenAI provider.** The prompt was tuned on the superseded Azure deployments of the
  same model versions.
- **Crude prevalence only.** No age adjustment, means, counts, trends, multi-subgroup or sub-state estimates.
- **One survey year (2025).** California, Mississippi and Nevada contributed no 2025 data. National values follow
  CDC's state-median convention, and no pooled national estimate is validated.
- **Costs are list-price estimates** from logged tokens, not invoice amounts.
- **gpt-5.2 was dropped** (A4). This is not a deployed or user-tested system: there is no UI and no
  human-reviewer study.

## Running it

```
uv sync
# download the files listed in data/manifest.json into data/raw/ (gitignored), then:
make data gate0 questions test
make eval-offline        # replays cached LLM responses; fails on a cache miss, never calls an API
```

- **Live calls** need `OPENAI_API_KEY` and `SURVEYLAB_LLM_ENABLED=1`.
- **Spend cap.** `SURVEYLAB_SPEND_CAP_USD` (default 8) stops live calls at the cap.
- **Azure.** `SURVEYLAB_LLM_PROVIDER=azure` exists only to replay the superseded Azure cache.
- **Tests:** `uv run pytest` runs 50 tests, covering:
  - variance vs a hand-computed example and `samplics`;
  - denominator and missing-code rules;
  - guard rejections;
  - grounding;
  - cost, snapshot pinning and the spend cap;
  - the Newcombe CI against the published example;
  - CDC regression cells.

## Provenance

- `data/manifest.json` lists source URLs and SHA-256 hashes for the raw data.
- The CDC reference snapshot is `gold/cdc_reference_2025.csv.gz`.
- `docs/ai-assisted-engineering.md` describes how the code was produced: it was implemented by an AI coding agent
  directed by Lu Zhang. That file also lists the defects caught by verification.
