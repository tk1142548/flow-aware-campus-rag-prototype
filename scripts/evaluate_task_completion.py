"""Score the filled task-completion sheet produced by build_task_completion_sheet.py.

Filled cells accept 完成 / 部分 / 未完成 (1 / 0.5 / 0). The per-configuration rate is
the mean of those values; differences between configurations are tested with the
same paired sign-flip procedure used elsewhere in this project.

Usage:
    python scripts/evaluate_task_completion.py [--sheet PATH] [--output PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.stage4_statistics import holm_adjust, paired_analysis

SCORES = {"完成": 1.0, "部分": 0.5, "未完成": 0.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=Path,
                        default=ROOT / "data/evaluation/task-completion-sheet.csv")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/task-completion.json")
    args = parser.parse_args()

    with args.sheet.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    configs = [name[: -len(" 是否足以支撑下一步（完成/未完成/部分）")]
               for name in rows[0]
               if name.endswith("是否足以支撑下一步（完成/未完成/部分）")]
    if not configs:
        raise SystemExit("未找到标注列；请确认表头未被改动。")

    scored: dict[str, list[float]] = {config: [] for config in configs}
    unlabelled = 0
    item_ids: list[str] = []
    for row in rows:
        item_ids.append(row["样本号"])
        for config in configs:
            raw = (row.get(f"{config} 是否足以支撑下一步（完成/未完成/部分）") or "").strip()
            if raw not in SCORES:
                unlabelled += 1
                continue
            scored[config].append(SCORES[raw])

    labelled = len(rows) - unlabelled
    if labelled <= 0:
        raise SystemExit(f"标注列为空（{len(rows)} 行均未填写）。")

    summary = {
        config: {
            "labelled": len(values),
            "task_completion_rate": sum(values) / len(values) if values else None,
        }
        for config, values in scored.items()
    }

    comparisons = []
    baseline = configs[-1]
    for config in configs[:-1]:
        shared = [i for i, row in enumerate(rows)
                  if (row.get(f"{config} 是否足以支撑下一步（完成/未完成/部分）") or "").strip() in SCORES
                  and (row.get(f"{baseline} 是否足以支撑下一步（完成/未完成/部分）") or "").strip() in SCORES]
        if not shared:
            continue
        left = [SCORES[rows[i][f"{config} 是否足以支撑下一步（完成/未完成/部分）"].strip()]
                for i in shared]
        right = [SCORES[rows[i][f"{baseline} 是否足以支撑下一步（完成/未完成/部分）"].strip()]
                 for i in shared]
        stat = paired_analysis(left, right, [item_ids[i] for i in shared], 10000, 0)
        comparisons.append({"left": config, "right": baseline, "metric": "task_completion_rate",
                            **stat})
    for comparison, adjusted in zip(
        comparisons, holm_adjust([c["paired_sign_flip_p"] for c in comparisons])
    ):
        comparison["holm_adjusted_p"] = adjusted

    payload = {
        "status": "已汇总",
        "protocol": {"scale": SCORES, "baseline": baseline, "sheet": args.sheet.name},
        "item_count": len(rows),
        "unlabelled_cells": unlabelled,
        "summary": summary,
        "paired_comparisons": comparisons,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'配置':<18}{'已标注':>8}{'任务完成率':>12}")
    for config, entry in summary.items():
        rate = entry["task_completion_rate"]
        print(f"{config:<18}{entry['labelled']:>8}"
              f"{(f'{rate:.4f}' if rate is not None else 'n/a'):>12}")
    print(f"\n未标注单元 {unlabelled} 个；结论 -> {args.output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
