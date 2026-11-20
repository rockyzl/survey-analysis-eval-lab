"""End-to-end question answering under a routing policy.

question -> (template | LLM) -> JSON spec -> guard -> deterministic executor -> deterministic answer -> grounding check
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from . import answer, executor, prompts, templates
from .llm import AzureLLM, Call
from .spec import GuardError, Spec, abstain, validate

POLICIES = ("TEMPLATE", "GPT4O", "GPT41", "ROUTER", "GPT52")
MODEL_OF = {"GPT4O": "gpt-4o", "GPT41": "gpt-4.1", "GPT52": "gpt-5.2"}
_clients: dict[str, AzureLLM] = {}


@dataclass
class Outcome:
    policy: str
    spec: Spec
    path: list[str]                      # e.g. ["template"], ["gpt-4o"], ["gpt-4o", "gpt-4.1"]
    calls: list[Call] = field(default_factory=list)
    guard_errors: list[str] = field(default_factory=list)
    result: executor.Result | None = None
    answer: str = ""
    ungrounded: list[str] = field(default_factory=list)
    seconds: float = 0.0                 # logged LLM latency + measured local time

    @property
    def cost(self) -> float:
        return sum(c.cost for c in self.calls)


def _client(model: str) -> AzureLLM:
    if model not in _clients:
        _clients[model] = AzureLLM(model)
    return _clients[model]


def llm_spec(question: str, model: str, offline: bool = False) -> tuple[Spec | None, Call, str | None]:
    call = _client(model).complete(prompts.messages(question), offline=offline)
    if call.error:
        return None, call, f"api error: {call.error}"
    try:
        return validate(call.content), call, None
    except GuardError as e:
        return None, call, str(e)


def route(question: str, policy: str, offline: bool = False) -> Outcome:
    t0 = time.monotonic()
    calls: list[Call] = []
    errors: list[str] = []
    path: list[str] = []
    spec: Spec | None = None
    if policy in ("TEMPLATE", "ROUTER"):
        spec = templates.match(question)
        path.append("template")
        if spec is None and policy == "TEMPLATE":
            spec = abstain("ambiguous", "no confident template match")
    if spec is None:
        first = "gpt-4o" if policy == "ROUTER" else MODEL_OF[policy]
        s, call, err = llm_spec(question, first, offline)
        calls.append(call); path.append(first)
        if err:
            errors.append(f"{first}: {err}")
        spec = s
        if policy == "ROUTER" and (spec is None or spec.confidence == "low"):
            s2, call2, err2 = llm_spec(question, "gpt-4.1", offline)
            calls.append(call2); path.append("gpt-4.1")
            if err2:
                errors.append(f"gpt-4.1: {err2}")
            if s2 is not None:
                spec = s2
        if spec is None:
            spec = abstain("ambiguous", "model output rejected by the guard")
    out = Outcome(policy=policy, spec=spec, path=path, calls=calls, guard_errors=errors)
    if spec.answerable:
        out.result = executor.execute(spec)
    out.answer = answer.render(spec, out.result)
    out.ungrounded = answer.check_grounding(out.answer, spec, out.result)
    if out.ungrounded:   # never show numbers the executor did not produce
        out.answer = "Answer withheld: grounding check failed."
    local = time.monotonic() - t0 - sum(c.seconds for c in calls if not c.from_cache)
    out.seconds = round(sum(c.seconds for c in calls) + max(local, 0.0), 3)
    return out


def expert(gold: dict) -> Outcome:
    """EXPERT policy: execute the hand-assigned gold spec (no NL interpretation)."""
    t0 = time.monotonic()
    obj = {"answerable": gold["answerable"]}
    if gold["answerable"]:
        sg = gold.get("subgroup")
        obj.update(indicator=gold["indicator"], response=gold["response"], geography=gold["geography"],
                   subgroup={"category": sg[0], "value": sg[1]} if sg else None)
    else:
        obj["abstain_reason"] = gold["abstain_reason"]
    spec = validate(obj)
    out = Outcome(policy="EXPERT", spec=spec, path=["expert"])
    if spec.answerable:
        out.result = executor.execute(spec)
    out.answer = answer.render(spec, out.result)
    out.ungrounded = answer.check_grounding(out.answer, spec, out.result)
    out.seconds = round(time.monotonic() - t0, 3)
    return out


def to_record(o: Outcome) -> dict:
    r = o.result
    return {"policy": o.policy, "path": o.path, "spec": o.spec.to_dict(), "guard_errors": o.guard_errors,
            "estimate": None if r is None else r.estimate, "ci_low": None if r is None else r.ci_low,
            "ci_high": None if r is None else r.ci_high, "n_yes": None if r is None else r.n_yes,
            "n_denom": None if r is None else r.n_denom, "suppressed": None if r is None else r.suppressed,
            "answer": o.answer, "ungrounded": o.ungrounded, "seconds": o.seconds, "cost_usd": round(o.cost, 6),
            "calls": [{"model": c.model, "prompt_tokens": c.prompt_tokens, "completion_tokens": c.completion_tokens,
                       "cached_tokens": c.cached_tokens, "seconds": c.seconds, "cost_usd": round(c.cost, 6),
                       "from_cache": c.from_cache, "error": c.error, "raw": c.content[:600]} for c in o.calls],
            "trace": None if r is None else r.trace}


def dumps(o: Outcome) -> str:
    return json.dumps(to_record(o), indent=1, default=str)
