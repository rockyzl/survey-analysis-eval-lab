# Commit-hash mapping after the pre-publication history rewrite (2026-11-20)

Before publication the history was rewritten twice with `git filter-repo`:

1. **First pass.** Local file-system paths and a cloud-resource identifier were replaced with placeholders; the
   path placeholders are `<repo>` and `<other-venv>` in `results/gate0_run.log` and
   `results/gate0_v1_prespecified/gate0_run.log`.
2. **Second pass (`--replace-text`).** Some wording about the superseded Azure OpenAI runs was rephrased. Only
   `README.md` and `docs/ai-assisted-engineering.md` changed.

Commit order, dates, authors and messages are unchanged. Hashes cited in docs and result files (`results/*.json`,
`results/tables.md`, protocol addenda A2–A6) refer to the original IDs; use this table to map them to the published history.

| original | published | commit |
|---|---|---|
| 570cead | 570cead | Prespecified protocol, catalog and data manifest |
| ee64945 | d07db7e | Gate 0 and guarded NL pipeline |
| cd68f2b | 74b3e9a | Freeze prompt v3, matcher and router (A2) |
| 070999e | 866b276 | Stop live LLM calls; Azure results provisional (A3) |
| 86cb571 | 164f33b | Switch provider to the OpenAI API (A4) |
| c6e13c6 | 56c889a | Fail fast on quota errors (A5); code state of the held-out and stress runs (A6) |
| e6b5861 | 7293859 | Held-out and stress evaluation on the OpenAI API (A6) |

Two later commits were made between the two passes and have no original ID: `7ec4ec2` → `13e9428` (MIT license and
third-party attribution) and `ff0a108` → `1a41faf` (the first version of this file).
