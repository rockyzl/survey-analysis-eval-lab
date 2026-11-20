"""Pluggable LLM backend with a response cache, token/cost accounting and a hard spend cap.

Providers (SURVEYLAB_LLM_PROVIDER):
  openai (default)  official OpenAI API; key read from OPENAI_API_KEY; model snapshots are pinned (MODEL_SNAPSHOT)
  azure             kept only to replay the provisional Azure cache (results/azure_provisional/, protocol A3);
                    config from SURVEYLAB_AZURE_ENDPOINT / SURVEYLAB_AZURE_SUBSCRIPTION (keyless CLI token)
Live calls additionally require SURVEYLAB_LLM_ENABLED=1; without it only cached responses are replayed.
SURVEYLAB_SPEND_CAP_USD (default 8) stops live calls once the cache's logged spend for the provider reaches it.

Every live call is cached in results/llm_cache.jsonl (gitignored) keyed by sha256(provider, snapshot, messages),
so reruns are free and deterministic.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass

from .paths import ROOT, RESULTS

CACHE = RESULTS / "llm_cache.jsonl"
_PRICES = json.loads((ROOT / "docs" / "pricing.json").read_text())
MODEL_SNAPSHOT = {"gpt-4o": "gpt-4o-2024-11-20", "gpt-4.1": "gpt-4.1-2025-04-14",
                  "gpt-4.1-mini": "gpt-4.1-mini-2025-04-14"}
AZURE_API_VERSION = "2024-10-21"

_lock = threading.Lock()
_token = {"value": None, "expires": 0.0}
_cache_mem: dict[str, dict] | None = None


class LLMDisabled(RuntimeError):
    pass


class SpendCapReached(RuntimeError):
    pass


class QuotaExhausted(RuntimeError):
    """The account has no credits / quota: fatal, never retried (a 429 that is not a rate limit)."""


def provider() -> str:
    p = os.environ.get("SURVEYLAB_LLM_PROVIDER", "openai")
    if p not in ("openai", "azure"):
        raise ValueError(p)
    return p


def live_enabled() -> bool:
    return os.environ.get("SURVEYLAB_LLM_ENABLED") == "1"


def spend_cap() -> float:
    return float(os.environ.get("SURVEYLAB_SPEND_CAP_USD", "8"))


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


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0,
             prov: str | None = None) -> float:
    """USD cost. Cached prompt tokens are billed at the cached-input rate, the rest at the input rate."""
    p = _PRICES[prov or provider()]["models"][model]
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


def logged_spend(prov: str | None = None) -> float:
    prov = prov or provider()
    return sum(r["cost"] for r in _cache().values() if r.get("provider", "azure") == prov)


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
    provider: str = "azure"
    served_model: str | None = None   # model string returned by the API (proves the snapshot)


class LLM:
    """One logical model ('gpt-4o', 'gpt-4.1', 'gpt-4.1-mini') on the configured provider."""

    def __init__(self, model: str):
        self.model = model
        self.provider = provider()
        self.snapshot = MODEL_SNAPSHOT[model] if self.provider == "openai" else model
        self._client = None   # created lazily, only for a live call

    @property
    def client(self):
        if self._client is None:
            if not live_enabled():
                raise LLMDisabled("live LLM calls are disabled (set SURVEYLAB_LLM_ENABLED=1)")
            if self.provider == "openai":
                from openai import OpenAI
                if not os.environ.get("OPENAI_API_KEY"):
                    raise LLMDisabled("OPENAI_API_KEY must be set for live OpenAI calls")
                self._client = OpenAI(timeout=90, max_retries=0)
            else:
                from openai import AzureOpenAI
                endpoint = os.environ.get("SURVEYLAB_AZURE_ENDPOINT")
                if not endpoint or not os.environ.get("SURVEYLAB_AZURE_SUBSCRIPTION"):
                    raise LLMDisabled("SURVEYLAB_AZURE_ENDPOINT and SURVEYLAB_AZURE_SUBSCRIPTION must be set")
                self._client = AzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=_access_token,
                                           api_version=AZURE_API_VERSION, timeout=90, max_retries=0)
        return self._client

    def cache_key(self, messages: list[dict]) -> str:
        if self.provider == "azure":   # key format used by the provisional Azure cache
            return hashlib.sha256(json.dumps([self.model, messages], sort_keys=True).encode()).hexdigest()
        return hashlib.sha256(json.dumps([self.provider, self.snapshot, messages], sort_keys=True).encode()).hexdigest()

    def complete(self, messages: list[dict], offline: bool = False) -> Call:
        key = self.cache_key(messages)
        c = _cache().get(key)
        if c is not None:
            return Call(**{**c, "from_cache": True})
        if offline or not live_enabled():
            raise LLMDisabled("cache miss and live LLM calls are disabled")
        with _lock:
            spent = logged_spend(self.provider)
        if spent >= spend_cap():
            raise SpendCapReached(f"logged spend ${spent:.4f} >= cap ${spend_cap():.2f}")
        t0 = time.monotonic()
        kw = dict(model=self.snapshot, messages=messages, response_format={"type": "json_object"},
                  temperature=0, max_tokens=400)
        from openai import RateLimitError
        try:
            for attempt in range(8):   # 429s are retried with backoff and never cached as answers
                try:
                    r = self.client.chat.completions.create(**kw)
                    break
                except RateLimitError as e:
                    if "insufficient_quota" in str(e) or "credit_balance_exhausted" in str(e):
                        raise QuotaExhausted(str(e)[:300]) from None
                    if attempt == 7:
                        raise
                    time.sleep(min(60, 8 * (attempt + 1)))
            content = r.choices[0].message.content or ""
            pt, ct = r.usage.prompt_tokens, r.usage.completion_tokens
            det = getattr(r.usage, "prompt_tokens_details", None)
            cached = getattr(det, "cached_tokens", None) if det is not None else None
            finish = r.choices[0].finish_reason
            served = getattr(r, "model", None)
        except QuotaExhausted:
            raise
        except Exception as e:  # recorded, not cached
            return Call(self.model, "", 0, 0, None, round(time.monotonic() - t0, 3), 0.0, False, None,
                        f"{type(e).__name__}: {str(e)[:300]}", self.provider, None)
        secs = round(time.monotonic() - t0, 3)
        call = Call(self.model, content, pt, ct, cached, secs, cost_usd(self.model, pt, ct, cached or 0, self.provider),
                    False, finish, None, self.provider, served)
        rec = {k: v for k, v in call.__dict__.items() if k != "from_cache"}
        with _lock:
            CACHE.parent.mkdir(exist_ok=True)
            with CACHE.open("a") as f:
                f.write(json.dumps({"key": key, "messages": messages, "response": rec}) + "\n")
            _cache()[key] = rec
        return call


AzureLLM = LLM   # backwards-compatible name
