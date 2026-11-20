"""Azure OpenAI backend (keyless: short-lived Azure CLI token for an explicitly named subscription).

Every call is cached in results/llm_cache.jsonl (gitignored) keyed by sha256(deployment, messages), so reruns are
free and deterministic. Token usage (incl. cached prompt tokens when the API reports them), latency and USD cost
are recorded per call.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import ROOT, RESULTS

CACHE = RESULTS / "llm_cache.jsonl"
PRICING = json.loads((ROOT / "docs" / "pricing.json").read_text())["models"]
API_VERSION = "2024-10-21"
API_VERSION_GPT52 = "2025-04-01-preview"

_lock = threading.Lock()
_token = {"value": None, "expires": 0.0}
_cache_mem: dict[str, dict] | None = None


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _access_token() -> str:
    with _lock:
        if _token["expires"] < time.time() + 120:
            sub = os.environ["SURVEYLAB_AZURE_SUBSCRIPTION"]
            r = subprocess.run(["az", "account", "get-access-token", "--subscription", sub,
                                "--resource", "https://cognitiveservices.azure.com/", "-o", "json"],
                               capture_output=True, text=True, timeout=60, check=True)
            d = json.loads(r.stdout)
            _token.update(value=d["accessToken"], expires=float(d.get("expires_on", time.time() + 600)))
        return _token["value"]


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float:
    """USD cost. Cached prompt tokens are billed at the cached-input rate, the rest at the input rate."""
    p = PRICING[model]
    cached = min(cached_tokens or 0, prompt_tokens)
    return ((prompt_tokens - cached) * p["input"] + cached * p["cached_input"]
            + completion_tokens * p["output"]) / 1e6


def _cache() -> dict[str, dict]:
    global _cache_mem
    if _cache_mem is None:
        _cache_mem = {}
        if CACHE.exists():
            with CACHE.open() as f:
                for line in f:
                    rec = json.loads(line)
                    _cache_mem[rec["key"]] = rec["response"]
    return _cache_mem


@dataclass
class Call:
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int | None     # None = not reported by the API
    seconds: float
    cost: float
    from_cache: bool
    finish_reason: str | None = None
    error: str | None = None


class AzureLLM:
    def __init__(self, model: str):
        from openai import AzureOpenAI
        _load_env()
        self.model = model
        if model == "gpt-5.2":
            endpoint, api = os.environ["SURVEYLAB_AZURE_ENDPOINT_GPT52"], API_VERSION_GPT52
        else:
            endpoint, api = os.environ["SURVEYLAB_AZURE_ENDPOINT"], API_VERSION
        self.client = AzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=_access_token,
                                  api_version=api, timeout=90, max_retries=2)

    @staticmethod
    def available() -> bool:
        _load_env()
        return bool(os.environ.get("SURVEYLAB_AZURE_ENDPOINT") and os.environ.get("SURVEYLAB_AZURE_SUBSCRIPTION"))

    def complete(self, messages: list[dict], offline: bool = False) -> Call:
        key = hashlib.sha256(json.dumps([self.model, messages], sort_keys=True).encode()).hexdigest()
        c = _cache().get(key)
        if c is not None:
            return Call(**{**c, "from_cache": True})
        if offline:
            raise RuntimeError("cache miss in offline mode")
        t0 = time.monotonic()
        kw = dict(model=self.model, messages=messages, response_format={"type": "json_object"})
        if self.model == "gpt-5.2":
            # reasoning model: temperature is fixed by the service; max_completion_tokens covers reasoning tokens
            kw.update(max_completion_tokens=2000, reasoning_effort="low")
        else:
            kw.update(temperature=0, max_tokens=400)
        err = None
        try:
            r = self.client.chat.completions.create(**kw)
            content = r.choices[0].message.content or ""
            pt, ct = r.usage.prompt_tokens, r.usage.completion_tokens
            det = getattr(r.usage, "prompt_tokens_details", None)
            cached = getattr(det, "cached_tokens", None) if det is not None else None
            finish = r.choices[0].finish_reason
        except Exception as e:  # recorded, not cached
            return Call(self.model, "", 0, 0, None, round(time.monotonic() - t0, 3), 0.0, False, None,
                        f"{type(e).__name__}: {str(e)[:300]}")
        secs = round(time.monotonic() - t0, 3)
        call = Call(self.model, content, pt, ct, cached, secs, cost_usd(self.model, pt, ct, cached or 0), False, finish, err)
        rec = {k: v for k, v in call.__dict__.items() if k != "from_cache"}
        with _lock:
            CACHE.parent.mkdir(exist_ok=True)
            with CACHE.open("a") as f:
                f.write(json.dumps({"key": key, "messages": messages, "response": rec}) + "\n")
            _cache()[key] = rec
        return call
