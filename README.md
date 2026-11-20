# survey-analysis-eval-lab

This is a public-health-survey AI evaluation prototype. Users ask plain-English questions about the **CDC BRFSS
2025** survey. The tool answers with **survey-weighted** crude prevalence and design-based 95% CIs, and shows the
exact computation it ran. It is judged against **values CDC itself published** (BRFSS Prevalence & Trends,
data.cdc.gov `dttw-5yxu`).

> **Update (addenda A4/A5).** The LLM provider was switched to the official OpenAI API, with pinned snapshots
> `gpt-4o-2024-11-20` and `gpt-4.1-2025-04-14`, and the provisional Azure results were moved to
> `results/azure_provisional/` (comparison only). The OpenAI run is **blocked**: the account has no credits
> (`insufficient_quota`). No OpenAI call succeeded and the spend is $0.00. The held-out LLM evaluation and the
> non-inferiority decision are still pending.
>
> **Status (2026-11-20): LLM evaluation incomplete. All LLM results below are provisional.** Live LLM calls were
> stopped partway through the held-out run because the Azure OpenAI endpoint used turned out not to be suitable
> for this project. The cached responses (`results/llm_cache.jsonl`, gitignored) came from that **provisional
> endpoint**. They must be **re-run before any use**. Live calls are now disabled by default
> (`SURVEYLAB_LLM_ENABLED` unset). The deterministic parts are complete and independent of any LLM: Gate 0, the
> survey estimator, the catalog, the guard, the template path and the harness.

## How it works

```
question ─► TEMPLATE matcher (regex, no LLM) ── confident? ──► spec
         └► else LLM (gpt-4o / gpt-4.1) ─► JSON spec only
spec ─► guard (catalog allow-list; unknown keys, variables, years, geographies, statistics rejected)
     ─► deterministic executor (weights _LLCPWT, strata _STSTR, PSU _PSU; Taylor linearization)
     ─► deterministic answer text ─► grounding check (every number in the text must come from the executor)
```

- **The LLM can only choose catalog values.** It picks an indicator id, a response category, a geography and at
  most one subgroup, or it abstains with a reason code. It never writes code or numbers.
- **Each answer shows its trace.** The trace lists the variable, the numerator and denominator codes, the
  denominator rule, the subgroup filter, the weight and design variables, and the variance method.
- **National questions** use CDC's convention: the US value is a median of jurisdiction estimates, not a pooled
  prevalence. The answer says so.
- **Catalog.**
  - `catalog/codebook.json` is parsed from the CDC codebook, with administrative variables dropped.
  - `catalog/indicators.json` is the hand-specified mapping of 55 CDC P&T questions to LLCP variables and codes,
    plus 5 break-out categories.

## Prespecified protocol

`docs/protocol.md` and `protocol.json` were committed (`570cead`) **before** Gate 0 and before any LLM call.
Later changes are dated addenda:

- **A1:** the Gate 0 convention fixes;
- **A2:** the dev-phase prompt and matcher changes, frozen at `cd68f2b`;
- **A3:** the stop of live LLM calls.

## Results

### Gate 0: deterministic code vs CDC published values (complete)

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
  3. records missing the break-out variable are **dropped before** domain estimation, SAS-style, which changes
     the per-stratum PSU counts and hence the variance;
  4. the medians include suppressed jurisdictions.
- **Still unexplained (not tuned away).** Two NHPI median cells, and 135 of about 215k suppression decisions at
  the RSE ≈ 0.3 boundary.

### Held-out test split (166 items: 119 answerable, 47 should-abstain)

The primary prespecified comparison has **not been run**. ROUTER, GPT41 and ROUTER_T41 on the full test split
were not completed before live calls were stopped. The rows below are what exists. Numbers come from
`results/azure_provisional/test_partial_summary.json`.

| Policy | Status | Outcome correct [95% CI] | Numeric agreement (answerable) | Abstain precision / recall | Cost total (per q) | Latency p50 / p95 |
|---|---|---|---|---|---|---|
| EXPERT (gold spec → executor) | final | 100.0% [97.7, 100] | 100.0% | 1.00 / 1.00 | $0 | 0.06 / 0.12 s |
| TEMPLATE (no LLM) | final | 62.0% [54.5, 69.1] | 49.6% (answers 62 items; 59 of those correct) | 0.42 / 0.94 | $0 | <0.01 s |
| GPT4O | **provisional endpoint** | 97.0% [93.1, 98.7] | 96.6% | 0.92 / 0.98 | $0.84 ($0.0050) | 1.69 / 2.71 s |
| GPT41 (first 60 test items only, all answerable) | **provisional endpoint, partial** | 100% (60/60) | 100% | n/a | $0.16 ($0.0026) | 1.29 / 10.75 s (rate-limited) |
| ROUTER, ROUTER_T41, GPT41 (full), GPT52 | **not run** | n/a | n/a | n/a | n/a | n/a |

