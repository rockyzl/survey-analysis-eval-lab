# All targets run inside the uv project venv. LLM targets need `az login` and a .env (see .env.example).
PY = env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run python

data:        ## convert the downloaded XPT to parquet and parse the codebook (see data/manifest.json for URLs)
	$(PY) scripts/convert_xpt.py data/raw/brfss2025/xpt/LLCP2025.XPT data/raw/brfss2025/llcp2025.parquet
	$(PY) -I scripts/parse_codebook.py data/raw/brfss2025/codebook/codebook25_llcp-v2-508.html catalog/codebook.json

gate0:       ## deterministic reproduction of CDC published values
	$(PY) scripts/gate0.py

questions:
	$(PY) gold/questions_src.py && $(PY) gold/stress_src.py

eval-offline: ## replay policies from the LLM cache (free; fails on a cache miss; ROUTER/GPT41 held-out runs are incomplete, see addendum A3)
	$(PY) scripts/run_eval.py --split test --policies EXPERT,TEMPLATE,GPT4O,GPT41,ROUTER,ROUTER_T41 --offline
	$(PY) scripts/run_eval.py --split stress --policies EXPERT,TEMPLATE,GPT4O,GPT41,ROUTER,ROUTER_T41 --offline

tables:
	$(PY) scripts/noninferiority.py && $(PY) scripts/make_tables.py

test:
	uv run pytest -q
