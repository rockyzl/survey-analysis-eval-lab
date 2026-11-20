# Gate 0 investigation log

Gate 0 compares deterministic, hand-specified estimates with CDC BRFSS Prevalence & Trends (P&T) 2025 crude
prevalence, using the frozen snapshot in `gold/cdc_reference_2025.csv.gz`. The tolerance is 0.1 pp on the point
estimate and on each CI limit. This log records every mismatch class found, what caused it, and what changed.
The prespecified first run is archived unchanged in `results/gate0_v1_prespecified/`.

## Run 1: prespecified conventions (`results/gate0_v1_prespecified/gate0_summary.json`)

| Cell set | Cells | Reproduced | Rate | Pass (≥95%) |
|---|---|---|---|---|
| G0_primary (Overall) | 7,897 | 7,715 | 97.7% | yes |
| G0_breakout | 157,897 | 142,384 | 90.2% | **no** |
| G0_median | 320 | 310 | 96.9% | yes |

The run flagged one indicator, `RACE8`, with only 46% of its primary cells reproduced. Excluding `RACE8`, 100% of
Overall cells reproduced. Every point-estimate mismatch outside race involved the race variable.

### Mismatch class 1: wrong race variable (affected `RACE8` and every Race/Ethnicity break-out)

- **Symptom.** The point estimates were off, and so were the counts: for WA White non-Hispanic, my count was
  14,467 vs CDC's `sample_size` 14,966.
- **Cause.** CDC uses `_RACEPRV`, not `_RACE`. `_RACEPRV` assigns respondents with don't know/refused race
  (`_RACE` = 9) to their imputed race (`_IMPRACE`). With `_RACEPRV`, all 8 WA counts match exactly
  (14,966 / 528 / 207 / 940 / 143 / 200 / 663 / 1,852).
- **Fix.** `catalog/indicators.json`: `RACE8` and the Race/Ethnicity subgroup now use `_RACEPRV`.

### Mismatch class 2: CIs not truncated at 0/100

- **Symptom.** Points matched, but CI limits went above 100 (e.g. GU, BLIND = No: 102.13 vs CDC 100.00).
- **Cause.** CDC truncates Wald limits to [0, 100].
- **Fix.** `survey.domain_proportions(clip=True)`.

### Mismatch class 3: break-out CIs slightly too wide in small domains

- **Symptom.** Points and counts matched exactly, but the CI half-width was too large in some small break-out cells.
  Example: FL, depression = Yes, income $200,000+. Mine was [8.41, 17.26], CDC's is [8.71, 16.95].
- **Hypotheses tested on 3 cells (FL, SC, MA):**

  | Variant | FL [8.71, 16.95] | SC [14.84, 38.32] | MA [25.28, 33.36] |
  |---|---|---|---|
  | full-design domain (prespecified) | 8.41, 17.26 | 14.57, 38.58 | 25.02, 33.62 |
  | subset to the domain, then estimate | 8.80, 16.87 | 14.85, 38.31 | 25.47, 33.17 |
  | **drop records missing the response OR the break-out variable, then domain-estimate** | **8.71, 16.96** | **14.83, 38.33** | **25.28, 33.36** |

- **Cause.** This matches SAS-style listwise exclusion of table variables. Records with a missing break-out value
  (e.g. `_INCOMG1` = 9) leave the analysis entirely, rather than staying as zero-contribution rows in the
  design. Within each stratum this changes the PSU count `n_h`, which changes the variance.
- **Fix.** The executor and Gate 0 drop records whose break-out variable is outside its non-missing universe
  before estimation. The 65–74 / 75+ age groups come from imputed `_AGE80`, which has no missing values.

### Mismatch class 4: CDC medians include suppressed jurisdictions

- **Symptom.** For US/UW medians, CDC's `sample_size` equals the number of jurisdictions, and it counted 50 / 48,
  including jurisdictions whose own estimate is suppressed.
- **Fix.** The median is now taken over every jurisdiction estimate, without dropping suppressed ones.

### Sub-check: suppression rule

- CDC also publishes no value when the numerator count is 0. Footnote `***` appears in 1,730 cells where my
  estimate was exactly 0.
- **Fix.** `survey.suppressed(..., n_yes)`.

## Run 2: corrected conventions (`results/gate0_summary.json`, the current results)

| Cell set | Cells | Reproduced | Rate | Max \|Δpoint\| | Max \|ΔCI\| | `sample_size` exact |
|---|---|---|---|---|---|---|
| G0_primary (Overall) | 7,897 | 7,897 | **100.0%** | 0.005 pp | 0.019 pp | 100% |
| G0_breakout | 157,897 | 157,897 | **100.0%** | 0.005 pp | 0.019 pp | 100% |
| G0_median | 320 | 318 | **99.4%** | 0.20 pp | n/a | n/a |

The maximum point difference of 0.005 pp is rounding, since CDC publishes 2 decimals. The CI differences of up to
0.019 pp are consistent with rounding plus a slightly different critical value. They are well inside the 0.1 pp
tolerance.

### Remaining unexplained differences (not fixed)

1. **NHPI medians (2 cells).** For `RACE8`, Native Hawaiian or Pacific Islander non-Hispanic, CDC publishes US and
   UW medians of 0.0. It says 47 and 46 jurisdictions contributed. My median over all 50 / 48 jurisdiction
   estimates is 0.20. Only 3 of 50 jurisdictions have an estimate of exactly 0. I could not reproduce CDC's
   number and did not tune toward it.
2. **Suppression at the RSE boundary.** Suppression decisions disagree in 135 of ~215k cells (0.06%). All of them
   have RSE between 0.283 and 0.321. CDC probably computes RSE from rounded or slightly different SEs. This does
   not affect any published value I compare.

## What this means for the evaluation

- The deterministic EXPERT pipeline reproduces every published CDC state and break-out cell in the 2025 P&T file
  within 0.1 pp.
- Held-out questions therefore cannot fail because of the reference pipeline, except the 2 NHPI median cells,
  which no question uses.
- These fixes were made **after** seeing Gate 0 mismatches. They are listed in protocol addendum A1. Both the
  prespecified and the corrected rates are reported.
