"""Stratify the four-configuration results and attribute failures to a layer.

Reads data/experiments/baselines-final.json and joins it with the dev set's
scenario/difficulty/version metadata so a failure can be read as "the method
misses version-conflict questions at the process layer" rather than as a single
aggregate number.

Usage:
    python scripts/analyze_baselines.py [--input PATH] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = ("baseline_a", "baseline_b", "baseline_c", "ablation_no_flow",
         "ablation_no_verify", "ablation_no_skeleton", "method_v2", "method")
RISK_CATEGORY = {
    "version_conflict": "版本冲突",
    "object_mismatch": "对象错配",
    "condition_missing": "信息缺失",
    "step_error": "步骤错误",
    "material_confusion": "材料混淆",
    "out_of_scope": "越界",
    "multi_turn": "多轮",
    "direct": "直接问答",
}
UNADDRESSED_RISK = "过期入口"


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=ROOT / "data/experiments/baselines-final.json")
    parser.add_argument("--samples", type=Path,
                        default=ROOT / "data/evaluation/stage2_samples.jsonl")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/experiments/error-analysis.json")
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(ROOT))
    from app.backend.error_taxonomy import classify_errors, layer_of, primary_error

    results = json.loads(args.input.read_text(encoding="utf-8"))
    samples = {row["sample_id"]: row for row in
               (json.loads(line) for line in
                args.samples.read_text(encoding="utf-8").splitlines() if line)}

    report: dict = {"source": str(args.input.name), "modes": {}, "risk_coverage": {}}
    for mode in MODES:
        rows = results["samples"].get(mode, [])
        if not rows:
            continue
        per_scenario: dict[str, list] = defaultdict(list)
        primary_counter: Counter[str] = Counter()
        layer_counter: Counter[str] = Counter()
        for row in rows:
            meta = samples.get(row["sample_id"], {})
            scenario = meta.get("scenario_type", "unknown")
            per_scenario[scenario].append(row)
            codes = classify_errors(row["metrics"])
            primary_counter[primary_error(codes)] += 1
            layer_counter[layer_of(codes)] += 1
        report["modes"][mode] = {
            "sample_count": len(rows),
            "overall_success": mean([r["metrics"]["overall_success"] for r in rows]),
            "answer_quality": mean([r["metrics"]["answer_quality"] for r in rows]),
            "by_scenario": {
                scenario: {
                    "n": len(group),
                    "overall_success": mean([r["metrics"]["overall_success"] for r in group]),
                    "answer_quality": mean([r["metrics"]["answer_quality"] for r in group]),
                }
                for scenario, group in sorted(per_scenario.items())
            },
            "primary_errors": dict(primary_counter.most_common()),
            "failing_layers": dict(layer_counter.most_common()),
        }

    # How much of each risk category the current set actually exercises, and
    # which category has no samples at all.
    counts = Counter(RISK_CATEGORY.get(s["scenario_type"], s["scenario_type"])
                     for s in samples.values())
    covered = set(counts)
    report["risk_coverage"] = {
        "counts": dict(counts),
        "categories_present": sorted(covered),
        "categories_missing": [UNADDRESSED_RISK] if UNADDRESSED_RISK not in covered else [],
        "note": ("过期入口 在现有证据层中没有任何样本：来源可用性（HTTP 410/403、认证跳转）"
                 "只记录在 source_records，未进入可检索的 evidence 层，"
                 "因此系统无法在回答中区分有效与失效入口。这是数据层缺口，不是方法缺陷。"),
    }

    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'mode':12s}{'n':>5s}{'overall':>9s}{'quality':>9s}  最早失效层分布")
    for mode in MODES:
        entry = report["modes"].get(mode)
        if not entry:
            continue
        layers = ", ".join(f"{k}:{v}" for k, v in entry["failing_layers"].items())
        print(f"{mode:12s}{entry['sample_count']:>5d}{entry['overall_success']:>9.4f}"
              f"{entry['answer_quality']:>9.4f}  {layers}")

    print("\n=== method 分层成功情况 ===")
    entry = report["modes"].get("method")
    if entry:
        for scenario, stats in entry["by_scenario"].items():
            label = RISK_CATEGORY.get(scenario, scenario)
            print(f"  {label:8s} n={stats['n']:>3d}  overall={stats['overall_success']:.3f}"
                  f"  quality={stats['answer_quality']:.3f}")

    print("\n=== 风险类别覆盖 ===")
    for name, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name:8s} {count}")
    print(f"  缺失类别: {report['risk_coverage']['categories_missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
