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

### A2 (2026-11-20): dev-phase changes, frozen before the held-out run

These are the changes made while iterating on the dev split (54 items). The held-out split had not been run
by any LLM policy at this point.

- **Prompt revisions (2 of the 3 allowed).** The prompt went from v1 to v3.
  - Dev outcome-correct went from v1 → v2 → v3 as follows:

    | Policy | v1 | v2 | v3 |
    |---|---|---|---|
    | gpt-4o | 0.926 | 0.889 | 0.981 |
    | gpt-4.1 | 0.796 | 1.000 | 1.000 |
    | ROUTER | 0.963 | 0.944 | 1.000 |

  - The v1 gpt-4.1 figure is depressed by HTTP 429 rate-limit errors, which v1 counted as abstentions (see
    below).
  - **v2** added rule 8 ("how many … percent" is a prevalence question) and rule 9 (demographic indicators).
  - v2's rule 9 made gpt-4o label single-subgroup questions as `multiple_subgroups`. **v3** reworded rule 9 and
    added rule 10 (the geography is never a subgroup).
  - All three prompt versions stay reproducible (`prompts.system_prompt(version)`).
- **Rate limits.** HTTP 429 responses are now retried with backoff and are never cached. gpt-4.1 / ROUTER run
  with 2 parallel workers.
- **Template matcher.** The matcher was tightened on dev so it defers whenever there is restriction wording it
  cannot fully parse, such as income ranges or "some college". On dev it answers 20/54 items, all correctly.
- **Exploratory policy added (not part of the primary comparison).** `ROUTER_T41` = TEMPLATE, falling back to
  gpt-4.1.
  - **Reason.** On dev, the measured prompt caching made gpt-4.1 cheaper per call than gpt-4o.
    - gpt-4o: 165,120 of 169,223 prompt tokens were reported as cached, billed at 50% of the input price.
    - gpt-4.1: 149,760 of 169,223 cached, billed at 25% of the input price, and gpt-4.1's list price is lower.
    - So the prespecified "cheap model first" premise of ROUTER does not hold.
  - ROUTER stays exactly as prespecified and remains the primary comparison.
- **Unchanged.** The primary endpoint, the non-inferiority margin (7.5 pp), the method, the split rule and the
  question set.
- **Disclosure.** The same agent wrote the questions, the gold specs, the template matcher and the prompts. The
  matcher and prompts were tuned only on dev results, but the author had seen the test question wording while
  writing the question file.
- The frozen commit hash is recorded in `results/test_summary.json` (`commit`, `code_dirty`).

### A3 (2026-11-20): live LLM calls stopped mid-way through the held-out run

During the single held-out run, live LLM calls were stopped. The Azure OpenAI endpoint being used turned out
not to be suitable for this project, and no further calls may be made until a suitable account is chosen.

- **Completed on the held-out split.** EXPERT, TEMPLATE and GPT4O (all 166 items), plus GPT41 on the first 60
  items. A separate exploratory run made 13 gpt-5.2 calls.
- **Not completed.** GPT41 (full), ROUTER, ROUTER_T41 and GPT52. The primary non-inferiority decision is therefore
  **not made**.
- **Status of the existing LLM responses.** They stay cached but are **provisional**. They must be regenerated on
  the replacement account before any result is used.
- **Re-run rule.** When the evaluation is re-run on the replacement account, the frozen prompt v3, the matcher
  and the router are used unchanged. All LLM policies are run once on the held-out split, without reusing the
  provisional responses: the cache keys include the deployment, so delete the cache or point it elsewhere.
  Any further change needs a new addendum.
- **Provider configuration.** The provider now reads its configuration only from environment variables and
  requires `SURVEYLAB_LLM_ENABLED=1` for live calls.

### A4 (2026-11-20): provider change from Azure OpenAI to the OpenAI API. Written and committed before any OpenAI evaluation call.

- **Provider.** The evaluation now uses the official OpenAI API, with the key read from `OPENAI_API_KEY`. Live
  calls still require `SURVEYLAB_LLM_ENABLED=1`.
- **Same model versions as before, pinned as snapshots.**
  - `gpt-4o` → `gpt-4o-2024-11-20`
  - `gpt-4.1` → `gpt-4.1-2025-04-14`

  Each logged call records the model string returned by the API.
- **Unchanged.** Everything frozen at `cd68f2b` (addendum A2) stays as it was:
  - prompt v3, the template matcher, and the ROUTER / ROUTER_T41 rules;
  - temperature 0, JSON output and max 400 tokens;
  - metrics, the primary endpoint, the 7.5 pp margin and Newcombe method 10;
  - the question set and the split.
- **Superseded results.** All provisional Azure LLM responses and results are superseded. They are kept aside for
  comparison only, never reused, and never part of any decision:
  - `results/azure_provisional/`
  - the cache `results/azure_provisional/llm_cache_azure.jsonl`, which is gitignored.

  The new cache key includes provider and snapshot, so no Azure response can be replayed by accident.
- **Policies.** `GPT52` is dropped. It was optional and exploratory, and was never part of the primary comparison.
  The prespecified held-out policies are:
  - EXPERT, TEMPLATE, GPT4O, GPT41 and ROUTER (primary);
  - ROUTER_T41 (exploratory, from A2).

  Each runs once on all 166 held-out items. The non-inferiority decision is ROUTER vs EXPERT, exactly as in §8.
  The stress set (39 items) is then run for all LLM policies and reported separately.
- **Post-hoc exploratory arm, NOT prespecified and NOT part of any decision.** `ROUTER_MINI` = TEMPLATE →
  `gpt-4.1-mini-2025-04-14`, escalating to gpt-4.1 on a guard rejection or `confidence: "low"`, the same
  escalation rule as ROUTER.
  - **Motivation.** The prespecified "cheap model first" premise failed: gpt-4.1 is cheaper per call than gpt-4o.
  - It was designed after the provisional results, so it is labeled post-hoc everywhere it is reported.
- **Prices.** OpenAI Standard-tier list prices from https://developers.openai.com/api/docs/pricing, retrieved
  2026-11-20, are in `docs/pricing.json`. Per 1M tokens (input / cached input / output):

  | Model | Input | Cached input | Output |
  |---|---|---|---|
  | gpt-4o | $2.50 | $1.25 | $10.00 |
  | gpt-4.1 | $2.00 | $0.50 | $8.00 |
  | gpt-4.1-mini | $0.40 | $0.10 | $1.60 |
- **Spend cap.** USD 8 on this key. The client refuses live calls once logged spend reaches the cap
  (`SURVEYLAB_SPEND_CAP_USD`).
- **No dev re-run.** Dev is not re-run on the new provider, except a 3-question connectivity smoke check that is
  not scored. The frozen prompt is used as-is.

### A5 (2026-11-20): OpenAI run blocked, no credits on the account

The first live call under A4 was the unscored 3-question connectivity smoke check. It returned HTTP 429
`insufficient_quota` / `credit_balance_exhausted` ("You have no credits remaining"). **No OpenAI call succeeded,
nothing was cached, and the logged spend is $0.00.**

- **Not run.** The held-out run, the non-inferiority decision, the stress-set LLM runs and the exploratory
  ROUTER_MINI arm were not run.
- **Retry behaviour.** Quota errors now fail immediately (`QuotaExhausted`) instead of being retried as rate
  limits.
- **When credits are added.** Run A4 exactly as written. Nothing else changes.
