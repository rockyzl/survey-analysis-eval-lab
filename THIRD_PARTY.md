# Third-party data and attribution

This repository contains **code, catalog metadata, CDC-published reference values and aggregate results only**. The BRFSS microdata files are not redistributed (see `.gitignore`). `data/manifest.json` records their source URLs and SHA-256 hashes.

| Component | Source | Terms |
|---|---|---|
| Survey microdata | CDC Behavioral Risk Factor Surveillance System (BRFSS) 2025 LLCP annual data, https://www.cdc.gov/brfss/annual_data/ | U.S. federal public-use data. Follow CDC's BRFSS data-use guidance (no re-identification attempts; cite CDC BRFSS) |
| Codebook / calculated-variable documentation | CDC BRFSS 2025 codebook and calculated-variables documentation | Public U.S. government documentation |
| Published reference estimates (`gold/cdc_reference_2025.csv.gz`) | CDC "BRFSS Prevalence & Trends" data on data.cdc.gov (dataset `dttw-5yxu`), snapshot 2026-11-20 | Public-domain U.S. government data; excerpted |
| LLM | OpenAI API (gpt-4o-2024-11-20, gpt-4.1-2025-04-14, gpt-4.1-mini-2025-04-14), called at run time with the author's own API key | No model weights or keys are included |

Source: Centers for Disease Control and Prevention (CDC), Behavioral Risk Factor Surveillance System Survey Data, 2025. U.S. Department of Health and Human Services. This project is independent and not affiliated with or endorsed by CDC. Results are for methods demonstration only.
