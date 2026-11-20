"""Run policies over a question split and write per-question records plus a summary.

usage: python scripts/run_eval.py --split dev|test|stress --policies EXPERT,TEMPLATE,GPT4O,GPT41,ROUTER [--offline]
       [--limit N] [--ids q001,q002] [--tag name]
"""
import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from survey_lab import evaluate, pipeline, prompts  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--split", required=True)
ap.add_argument("--policies", default="EXPERT,TEMPLATE,GPT4O,GPT41,ROUTER")
ap.add_argument("--offline", action="store_true", help="fail on LLM cache miss instead of calling the API")
ap.add_argument("--limit", type=int)
ap.add_argument("--ids")
ap.add_argument("--tag", default="")
ap.add_argument("--workers", type=int, default=4)
args = ap.parse_args()

qfile = ROOT / "gold" / ("stress_questions.jsonl" if args.split == "stress" else "questions.jsonl")
items = [json.loads(l) for l in qfile.read_text().splitlines() if l.strip()]
if args.split != "stress":
    items = [i for i in items if i["split"] == args.split]
if args.ids:
    keep = set(args.ids.split(",")); items = [i for i in items if i["id"] in keep]
if args.limit:
    items = items[: args.limit]

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
dirty = bool(subprocess.run(["git", "status", "--porcelain", "src", "gold", "catalog"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip())
outdir = ROOT / "results" / "runs"; outdir.mkdir(parents=True, exist_ok=True)
summary = {"split": args.split, "n_items": len(items), "commit": commit, "code_dirty": dirty,
           "prompt_version": prompts.PROMPT_VERSION, "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "policies": {}}
all_recs = {}
for pol in args.policies.split(","):
    t0 = time.time()

    def one(item, pol=pol):
        o = pipeline.expert(item["gold"]) if pol == "EXPERT" else pipeline.route(item["question"], pol, args.offline)
        rec = pipeline.to_record(o)
        rec["id"] = item["id"]
        rec["score"] = evaluate.score(item, rec)
        return rec

    workers = 1 if pol in ("EXPERT", "TEMPLATE", "GPT52") else (2 if pol in ("GPT41", "ROUTER") else args.workers)
    with ThreadPoolExecutor(workers) as ex:
        recs = list(ex.map(one, items))
    all_recs[pol] = recs
    name = f"{args.split}{('_' + args.tag) if args.tag else ''}_{pol}.jsonl"
    with open(outdir / name, "w") as f:
        for r in recs:
            f.write(json.dumps(r, default=str) + "\n")
    summary["policies"][pol] = evaluate.summarize(items, recs)
    s = summary["policies"][pol]
    print(f"{pol:9s} correct={s['outcome_correct']:.3f} spec={s['spec_exact_match']:.3f} "
          f"absP={s['abstention_precision']} absR={s['abstention_recall']} cost=${s['cost_total_usd']:.4f} "
          f"p50={s['latency_median_s']:.2f}s ({time.time() - t0:.0f}s wall)", flush=True)

ref = "EXPERT"
if ref in all_recs:
    for pol in all_recs:
        if pol == ref:
            continue
        a = [r["score"]["correct"] for r in all_recs[pol]]; b = [r["score"]["correct"] for r in all_recs[ref]]
        summary.setdefault("paired_vs_expert", {})[pol] = evaluate.newcombe_paired(a, b)
name = f"{args.split}{('_' + args.tag) if args.tag else ''}_summary.json"
(ROOT / "results" / name).write_text(json.dumps(summary, indent=1, default=str))
print("wrote", name)
