# Prespecified evaluation protocol (v1.0, 2026-11-20)

This protocol was written and committed **before** Gate 0 was run and **before** any LLM call.
`protocol.json` is the machine-readable copy; the evaluation scripts read their thresholds from it.
Any later change goes into a dated addendum at the bottom of this file. Earlier text is never edited.

## 1. Question being answered

Can an LLM-backed natural-language tool answer public-health-survey prevalence questions as accurately as a
deterministic, expert-specified analysis, at an acceptable cost and latency? Accuracy is judged against
values **published by CDC**, not against the tool's own pipeline.

## 2. Data and reference

- **Survey microdata:** CDC BRFSS 2025 LLCP public-use file (`LLCP2025XPT.zip`, 356,158 records).
  Design variables: final weight `_LLCPWT`, strata `_STSTR`, PSU `_PSU` (nested within strata).
- **Expert reference values:** CDC "BRFSS Prevalence Data (2011 to present)", data.cdc.gov dataset
  `dttw-5yxu`, year 2025, crude prevalence. The snapshot was taken on 2026-11-20 (`rowsUpdatedAt` = 2026-09-15).
  Its SHA-256 is recorded in `protocol.json` and `data/manifest.json`. The evaluation reads only the frozen snapshot.
- The 2025 P&T file contains crude prevalence only, so no age-adjusted comparison is possible. The tool
  abstains on age-adjusted requests.

## 3. Gate 0: deterministic reproduction of CDC values (runs before any LLM call)

The hand-specified mapping is `catalog/indicators.json`. It maps each P&T question/response to an LLCP variable
and its codes. Every code that is not in `valid` is excluded from the denominator. This covers 7/9/77/99
don't know/refused, blanks and out-of-universe codes.

- **Estimator.** Weighted proportion with Taylor-linearization variance (with-replacement PSUs). Domains use
  full-design domain estimation; records are never subset before estimation. Strata with a single PSU
  contribute zero. The CI is Wald, p ± 1.96·SE.
- **Cell sets.**
  - `G0_primary`: 55 questions × all responses × 50 jurisdictions, Overall.
  - `G0_breakout`: the same cells × 29 break-out values.
  - `G0_median`: the CDC "US" and "UW" median rows, point only.
  - Cells where CDC publishes no value are excluded.
- **Tolerance.** |Δ| ≤ 0.1 percentage points for the point estimate and for each CI limit.
- **Sub-checks.** The numerator `sample_size` must match exactly. The suppression decision must agree
  (CDC rule: denominator n < 50 or RSE > 0.3).
- **Pass.** At least 95% of cells reproduced in each cell set. Any indicator with fewer than 95% of its primary
  cells reproduced is flagged and investigated in `docs/gate0-investigation.md`.
- **Disclosed prior look.** One cell (WA, fair/poor health, Overall) was computed while validating the variance
  code, before this protocol was written. It matched to 0.01 pp.

## 4. Tool scope and abstention rules

- **Answerable questions.** Crude prevalence for 2025, for one catalog indicator/response, in one of:
  - one of the 50 jurisdictions;
  - `US_MEDIAN` (CDC "US", the median across states, DC and territories);
  - `STATES_DC_MEDIAN` (CDC "UW").

  At most one catalog subgroup filter is allowed.
- **National questions.** "In the US" / "nationally" is answered with the CDC median convention
  (`US_MEDIAN`). The answer text says that it is a median of jurisdiction estimates, not a pooled national
  prevalence.
- **Must abstain.** The tool abstains on:
  - another year;
  - California, Mississippi or Nevada (no 2025 data), or a county or city;
  - age-adjusted estimates, means, counts, trends, regressions;
  - topics outside the catalog;
  - causal or "why" questions;
  - more than one subgroup filter;
  - non-survey questions.

## 5. Questions, split, and freezing

- **Authoring.** Questions are hand-written in `gold/questions.jsonl` with varied phrasing. Each has a
  hand-assigned gold spec or a gold "abstain" with a reason category.
- **Split.** Deterministic: `dev` if `int(sha256(id)[:8],16) % 10 < 3`, else `test` (about 30/70).
- **Dev use.** Prompts and the template matcher are developed on `dev` only, with at most 3 prompt revisions.
- **Freezing.** Before the held-out run, the prompt, matcher and router are frozen and the commit hash is
  recorded in `results/`. The held-out split is then run once per policy.
