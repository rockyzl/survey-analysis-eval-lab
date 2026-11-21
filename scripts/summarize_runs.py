"""Summarise whatever per-question run files exist for a split (no LLM calls; reads results/runs/*.jsonl).

Used after live LLM calls were stopped mid-run: writes results/<split>_partial_summary.json with one entry per
run file and marks LLM-backed entries as provisional.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from survey_lab import evaluate  # noqa: E402

split = sys.argv[1]
qfile = ROOT / "gold" / ("stress_questions.jsonl" if split == "stress" else "questions.jsonl")
items = {json.loads(l)["id"]: json.loads(l) for l in qfile.read_text().splitlines() if l.strip()}
out = {"split": split, "note": "Superseded provisional results from an Azure OpenAI deployment, kept for comparison only; "
       "see docs/protocol.md addenda A3/A4.", "runs": {}}
for f in sorted((ROOT / "results" / "runs").glob(f"{split}_*.jsonl")):
    recs = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    its = [items[r["id"]] for r in recs]
    s = evaluate.summarize(its, recs)
    s["provisional_llm"] = any(r["calls"] for r in recs)
    name = f.stem[len(split) + 1:]
    out["runs"][name] = s
    exp = ROOT / "results" / "runs" / f"{split}{'_gpt52subset' if 'gpt52subset' in name else ''}_EXPERT.jsonl"
    if exp.exists() and not name.endswith("EXPERT"):
        e = {json.loads(l)["id"]: json.loads(l) for l in exp.read_text().splitlines()}
        a = [r["score"]["correct"] for r in recs]; b = [e[r["id"]]["score"]["correct"] for r in recs]
        s["paired_vs_expert"] = evaluate.newcombe_paired(a, b)
    print(f"{name:22s} n={s['n']:3d} correct={s['outcome_correct']:.3f} absP={s['abstention_precision']} "
          f"absR={s['abstention_recall']} cost=${s['cost_total_usd']:.4f} provisional={s['provisional_llm']}")
(ROOT / "results" / f"{split}_partial_summary.json").write_text(json.dumps(out, indent=1, default=str))
