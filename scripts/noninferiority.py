"""Prespecified non-inferiority decision (protocol section 8) from the frozen held-out run records."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from survey_lab.evaluate import newcombe_paired  # noqa: E402

proto = json.loads((ROOT / "protocol.json").read_text())["noninferiority"]
margin = proto["margin_pp"] / 100
runs = ROOT / "results" / "runs"


def load(pol):
    return {json.loads(l)["id"]: json.loads(l) for l in (runs / f"test_{pol}.jsonl").read_text().splitlines()}


exp = load("EXPERT")
ids = sorted(exp)
out = {"margin_pp": proto["margin_pp"], "method": proto["method"], "n": len(ids), "comparisons": {}}
for pol in ("ROUTER", "GPT41", "GPT4O", "ROUTER_T41", "TEMPLATE"):
    f = runs / f"test_{pol}.jsonl"
    if not f.exists():
        continue
    rec = load(pol)
    a = [rec[i]["score"]["correct"] for i in ids]; b = [exp[i]["score"]["correct"] for i in ids]
    r = newcombe_paired(a, b)
    r["non_inferior"] = r["ci_low"] > -margin
    r["role"] = "primary" if pol == "ROUTER" else ("secondary (prespecified)" if pol == "GPT41" else "exploratory")
    r["policy_errors"] = [i for i in ids if not rec[i]["score"]["correct"]]
    out["comparisons"][pol] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
p = out["comparisons"].get("ROUTER")
if p:
    out["decision"] = ("ROUTER is non-inferior to EXPERT" if p["non_inferior"] else
                       "Non-inferiority of ROUTER vs EXPERT not shown") + \
        f" (diff {100 * p['diff']:+.1f} pp, 95% CI [{100 * p['ci_low']:+.1f}, {100 * p['ci_high']:+.1f}], margin -{proto['margin_pp']} pp)"
(ROOT / "results" / "noninferiority.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
