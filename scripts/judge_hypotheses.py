"""Apply the pre-registered decision rules to the independent-set results.

The rules were fixed in docs/experiments/INDEPENDENT_SET_PREREGISTRATION.md before
any configuration ran successfully on the set. This script only evaluates them; it
does not choose metrics, thresholds or comparisons after seeing numbers.

Each rule is a *within-design* contrast: the two configurations compared differ in
exactly one component, so an effect can be attributed to that component rather than
to the prompt shape it happens to live in.

Usage:
    python scripts/judge_hypotheses.py [--input PATH] [--samples PATH]
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

# (label, left config, right config, metric, expected direction, subset or None)
RULES = [
    ("H3 交互控制", "baseline_c", "ablation_no_flow", "response_mode_accuracy", "up", None),
    ("H1 流程中间表示", "ablation_v2_no_skeleton", "method_v2", "overall_success", "up", None),
    ("H2 断言核验（强形态）", "ablation_v2_no_verify", "method_v3", "overall_success", "up", None),
    ("版本限定", "ablation_no_version_limit", "method_v2", "response_mode_accuracy", "up",
     "version_conflict"),
]

# Reported alongside; none of these decides a hypothesis.
SUPPORTING = [
    ("本方法 vs 基线C 整体成功率", "baseline_c", "method_v2", "overall_success", None),
    ("本方法 vs 基线C 应答方式", "baseline_c", "method_v2", "response_mode_accuracy", None),
    ("本方法 vs 无骨架对照 整体成功率", "ablation_no_flow", "method_v2", "overall_success", None),
    ("强核验 vs 弱核验 整体成功率", "method_v2", "method_v3", "overall_success", None),
    ("强核验 vs 无核验 整体成功率", "ablation_v2_no_verify", "method_v3", "overall_success", None),
    ("原设计 vs 骨架驱动决策 整体成功率", "method", "method_v2", "overall_success", None),
]

SUMMARY_KEYS = ["overall_success", "response_mode_accuracy", "answer_quality",
                "claim_coverage", "step_coverage", "evidence_recall", "follow_up_correct",
                "missing_slot_f1", "item_correct"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=ROOT / "data/experiments/independent-baselines.json")
    parser.add_argument("--samples", type=Path,
                        default=ROOT / "data/evaluation/independent-set.jsonl")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    samples = payload["samples"]
    scenario = {}
    if args.samples.exists():
        for line in args.samples.read_text(encoding="utf-8").splitlines():
            if line:
                row = json.loads(line)
                scenario[row["sample_id"]] = row.get("scenario_type")

    print(f"数据：{payload.get('dataset')}  {payload.get('samples_path')}")
    print(f"样本数：{payload['sample_count']}　失败：{len(payload['failures'])}　"
          f"空回答：{payload.get('empty_answers')}")

    def paired(left: str, right: str, metric: str, subset: str | None) -> dict:
        aligned_left = {r["sample_id"]: r for r in samples[left]}
        aligned_right = {r["sample_id"]: r for r in samples[right]}
        shared = [sid for sid in aligned_right if sid in aligned_left]
        if subset:
            shared = [sid for sid in shared if scenario.get(sid) == subset]
        if not shared:
            raise SystemExit(f"没有可用于 {left} vs {right} 的样本（子集 {subset}）")
        return paired_analysis(
            [aligned_left[sid]["metrics"][metric] for sid in shared],
            [aligned_right[sid]["metrics"][metric] for sid in shared],
            [aligned_right[sid]["item_id"] for sid in shared], 10000, 0,
        )

    print()
    print("=" * 96)
    print("预注册判定规则")
    print("=" * 96)
    primary = []
    for label, left, right, metric, direction, subset in RULES:
        stat = paired(left, right, metric, subset)
        primary.append({"label": label, "left": left, "right": right, "metric": metric,
                        "subset": subset, "direction": direction, **stat})
    for entry, adjusted in zip(primary, holm_adjust([e["paired_sign_flip_p"] for e in primary])):
        entry["holm_adjusted_p"] = adjusted

    for entry in primary:
        significant = entry["holm_adjusted_p"] < ALPHA
        positive = entry["mean_difference"] > 0
        holds = significant and ((positive and entry["direction"] == "up")
                                 or (not positive and entry["direction"] == "down"))
        verdict = "成立" if holds else ("方向相反" if significant and not positive else "不成立")
        scope = f"，子集 {entry['subset']}" if entry["subset"] else ""
        print(f"\n{entry['label']}（{entry['left']} → {entry['right']}，{entry['metric']}{scope}）")
        print(f"  差值 {entry['mean_difference']:+.4f}　胜 {entry['wins']}　负 {entry['losses']}　"
              f"平 {entry['ties']}　n={entry['pair_count']}　p = {entry['paired_sign_flip_p']:.4f}　"
              f"Holm p = {entry['holm_adjusted_p']:.4f}")
        print(f"  95% 区间（事项簇）{entry['item_cluster_bootstrap_ci95']}")
        print(f"  判定：{verdict}")

    print()
    print("=" * 96)
    print("配套对照（不用于判定，供读结果用）")
    print("=" * 96)
    print(f"{'对照':40s}{'差值':>9s}{'胜':>5s}{'负':>5s}{'p':>9s}")
    for label, left, right, metric, subset in SUPPORTING:
        stat = paired(left, right, metric, subset)
        print(f"{label:40s}{stat['mean_difference']:>+9.4f}{stat['wins']:>5d}"
              f"{stat['losses']:>5d}{stat['paired_sign_flip_p']:>9.4f}")

    print()
    print("=" * 96)
    print("配置总表")
    print("=" * 96)
    modes = list(payload["summary"])
    print(f"{'指标':24s}" + "".join(f"{m[:13]:>15s}" for m in modes))
    for key in SUMMARY_KEYS:
        print(f"{key:24s}" + "".join(f"{payload['summary'][m]['metrics'][key]:>15.4f}"
                                     for m in modes))

    print()
    print("=" * 96)
    print("分层：按场景（整体成功率）")
    print("=" * 96)
    scenarios = sorted({s for s in scenario.values() if s})
    if scenarios:
        print(f"{'场景':22s}" + "".join(f"{m[:13]:>15s}" for m in modes))
        for name in scenarios:
            line = f"{name:22s}"
            for mode in modes:
                rows = [r for r in samples[mode] if scenario.get(r["sample_id"]) == name]
                value = (sum(r["metrics"]["overall_success"] for r in rows) / len(rows)
                         if rows else float("nan"))
                line += f"{value:>15.4f}"
            print(line)

    report = {
        "input": str(args.input.name),
        "dataset": payload.get("dataset"),
        "sample_count": payload["sample_count"],
        "failures": len(payload["failures"]),
        "empty_answers": payload.get("empty_answers"),
        "alpha": ALPHA,
        "primary": primary,
        "supporting": [{"label": label, "left": left, "right": right, "metric": metric,
                        "subset": subset, **paired(left, right, metric, subset)}
                       for label, left, right, metric, subset in SUPPORTING],
        "summary": payload["summary"],
    }
    output = args.input.with_name(args.input.stem + "-verdicts.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写出 {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
