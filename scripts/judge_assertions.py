"""Judge each answer's assertions against the evidence the system retrieved (H2).

The judge model is from a different family than the generators (kimi-k2.6 vs
Qwen), so it is not grading its own outputs. Its verdicts are a measurement to be
calibrated against human labels before the unsupported rate is reported.

For every content answer in the run (gold and predicted mode give content), the
judge splits the answer into atomic assertions and labels each supported /
partial / unsupported against the retrieved evidence only.

Usage:
    python scripts/judge_assertions.py data/experiments/dev-run-qwen-plus.json \
        --samples data/evaluation/dev-set.jsonl [--configs full,full_no_verify] \
        [--output PATH] [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import judge_client
from app.backend.prompting import evidence_block
from app.backend.research_data import ResearchRepository
from app.backend.stage4_statistics import paired_analysis

CONTENT_MODES = {"answer", "scoped_correction", "version_qualified", "conversation_resolution"}

SYSTEM = (
    "你是严格的事实核验员。判断【回答】中的每条实质性陈述是否被【证据】直接支持。"
    "只依据给定证据，不使用你自己的常识补充。"
)

USER = """【证据】
{evidence}

【回答】
{answer}

把回答拆成互不重叠的原子陈述（办理主体、对象、步骤、材料、份数、时间、地点、费用、条件），
逐条判定。只输出 JSON：
{{"assertions": [{{"text": "原子陈述", "verdict": "supported | partial | unsupported",
                  "evidence_ids": ["支撑它的证据编号"]}}]}}

判定标准：
- supported：证据中有文字直接写了这个意思。
- partial：一部分有证据，另一部分是推断或补充。
- unsupported：证据中没有，或与证据矛盾。
- 礼貌用语、"建议咨询相关部门"这类不含具体事实的句子不要列出。"""


def judge_one(client, evidence_rows, answer: str) -> dict:
    data = client.chat_json(
        [{"role": "system", "content": SYSTEM},
         {"role": "user", "content": USER.format(evidence=evidence_block(evidence_rows),
                                                 answer=answer)}],
        max_tokens=2000)
    assertions = [a for a in (data.get("assertions") or []) if isinstance(a, dict)]
    counts = {v: sum(1 for a in assertions if a.get("verdict") == v)
              for v in ("supported", "partial", "unsupported")}
    total = sum(counts.values())
    return {"assertions": assertions, "counts": counts,
            "unsupported_rate": (counts["unsupported"] / total) if total else 0.0,
            "not_fully_supported_rate": ((counts["unsupported"] + counts["partial"]) / total)
            if total else 0.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--configs", default="full,full_no_verify,interaction")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    run = json.loads(args.run.read_text(encoding="utf-8"))
    samples = {s["sample_id"]: s for s in
               (json.loads(line) for line in args.samples.read_text(encoding="utf-8").splitlines()
                if line)}
    client = judge_client(ROOT / "data/cache")
    configs = [c for c in args.configs.split(",") if c in run["samples"]]

    jobs = []
    for config in configs:
        for record in run["samples"][config]:
            gold_mode = samples[record["sample_id"]]["gold"]["response_mode"]
            if gold_mode in CONTENT_MODES and record["prediction"]["response_mode"] in CONTENT_MODES:
                jobs.append((config, record))

    def work(job):
        config, record = job
        rows = [repository.evidence[e] for e in record["retrieved_evidence_ids"]
                if e in repository.evidence]
        try:
            return config, record["sample_id"], judge_one(client, rows,
                                                           record["prediction"]["answer_text"])
        except Exception as error:  # noqa: BLE001 - recorded, not swallowed
            return config, record["sample_id"], {"error": f"{type(error).__name__}: {error}"[:300]}

    results: dict[str, dict[str, dict]] = {c: {} for c in configs}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for config, sid, verdict in pool.map(work, jobs):
            results[config][sid] = verdict

    summary = {}
    for config, rows in results.items():
        good = [v for v in rows.values() if "error" not in v]
        summary[config] = {
            "judged": len(good), "errors": len(rows) - len(good),
            "unsupported_rate": sum(v["unsupported_rate"] for v in good) / len(good) if good else None,
            "not_fully_supported_rate": (sum(v["not_fully_supported_rate"] for v in good) / len(good))
            if good else None,
        }

    contrasts = []
    for left, right in (("full_no_verify", "full"), ("interaction", "full_no_verify")):
        if left in results and right in results:
            shared = [sid for sid in results[right] if sid in results[left]
                      and "error" not in results[left][sid] and "error" not in results[right][sid]]
            if len(shared) >= 2:
                stat = paired_analysis(
                    [results[left][s]["unsupported_rate"] for s in shared],
                    [results[right][s]["unsupported_rate"] for s in shared],
                    [samples[s]["allocation_item_id"] or "OUT_OF_SCOPE" for s in shared], 10000, 0)
                contrasts.append({"left": left, "right": right, "metric": "unsupported_rate", **stat})

    print(f"judge: {client.chat_model}   generation: {run.get('generation_model')}")
    for config, m in summary.items():
        print(f"  {config:18s} judged={m['judged']:3d} errors={m['errors']:2d} "
              f"unsupported={m['unsupported_rate'] if m['unsupported_rate'] is not None else float('nan'):.3f} "
              f"not_fully={m['not_fully_supported_rate'] if m['not_fully_supported_rate'] is not None else float('nan'):.3f}")
    for c in contrasts:
        print(f"  {c['left']} -> {c['right']}: diff={c['mean_difference']:+.3f} "
              f"W/L={c['wins']}/{c['losses']} p={c['paired_sign_flip_p']:.4f}")
    print(f"cost: {client.cost_summary()}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"run": args.run.as_posix(), "judge_model": client.chat_model,
                                           "summary": summary, "contrasts": contrasts,
                                           "verdicts": results}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