- **Non-inferiority (primary: ROUTER vs EXPERT, margin −7.5 pp): not decided.** The ROUTER held-out run does
  not exist.
- **Descriptive only, not prespecified.** GPT4O − EXPERT = −3.0 pp, Newcombe 95% CI [−6.9, −0.2].
- **Prompt caching was measured, not assumed.** On the GPT4O test run, the API reported 506,880 of 520,134
  prompt tokens as cached.
- **Cost premise of ROUTER.** On dev, gpt-4.1 cost less per call than gpt-4o: its list price is lower and its
  cached-input discount is larger (25% vs 50% of the input price). So ROUTER's "cheaper model first" premise
  does not hold at these prices.

### Dev split (54 items, prompt iteration, provisional endpoint)

| Policy | prompt v1 | v2 | v3 (frozen) |
|---|---|---|---|
| gpt-4o | 92.6% | 88.9% | 98.1% |
| gpt-4.1 | 79.6%* | 100% | 100% |
| ROUTER | 96.3% | 94.4% | 100% |
| TEMPLATE | 64.8% | 64.8% | 64.8% |

\*The v1 gpt-4.1 figure is depressed by HTTP 429 errors that v1 scored as abstentions. This was fixed in A2.

### Stress set (39 items, written after the first held-out results; deterministic policies only)

TEMPLATE scored 53.8%. It answered 4 of 16 should-abstain items and got 3 answered items wrong. EXPERT scored
100%. LLM policies were not run on the stress set. Numbers come from `results/stress_nollm_summary.json`.

## Failure modes observed

- **Template: an unknown restriction word is silently dropped and the wrong population is answered.**
  - "ladies" and "Latino" were not recognized, so the matcher answered for all adults.
  - "among veterans" was read as the VETERAN3 indicator.
  - "caregivers" was not recognized.
  - The matcher can only defer on restriction words it knows, which is an open-world problem.
- **Template: denominator and compound traps.**
  - "of adults who drink alcohol, what share binge drink" answered with the all-adult binge-drinking rate.
  - "flu shot among ALL adults" answered with the 65+ indicator.
  - "obese or overweight" answered only obese.
  - "Virginia (not West Virginia)" answered West Virginia.
- **gpt-4o (provisional): mostly over-abstention.**
  - It said `topic_not_in_catalog` for prediabetes, for share aged 65+, and for pregnancy-only diabetes.
  - It said `multiple_subgroups` for a single education subgroup.
- **A debatable gold label.** In q101, "flu vaccination among women 65+", 65+ is the flu-shot indicator's own
  universe, so this is arguably a single subgroup. The gold label says abstain. gpt-4o and TEMPLATE answered it.
  The gold label was not edited.

## Limitations and what was NOT done

- **The LLM evaluation is incomplete and provisional.** The primary non-inferiority test, ROUTER/GPT41 on the
  full held-out split, the stress set for LLM policies, and gpt-5.2 (only 13 calls) were not done.
- **The same author wrote everything that is scored.** The questions, the gold specs, the template matcher and
  the prompts were all written by the same AI agent. Prompts and matcher were tuned on dev only, but the author
  had seen the test wording. The sample is small: 166 held-out items.
- **Crude prevalence only.** No age adjustment, means, counts, trends, multi-subgroup or sub-state estimates.
  Those requests abstain by design.
- **One survey year (2025).** California, Mississippi and Nevada contributed no 2025 data.
- **National values follow CDC's state-median convention.** No pooled national estimate is validated.
- **Cost is computed at list prices** (Azure Retail Prices API, retrieved 2026-11-20; `docs/pricing.json`).
  It is not taken from an invoice.
- **This is not a deployed or user-tested system.** There is no UI and no human-reviewer study.

## Running it

```
uv sync
# download the files listed in data/manifest.json into data/raw/ (gitignored), then:
make data gate0 questions test
make eval-offline        # replays cached LLM responses; fails on a cache miss, never calls an API
```

- **Live LLM calls (default provider `openai`)** need `OPENAI_API_KEY` and `SURVEYLAB_LLM_ENABLED=1`.
  `SURVEYLAB_SPEND_CAP_USD` (default 8) stops live calls at the cap. `SURVEYLAB_LLM_PROVIDER=azure` exists only
  to replay the superseded provisional cache.
- **No API keys** are used, and nothing is hard-coded. Deployment names are assumed to equal the model names.
- **Tests:** `uv run pytest` runs 48 tests, covering:
  - variance vs a hand-computed example and `samplics`;
  - denominator and missing-code rules;
  - guard rejections;
  - grounding;
  - cost accounting;
  - the Newcombe CI against the published example;
  - CDC regression cells.

## Provenance

- `data/manifest.json` lists source URLs and SHA-256 hashes for the raw data.
- The CDC reference snapshot is `gold/cdc_reference_2025.csv.gz`.
- `docs/ai-assisted-engineering.md` describes how the code was produced: it was implemented by an AI coding
  agent directed by Lu Zhang. That file also lists the defects caught by verification.
