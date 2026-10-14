"""Evaluate process-skeleton extraction against the hand-annotated gold.

Two modes, both oracle-free (the model never receives the gold process id):

* ``pure``   - extract from the top evidence for the question, no item hint
* ``routed`` - first guess the item from the retrieval hits, then extract from
               that item's evidence only

Metrics follow the申报书 stage-3 wording: step coverage, order consistency,
material accuracy, plus an evidence-binding rate that catches invented citations.

Usage:
    python scripts/run_flow_extraction.py [--limit N] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.flow_extractor import binding_validity, extract, order_consistency
from app.backend.research_data import ResearchRepository
from app.backend.retrieval_stack import RetrievalStack
from app.backend.scoring_v2 import ElementMatcher, lexical_containment, resolve_gold_elements

EVIDENCE_K = 8
CANDIDATE_K = 40
MODES = ("pure", "routed")
GROUNDING_THRESHOLD = 0.4
# These two processes carry a single placeholder step instead of a real sequence,
# so any extracted steps are scored against a stub. Flagged rather than hidden.
STUB_STEP_MARKER = "按照官方页面"


def question_of(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def is_stub_gold(process: dict) -> bool:
    steps = process.get("steps") or []
    return len(steps) == 1 and STUB_STEP_MARKER in steps[0].get("action", "")


def step_grounding(skeleton: dict, evidence_by_id: dict[str, dict]) -> float:
    """Fraction of extracted steps whose text is actually supported by what they cite."""
    steps = skeleton.get("steps") or []
    if not steps:
        return 1.0
    grounded = 0
    for step in steps:
        texts = " ".join(
            (evidence_by_id[eid].get("normalized_claim", "") + " "
             + evidence_by_id[eid].get("verbatim_text", ""))
            for eid in step.get("evidence_ids", []) if eid in evidence_by_id
        )
        if texts and lexical_containment(texts, step["text"]) >= GROUNDING_THRESHOLD:
            grounded += 1
    return grounded / len(steps)


def evaluate(repository: ResearchRepository, sample: dict, skeleton: dict,
             matcher: ElementMatcher, allowed_ids: set[str],
             evidence_by_id: dict[str, dict]) -> dict:
    gold_elements = resolve_gold_elements(repository, sample)
    step_texts = [e["text"] for e in skeleton.get("steps", [])]
    material_texts = [e["text"] for e in skeleton.get("materials", [])]

    step_matches = matcher.match("\n".join(step_texts),
                                 [e for e in gold_elements if e["kind"] == "step"])
    material_matches = matcher.match("\n".join(material_texts),
                                     [e for e in gold_elements if e["kind"] == "material"])
    all_matches = matcher.match(
        "\n".join(step_texts + material_texts),
        [e for e in gold_elements if e["kind"] in {"step", "material"}],
    )

    gold_step_text = {e["id"]: e["text"] for e in gold_elements if e["kind"] == "step"}
    process = repository.processes[sample["process_id"]]
    gold_order = [s["step_id"] for s in process["steps"]
                  if s["step_id"] in {e["id"] for e in gold_elements if e["kind"] == "step"}]

    binding = binding_validity(skeleton, allowed_ids)
    return {
        "step_coverage": (sum(m["covered"] for m in step_matches) / len(step_matches)
                          if step_matches else 1.0),
        "material_coverage": (sum(m["covered"] for m in material_matches) / len(material_matches)
                              if material_matches else 1.0),
        "element_coverage": (sum(m["covered"] for m in all_matches) / len(all_matches)
                             if all_matches else 1.0),
        "order_consistency": order_consistency(skeleton.get("steps", []), gold_order, gold_step_text),
        "step_grounding": step_grounding(skeleton, evidence_by_id),
        "gold_stub": is_stub_gold(process),
        "binding_rate": binding["binding_rate"],
        "invented_evidence_ids": binding["invented_evidence_ids"],
        "extracted_steps": len(skeleton.get("steps", [])),
        "extracted_materials": len(skeleton.get("materials", [])),
        "gold_steps": len(gold_step_text),
        "gold_materials": sum(1 for e in gold_elements if e["kind"] == "material"),
        "insufficient_flagged": skeleton.get("insufficient", False),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_sample(repository: ResearchRepository, stack: RetrievalStack, client: Any,
               matcher: ElementMatcher, sample: dict) -> dict:
    question = question_of(sample)
    candidates = stack.hybrid.search(question, CANDIDATE_K)
    guessed_item = RetrievalStack.guess_item([row for row, _ in candidates[:3]])

    pools = {"pure": candidates}
    pools["routed"] = [c for c in candidates if c[0]["item_id"] == guessed_item] or candidates

    entry = {
        "sample_id": sample["sample_id"],
        "item_id": sample["allocation_item_id"],
        "guessed_item": guessed_item,
        "item_guess_correct": float(guessed_item == sample["allocation_item_id"]),
        "modes": {},
    }
    for mode in MODES:
        hits = stack.reranker.rerank(question, pools[mode], EVIDENCE_K)
        rows = [row for row, _ in hits]
        skeleton = extract(client, question, rows)
        entry["modes"][mode] = {
            "skeleton": skeleton,
            "retrieved_evidence_ids": [row["evidence_id"] for row in rows],
            "metrics": evaluate(repository, sample, skeleton, matcher,
                                {row["evidence_id"] for row in rows},
                                repository.evidence),
        }
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/flow-extraction.json")
    args = parser.parse_args()

    started = time.perf_counter()
    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")
    matcher = ElementMatcher(client)

    samples = [json.loads(line) for line in
               (ROOT / "data/evaluation/stage2_samples.jsonl").read_text(encoding="utf-8").splitlines()
               if line]
    samples = [s for s in samples if s["gold"]["supporting_evidence_ids"]]
    if args.limit:
        samples = samples[: args.limit]

    verified = repository.all_verified_evidence()
    stack = RetrievalStack(verified, client, alpha=0.5)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(
            lambda sample: run_sample(repository, stack, client, matcher, sample), samples
        ))
    print(f"  {len(records)} samples done", flush=True)

    summary = {}
    for mode in MODES:
        rows = [r["modes"][mode]["metrics"] for r in records]
        real_gold = [r for r in rows if not r["gold_stub"]]
        summary[mode] = {
            "sample_count": len(rows),
            "step_coverage": mean([r["step_coverage"] for r in rows]),
            "step_coverage_excl_stub_gold": (mean([r["step_coverage"] for r in real_gold])
                                             if real_gold else None),
            "samples_with_stub_gold": len(rows) - len(real_gold),
            "material_coverage": mean([r["material_coverage"] for r in rows]),
            "element_coverage": mean([r["element_coverage"] for r in rows]),
            "order_consistency": mean([r["order_consistency"] for r in rows]),
            "step_grounding": mean([r["step_grounding"] for r in rows]),
            "binding_rate": mean([r["binding_rate"] for r in rows]),
            "insufficient_rate": mean([1.0 if r["insufficient_flagged"] else 0.0 for r in rows]),
            "avg_extracted_steps": mean([float(r["extracted_steps"]) for r in rows]),
            "avg_gold_steps": mean([float(r["gold_steps"]) for r in rows]),
            "samples_with_invented_ids": sum(1 for r in rows if r["invented_evidence_ids"]),
        }
    summary["item_guess_accuracy"] = mean([r["item_guess_correct"] for r in records])

    payload = {
        "status": "已验证",
        "protocol": {"evidence_k": EVIDENCE_K, "candidate_k": CANDIDATE_K,
                     "oracle_used": False,
                     "note": "抽取只看到用户问题与本次检索证据；金标准流程仅用于评分"},
        "dataset_version": "1.0.1-frozen(开发集)",
        "sample_count": len(records),
        "summary": summary,
        "samples": records,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "cost": client.cost_summary(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nitem guess accuracy: {summary['item_guess_accuracy']:.4f}")
    for mode in MODES:
        s = summary[mode]
        print(f"\n=== {mode} ===")
        excl = s["step_coverage_excl_stub_gold"]
        excl_text = f"{excl:.4f}" if excl is not None else "n/a"
        print(f"  step_coverage          {s['step_coverage']:.4f}"
              f"  (剔除占位金标准后 {excl_text}，占位样本 {s['samples_with_stub_gold']})")
        print(f"  material_coverage      {s['material_coverage']:.4f}")
        print(f"  order_consistency      {s['order_consistency']:.4f}")
        print(f"  step_grounding         {s['step_grounding']:.4f}")
        print(f"  binding_rate           {s['binding_rate']:.4f}")
        print(f"  avg steps {s['avg_extracted_steps']:.2f} vs gold {s['avg_gold_steps']:.2f}")
        print(f"  编造证据编号的样本 {s['samples_with_invented_ids']}")
    print(f"\ncost: {client.cost_summary()}")
    print(f"elapsed: {payload['elapsed_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
