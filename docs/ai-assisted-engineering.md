# AI-assisted engineering note

## Who did what

- **Lu Zhang** chose the project, set the requirements and constraints, and set the honesty rules. His requirements
  covered:
  - BRFSS microdata, with CDC published values as the reference answers;
  - Gate 0 before any LLM run;
  - a guarded spec instead of free-form code;
  - routing and cost tracking;
  - a prespecified non-inferiority test;
  - an env-configured Azure OpenAI endpoint with keyless auth, a budget cap, and no new system software.
- **An AI coding agent (Claude, Anthropic) implemented the code under Lu's direction.** That covers the data
  download, codebook parsing, the catalog mapping, the survey estimator, Gate 0, the guard, executor, matcher
  and prompts, the evaluation harness, the tests and the documentation.
- **The question set and gold specs were also written by the agent.** That is a limitation: the same author
  wrote the questions, the template matcher and the prompts. See `docs/protocol.md` addendum A2.

Every number in the README comes from a file under `results/` that a script in `scripts/` produced.

## Verification that caught defects and mistakes

| # | Defect / mistake | How it was caught | Fix |
|---|---|---|---|
| 1 | First download of `LLCP2025XPT.zip` was truncated (48.5 of 64.6 MB) and failed to unzip | `BadZipFile`, then compared against `content-length` | resumed with `curl -C -`; SHA-256 of the complete file in `data/manifest.json` |
| 2 | Zip member name had a trailing space (`'LLCP2025.XPT '`) | file listing | renamed on extraction; noted in manifest |
| 3 | First codebook parser read the wrong table cells (value labels became percentages) | spot-checking parsed labels against the HTML | rewrote the parser to read `<tr>`/`<td>` rows |
| 4 | Wrong race variable (`_RACE` instead of `_RACEPRV`) | **Gate 0 run 1**: RACE8 reproduced only 46% of cells; `sample_size` counts disagreed | catalog fix (addendum A1) |
| 5 | CIs not truncated at 0/100 | Gate 0 run 1 CI mismatches above 100% | clip in estimator |
| 6 | Break-out CI too wide in small domains: missing break-out values kept in the design | Gate 0 run 1 break-out set failed (90.2%); 3 hypotheses tested on 3 cells | listwise exclusion of missing break-out values (CDC/SAS convention) |
| 7 | CDC medians include suppressed jurisdictions | Gate 0 median cells: CDC's jurisdiction count (50) > mine (47) | median over all jurisdiction estimates |
| 8 | CDC does not publish zero-numerator cells | suppression sub-check (1,730 disagreements) | `n_yes == 0` counts as not published |
| 9 | Two hand-written questions pointed at break-outs CDC does not publish (65–74 / 75+ exist only for flu/pneumonia vaccines) | question-file build step checks every gold reference exists | the two questions were rewritten before any LLM call |
| 10 | Template matcher answered single-subgroup questions while ignoring a second, unparsed restriction (e.g. income ranges) | dev run of TEMPLATE | matcher now defers when unexplained restriction wording remains |
| 11 | Hispanic regex matched inside "non-Hispanic" | dev review of template output | negative look-behind |
| 12 | gpt-4.1 HTTP 429 rate-limit errors were silently scored as abstentions (dev v1: 11 of 54 items) | inspected dev errors, which showed `RateLimitError` in `guard_errors` | retry with backoff; errors are never cached; fewer workers |
| 13 | Prompt v2 rule regressed gpt-4o (single-subgroup questions → `multiple_subgroups`) | dev v2 vs v1 comparison | v3 reworded the rule |
| 14 | Newcombe CI: continuity correction of phi initially applied symmetrically | checked against Newcombe (1998) example (a), CI 0.0569–0.3404 | correction applied only when ad > bc; unit test |
| 15 | Wilson upper bound compared with `==` 1.0 (floating point) | failing unit test | `pytest.approx` |
| 16 | Toy test fixture too small, so the estimate was correctly suppressed (n < 50) and the test failed | failing unit test | larger fixture |
| 17 | A gold label is debatable: q101 "flu vaccination among women 65+". Gold says `multiple_subgroups`, but 65+ is the flu-shot indicator's own universe, so only one subgroup is involved | held-out results review (TEMPLATE answered it) | gold not edited; sensitivity analysis reported (see README) |
| 18 | Live LLM calls were stopped mid-way through the held-out run to change provider, away from the Azure OpenAI deployment used until then | coordinator decision during the held-out run | live calls stopped; provider made env-only and opt-in; LLM results marked provisional (addendum A3) |
| 19 | The first OpenAI attempt hit an account with no credits; the retry loop treated `insufficient_quota` as a rate limit and kept retrying | direct probe of the API error body | quota errors now raise `QuotaExhausted` immediately (A5) |
| 20 | README draft overstated two figures: the count of grounded LLM answers (said 1,284, actual 791) and the cached-token share (said 77–90%) | recomputed from the run files before committing | corrected |
| 21 | The first q101 sensitivity analysis scored EXPERT as wrong on the relabelled item | reviewing the sensitivity output | EXPERT executes the relabelled gold spec and is scored correct |

## Things the agent did not do

- It did not create, modify or delete any Azure resource.
- Azure calls used a short-lived Azure CLI token for an explicitly named subscription, not an API key. The final OpenAI run read `OPENAI_API_KEY` from the environment; no key is stored in the repository. Earlier provisional runs on an Azure OpenAI deployment (637 calls) were superseded by the OpenAI API run (addenda A3/A4) and are kept only for comparison. The final evaluation used the OpenAI API: 538 calls, $1.80.
- It installed no system software. Python dependencies only, via `uv`.
- It did not create a GitHub remote during development; the author published the repository.