- **Excluded test items.** Test items whose reference cell failed Gate 0 are excluded from the primary analysis
  and reported separately.
- **Stress set.** Written after the first held-out results: paraphrases, ambiguous denominators, wrong
  year/geography, subgroup traps, national vs median. It is reported separately and never enters the primary
  comparison.

## 6. Metrics

| Metric | Definition |
|---|---|
| spec exact match | indicator, response, geography and subgroup all equal the gold spec (should-abstain items: tool abstained) |
| numeric agreement | an estimate was executed and \|estimate − CDC\| ≤ 0.1 pp |
| **outcome correct (primary)** | answerable: numeric agreement; should-abstain: tool abstained |
| abstention precision / recall | positive class = abstain |
| cost | USD per question from logged tokens (incl. cached tokens when the API reports them) and `docs/pricing.json` |
| latency | wall-clock seconds per question (median, p95); cache replays report the originally logged latency |

## 7. Policies compared

| Policy | Description |
|---|---|
| EXPERT | The gold spec executed by the deterministic pipeline. This is the expert-specified process, with no NL interpretation. |
| TEMPLATE | Deterministic keyword/regex matcher only. It abstains when not confident. |
| GPT4O | Always gpt-4o (2024-11-20). |
| GPT41 | Always gpt-4.1 (2025-04-14). |
| ROUTER | Uses TEMPLATE if it returns a confident spec. Otherwise it calls gpt-4o, and escalates to gpt-4.1 if the gpt-4o spec fails the guard or gpt-4o reports `confidence: "low"`. |
| GPT52 | Optional and exploratory. gpt-5.2 runs on a subset only, because its capacity is 10K TPM. It is not part of the primary comparison. |

All LLM calls use temperature 0, JSON output and max 400 output tokens. Every call is cached in
`results/llm_cache.jsonl`. The LLM only emits a JSON analysis spec. It never writes code, and it never writes
the numbers in the answer.

## 8. Non-inferiority (primary decision)

- **Comparison and endpoint.** ROUTER vs EXPERT on the held-out test split, using paired `outcome correct`.
- **Margin.** δ = 7.5 percentage points.
- **Method.** Paired difference ROUTER − EXPERT, with a Newcombe (1998) method-10 hybrid-score 95% CI.
- **Decision.** Non-inferior if the lower 95% limit is > −7.5 pp. Otherwise the result is reported as
  "non-inferiority not shown".
- **Why this margin.**
  - EXPERT is near-perfect by construction. Its only possible errors are Gate 0 mismatches.
  - With roughly 150 held-out items, a 5 pp margin would fail after about 2 errors. That would make the test
    mostly a test of sample size.
  - 7.5 pp tolerates roughly 3–4 errors in 150. That is still a strict bar for an assistant whose every answer
    shows the executed spec for human review.
  - This is a prototype decision rule, not a regulatory threshold.
- **Secondary.** GPT41 vs EXPERT with the same method. ROUTER vs GPT41 cost and latency, descriptive.

## 9. Budget

The total LLM spend cap is USD 10. Prices come from the Azure Retail Prices API (retrieved 2026-11-20) and
are recorded in `docs/pricing.json`.

---

## Addenda

### A1 (2026-11-20): Gate 0 convention fixes, made after Gate 0 run 1 and before any LLM call

Gate 0 run 1 used the prespecified conventions, and its output is archived in
`results/gate0_v1_prespecified/`. G0_primary passed at 97.7% and G0_median at 96.9%. **G0_breakout failed
(90.2% < 95%).** The investigation is in `docs/gate0-investigation.md`. Four conventions were changed to match
how CDC computes P&T:

1. **Race variable.** Race now uses `_RACEPRV` instead of `_RACE`. This is a catalog fix.
2. **CI truncation.** Wald CIs are truncated to [0, 100].
3. **Missing break-out values.** Records missing the break-out variable are dropped before domain estimation,
   following CDC's SAS-style listwise exclusion.
4. **Medians and suppression.** US/UW medians use all jurisdiction estimates, including suppressed ones. A
   numerator of 0 counts as "not published" in the suppression sub-check.

Run 2 reproduced 100.0% of G0_primary, 100.0% of G0_breakout and 99.4% of G0_median. Both runs are reported.
The tolerance, the cell sets and the pass criteria are unchanged. The executor used by every policy applies the
corrected conventions.
