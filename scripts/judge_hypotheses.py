"""Apply the pre-registered decision rules to the independent-set results.

The rules were fixed in docs/experiments/INDEPENDENT_SET_PREREGISTRATION.md before
any configuration ran on the set. This script only evaluates them; it does not
choose metrics, thresholds or comparisons after seeing numbers.

Usage:
    python scripts/judge_hypotheses.py [--input PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.stage4_statistics import holm_adjust, paired_analysis

ALPHA = 0.05

# (label, left config, right config, metric, direction of the expected effect)
RULES = [
    ("H3 交互控制", "ablation_no_flow", "method_v2", "response_mode_accuracy", "up"),
    ("H1 流程中间表示", "ablation_no_skeleton", "method_v2", "overall_success", "up"),
    ("H2 断言核验（强形态）", "ablation_no_verify", "method_v2", "overall_success", "up"),
]

# H1 (flow representation) versus the strongest baseline, reported alongside.
SUPPORTING = [
    ("本方法 vs 基线C 整体成功率", "baseline_c", "method_v2", "overall_success"),
    ("本方法 vs 基线C 内容覆盖", "baseline_c", "method_v2", "answer_quality"),
    ("本方法 vs 基线C 应答方式", "baseline_c", "method_v2", "response_mode_accuracy"),
    ("本方法 vs 无骨架对照 整体成功率", "ablation_no_flow", "method_v2", "overall_success"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=ROOT / "data/experiments/independent-baselines.json")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    samples = payload["samples"]
    print(f"数据：{payload.get('dataset')}  {payload.get('samples_path')}")
    print(f"样本数：{payload['sample_count']}　失败：{len(payload['failures'])}")
    print()

    def paired(left: str, right: str, metric: str) -> dict:
        aligned_left = {r["sample_id"]: r for r in samples[left]}
        aligned_right = {r["sample_id"]: r for r in samples[right]}
        shared = [sid for sid in aligned_right if sid in aligned_left]
        return paired_analysis(
            [aligned_left[sid]["metrics"][metric] for sid in shared],
            [aligned_right[sid]["metrics"][metric] for sid in shared],
            [aligned_right[sid]["item_id"] for sid in shared], 10000, 0,
        )

    print("=" * 96)
    print("预注册判定规则")
    print("=" * 96)
    primary = []
    for label, left, right, metric, direction in RULES:
        stat = paired(left, right, metric)
        primary.append({"label": label, "left": left, "right": right, "metric": metric,
                        "direction": direction, **stat})
    for entry, adjusted in zip(primary, holm_adjust([e["paired_sign_flip_p"] for e in primary])):
        entry["holm_adjusted_p"] = adjusted

    for entry in primary:
        significant = entry["holm_adjusted_p"] < ALPHA
        positive = entry["mean_difference"] > 0
        holds = significant and ((positive and entry["direction"] == "up")
                                 or (not positive and entry["direction"] == "down"))
        verdict = "成立" if holds else ("方向相反" if significant and not positive else "不成立")
        print(f"\n{entry['label']}（{entry['left']} → {entry['right']}，{entry['metric']}）")
        print(f"  差值 {entry['mean_difference']:+.4f}　胜 {entry['wins']}　负 {entry['losses']}　"
              f"平 {entry['ties']}　p = {entry['paired_sign_flip_p']:.4f}　"
              f"Holm p = {entry['holm_adjusted_p']:.4f}")
        print(f"  95% 区间（事项簇）{entry['item_cluster_bootstrap_ci95']}")
        print(f"  判定：{verdict}")

    print()
    print("=" * 96)
    print("配套对照（不用于判定，供读结果用）")
    print("=" * 96)
    print(f"{'对照':38s}{'差值':>9s}{'胜':>5s}{'负':>5s}{'p':>9s}")
    for label, left, right, metric in SUPPORTING:
        stat = paired(left, right, metric)
        print(f"{label:38s}{stat['mean_difference']:>+9.4f}{stat['wins']:>5d}"
              f"{stat['losses']:>5d}{stat['paired_sign_flip_p']:>9.4f}")

    print()
    print("=" * 96)
    print("配置总表")
    print("=" * 96)
    modes = list(payload["summary"])
    keys = ["overall_success", "response_mode_accuracy", "answer_quality",
            "claim_coverage", "step_coverage", "evidence_recall", "follow_up_correct",
            "missing_slot_f1", "item_correct"]
    print(f"{'指标':24s}" + "".join(f"{m[:12]:>14s}" for m in modes))
    for key in keys:
        print(f"{key:24s}" + "".join(f"{payload['summary'][m]['metrics'][key]:>14.4f}"
                                     for m in modes))

    report = {
        "input": str(args.input.name),
        "dataset": payload.get("dataset"),
        "sample_count": payload["sample_count"],
        "alpha": ALPHA,
        "primary": primary,
        "supporting": [{"label": label, "left": left, "right": right, "metric": metric,
                        **paired(left, right, metric)}
                       for label, left, right, metric in SUPPORTING],
        "summary": payload["summary"],
    }
    output = args.input.with_name(args.input.stem + "-verdicts.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写出 {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
