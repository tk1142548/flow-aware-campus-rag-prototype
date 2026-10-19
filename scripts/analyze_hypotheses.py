"""Per-hypothesis analysis with one primary test per hypothesis.

Reads stored run files and judge verdicts; no model is called.

Each hypothesis has one primary metric, fixed here and in the pre-registration:

    H1  full_no_skeleton -> full        step_recall      (multi-step samples)
    H2  full_no_verify  -> full         unsupported_rate (judge verdicts)
    H3  baseline_c      -> interaction   mode_correct     (all samples)

The primary tests from every model form one family, Holm-adjusted as a whole.
Every other metric is printed for explanation and error analysis and is marked
as not part of the family.

Usage:
    python scripts/analyze_hypotheses.py \
        --run qwen-plus=data/experiments/run-plus.json \
        --run small=data/experiments/run-small.json \
        --judge qwen-plus=data/experiments/judge-plus.json \
        --samples data/evaluation/dev-set.jsonl [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.hypothesis_metrics import (MULTI_STEP, interaction_metrics,
                                            per_sample_scores)
from app.backend.stage4_statistics import holm_adjust, paired_analysis

# hypothesis: (left, right, primary metric, direction favouring the right side)
PRIMARY = {
    "H1": ("full_no_skeleton", "full", "step_recall", "higher"),
    "H2": ("full_no_verify", "full", "unsupported_rate", "lower"),
    "H3": ("baseline_c", "interaction", "mode_correct", "higher"),
}
SECONDARY = {
    "H1": ("step_order", "material_recall", "step_coverage", "answer_quality"),
    "H2": ("citation_validity", "claim_coverage", "answer_quality"),
    "H3": ("mode_macro_f1", "abstain_precision", "abstain_recall", "over_clarification"),
}
CONTENT_MODES = {"answer", "scoped_correction", "version_qualified", "conversation_resolution"}


def paired(left_rows, right_rows, metric, keep, items):
    left = {r["sample_id"]: r for r in left_rows}
    right = {r["sample_id"]: r for r in right_rows}
    pairs = [(sid, left[sid][metric], right[sid][metric]) for sid in right
             if sid in left and keep(sid)
             and left[sid].get(metric) is not None and right[sid].get(metric) is not None]
    if len(pairs) < 2:
        return {"pair_count": len(pairs)}
    stat = paired_analysis([p[1] for p in pairs], [p[2] for p in pairs],
                           [items[p[0]] for p in pairs], 10000, 0)
    stat["left_mean"] = sum(p[1] for p in pairs) / len(pairs)
    stat["right_mean"] = sum(p[2] for p in pairs) / len(pairs)
    stat["pair_count"] = len(pairs)
    return stat


def judge_rates(judge_path: Path) -> dict[str, dict[str, float]]:
    """Per-sample unsupported rate for each configuration the judge covered."""
    data = json.loads(judge_path.read_text(encoding="utf-8"))
    return {config: {sid: v["unsupported_rate"] for sid, v in rows.items() if "error" not in v}
            for config, rows in data["verdicts"].items()}


def primary_tests(name: str, run: dict, samples: dict, multi_step: set[str],
                  items: dict, judge: dict | None) -> list[dict]:
    scores = {mode: [{"sample_id": r["sample_id"], **per_sample_scores(r, samples[r["sample_id"]]["gold"]["response_mode"])}
                     for r in rows]
              for mode, rows in run["samples"].items()}
    tests = []
    for hypothesis, (left, right, metric, direction) in PRIMARY.items():
        if metric == "unsupported_rate":
            if judge is None or left not in judge or right not in judge:
                tests.append({"hypothesis": hypothesis, "model": name, "metric": metric,
                              "pair_count": 0, "missing": "no judge output"})
                continue
            left_rows = [{"sample_id": s, "unsupported_rate": v} for s, v in judge[left].items()]
            right_rows = [{"sample_id": s, "unsupported_rate": v} for s, v in judge[right].items()]
            keep = lambda sid: True  # noqa: E731 - judged samples only
        elif metric == "step_recall":
            left_rows, right_rows = scores.get(left, []), scores.get(right, [])
            keep = lambda sid: sid in multi_step  # noqa: E731
        else:
            left_rows, right_rows = scores.get(left, []), scores.get(right, [])
            keep = lambda sid: True  # noqa: E731
        if not left_rows or not right_rows:
            tests.append({"hypothesis": hypothesis, "model": name, "metric": metric,
                          "pair_count": 0, "missing": f"{left} or {right} not run"})
            continue
        stat = paired(left_rows, right_rows, metric, keep, items)
        tests.append({"hypothesis": hypothesis, "model": name, "metric": metric,
                      "left": left, "right": right, "direction": direction, **stat})
    return tests


def secondary_rows(name: str, run: dict, samples: dict, multi_step: set[str],
                   items: dict) -> list[dict]:
    scores = {mode: [{"sample_id": r["sample_id"], **per_sample_scores(r, samples[r["sample_id"]]["gold"]["response_mode"])}
                     for r in rows]
              for mode, rows in run["samples"].items()}
    rows = []
    for hypothesis, (left, right, _, _) in PRIMARY.items():
        for metric in SECONDARY[hypothesis]:
            keep = (lambda sid: sid in multi_step) if metric in ("step_order", "step_recall") else (lambda sid: True)
            if metric in ("step_order", "material_recall"):
                source = scores
                left_rows, right_rows = source.get(left, []), source.get(right, [])
            else:
                left_rows = [{"sample_id": r["sample_id"], "m": r["metrics"].get(metric)}
                             for r in run["samples"].get(left, [])]
                right_rows = [{"sample_id": r["sample_id"], "m": r["metrics"].get(metric)}
                              for r in run["samples"].get(right, [])]
                left_rows = [{"sample_id": r["sample_id"], metric: r["m"]} for r in left_rows]
                right_rows = [{"sample_id": r["sample_id"], metric: r["m"]} for r in right_rows]
            if not left_rows or not right_rows:
                continue
            stat = paired(left_rows, right_rows, metric, keep, items)
            rows.append({"hypothesis": hypothesis, "model": name, "metric": metric,
                         "left": left, "right": right, **stat})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--judge", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    samples = {s["sample_id"]: s for s in
               (json.loads(line) for line in args.samples.read_text(encoding="utf-8").splitlines() if line)}
    items = {sid: s["allocation_item_id"] or "OUT_OF_SCOPE" for sid, s in samples.items()}
    multi_step = {sid for sid, s in samples.items()
                  if len(s["gold"]["ordered_step_ids"]) >= MULTI_STEP}

    runs = {}
    for spec in args.run:
        name, path = spec.split("=", 1)
        runs[name] = json.loads(Path(path).read_text(encoding="utf-8"))
    judges = {}
    for spec in args.judge:
        name, path = spec.split("=", 1)
        if Path(path).exists():
            judges[name] = judge_rates(Path(path))

    tests, secondary, interaction = [], [], {}
    for name, run in runs.items():
        tests += primary_tests(name, run, samples, multi_step, items, judges.get(name))
        secondary += secondary_rows(name, run, samples, multi_step, items)
        interaction[name] = {mode: interaction_metrics(rows, {sid: s["gold"]["response_mode"] for sid, s in samples.items()})
                             for mode, rows in run["samples"].items() if rows}

    tested = [t for t in tests if t.get("pair_count", 0) >= 2]
    adjusted = holm_adjust([t["paired_sign_flip_p"] for t in tested]) if tested else []
    for test, value in zip(tested, adjusted):
        test["holm_adjusted_p"] = value
        better = (test["mean_difference"] > 0) if test["direction"] == "higher" else (test["mean_difference"] < 0)
        test["verdict"] = ("支持假设" if better and value < 0.05 else
                           "方向相反" if not better and value < 0.05 else "未检出差异")

    print(f"主检验族：{len(tested)} 项（3 个假设 × {len(runs)} 档模型），Holm 校正")
    print(f"{'假设':4s}{'模型':10s}{'对照':30s}{'指标':16s}{'n':>4s}{'左':>8s}{'右':>8s}{'差值':>8s}{'胜/负':>8s}{'p':>8s}{'校正后':>8s}  判定")
    for test in tested:
        print(f"{test['hypothesis']:4s}{test['model']:10s}"
              f"{test['left'] + '→' + test['right']:30s}{test['metric']:16s}"
              f"{test['pair_count']:>4d}{test['left_mean']:>8.3f}{test['right_mean']:>8.3f}"
              f"{test['mean_difference']:>+8.3f}{str(test['wins']) + '/' + str(test['losses']):>8s}"
              f"{test['paired_sign_flip_p']:>8.4f}{test['holm_adjusted_p']:>8.4f}  {test['verdict']}")
    for test in tests:
        if test.get("pair_count", 0) < 2:
            print(f"{test['hypothesis']:4s}{test['model']:10s}{test['metric']:16s} 未检验：{test.get('missing')}")

    print(f"\n次要指标（不参与显著性判定，用于解释）：")
    print(f"{'假设':4s}{'模型':10s}{'指标':18s}{'n':>4s}{'左':>8s}{'右':>8s}{'差值':>8s}{'胜/负':>8s}{'p(参考)':>9s}")
    for row in secondary:
        if row.get("pair_count", 0) < 2:
            continue
        print(f"{row['hypothesis']:4s}{row['model']:10s}{row['metric']:18s}{row['pair_count']:>4d}"
              f"{row['left_mean']:>8.3f}{row['right_mean']:>8.3f}{row['mean_difference']:>+8.3f}"
              f"{str(row['wins']) + '/' + str(row['losses']):>8s}{row['paired_sign_flip_p']:>9.4f}")

    print(f"\n应答方式（各配置，描述性）：")
    print(f"{'模型':10s}{'配置':18s}{'准确率':>8s}{'宏F1':>8s}{'拒答P':>8s}{'拒答R':>8s}{'过度追问':>10s}")
    for name, table in interaction.items():
        for mode, m in table.items():
            print(f"{name:10s}{mode:18s}{m['mode_accuracy']:>8.3f}{m['mode_macro_f1']:>8.3f}"
                  f"{m['abstain_precision']:>8.3f}{m['abstain_recall']:>8.3f}{m['over_clarification']:>10.3f}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"primary": tests, "secondary": secondary,
                                           "interaction": interaction}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
