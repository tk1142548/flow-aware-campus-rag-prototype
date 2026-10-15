"""Build the human annotation sheet for the task-completion-rate metric.

申报书 singles out 任务完成率 -- whether an answer is enough to carry out the next
step -- as a required metric, and it cannot be computed from gold claims. This
script produces a stratified 60-item sheet with each configuration's answer, so
the judgement is made by a person reading the answers side by side.

Usage:
    python scripts/build_task_completion_sheet.py [--size 60] [--output PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.research_data import ResearchRepository
from app.backend.scoring_v2 import resolve_gold_elements

CONFIGS = ("baseline_c", "ablation_no_flow", "method_v2")


def question_of(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=60)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/evaluation/task-completion-sheet.csv")
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    results = json.loads(
        (ROOT / "data/experiments/baselines-final.json").read_text(encoding="utf-8"))
    samples = {row["sample_id"]: row for row in
               (json.loads(line) for line in
                (ROOT / "data/evaluation/stage2_samples.jsonl")
                .read_text(encoding="utf-8").splitlines() if line)}

    # Stratify by scenario so no single risk category dominates the sheet.
    buckets: dict[str, list[str]] = defaultdict(list)
    for record in results["samples"][CONFIGS[0]]:
        sample_id = record["sample_id"]
        if sample_id in samples:
            buckets[samples[sample_id]["scenario_type"]].append(sample_id)
    ordered: list[str] = []
    while any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key]:
                ordered.append(buckets[key].pop(0))
    selected = ordered[: args.size]

    answers = {config: {r["sample_id"]: r for r in results["samples"][config]}
               for config in CONFIGS}

    header = ["样本号", "场景", "用户问题", "金标准要点（判定依据）"]
    for config in CONFIGS:
        header += [f"{config} 回答", f"{config} 是否足以支撑下一步（完成/未完成/部分）"]
    header += ["标注备注"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for sample_id in selected:
            sample = samples[sample_id]
            gold = sample["gold"]
            expectations = [e["text"] for e in resolve_gold_elements(repository, sample)]
            gold_text = "\n".join(
                [f"响应方式：{gold['response_mode']}",
                 f"边界：{gold.get('answer_boundary', '')}"]
                + [f"· {text}" for text in expectations]
                + ([f"缺失条件：{'、'.join(gold['missing_slot_ids'])}"]
                   if gold.get("missing_slot_ids") else [])
            )
            row = [sample_id, sample["scenario_type"], question_of(sample), gold_text]
            for config in CONFIGS:
                row += [answers[config][sample_id]["prediction"]["answer_text"], ""]
            row += [""]
            writer.writerow(row)

    print(f"标注表 {len(selected)} 行 -> {args.output}")
    print("待标注列：" + " / ".join(
        f"{config} 是否足以支撑下一步" for config in CONFIGS))
    print("填写后运行 evaluate_task_completion.py 汇总各配置的完成率。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
