"""Per-hypothesis analysis of a run file produced by run_baselines.py.

Reads only stored records; no model is called. For each hypothesis contrast it
reports the dedicated metric with a paired sign-flip test:

    H1  full_no_skeleton -> full   step recall, step order, material recall
                                   on samples whose gold has >= 3 steps
    H3  baseline_c -> interaction  response-mode correctness; macro F1 and the
                                   confusion table per configuration
    H2  needs judge output and is reported by judge_assertions.py

Usage:
    python scripts/analyze_hypotheses.py data/experiments/dev-run-qwen-plus.json \
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
from app.backend.stage4_statistics import paired_analysis

FLOW_METRICS = ("step_recall", "step_order", "material_recall")


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
    return stat


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    run = json.loads(args.run.read_text(encoding="utf-8"))
    samples = {s["sample_id"]: s for s in
               (json.loads(line) for line in args.samples.read_text(encoding="utf-8").splitlines()
                if line)}
    gold_modes = {sid: s["gold"]["response_mode"] for sid, s in samples.items()}
    items = {sid: s["allocation_item_id"] or "OUT_OF_SCOPE" for sid, s in samples.items()}
    multi_step = {sid for sid, s in samples.items()
                  if len(s["gold"]["ordered_step_ids"]) >= MULTI_STEP}

    scores = {mode: [{"sample_id": r["sample_id"], **per_sample_scores(r, gold_modes[r["sample_id"]])}
                     for r in rows]
              for mode, rows in run["samples"].items()}

    report = {"run": args.run.as_posix(), "generation_model": run.get("generation_model"),
              "multi_step_samples": len(multi_step), "interaction": {}, "contrasts": []}
    for mode, rows in run["samples"].items():
        if rows:
            report["interaction"][mode] = interaction_metrics(rows, gold_modes)

    if scores.get("baseline_c") and scores.get("interaction"):
        report["contrasts"].append({"hypothesis": "H3", "left": "baseline_c", "right": "interaction",
                                    "metric": "mode_correct",
                                    **paired(scores["baseline_c"], scores["interaction"],
                                             "mode_correct", lambda sid: True, items)})
    if scores.get("full_no_skeleton") and scores.get("full"):
        for metric in FLOW_METRICS:
            report["contrasts"].append({"hypothesis": "H1", "left": "full_no_skeleton",
                                        "right": "full", "metric": metric,
                                        **paired(scores["full_no_skeleton"], scores["full"], metric,
                                                 lambda sid: sid in multi_step, items)})

    print(f"model: {report['generation_model']}   multi-step samples: {len(multi_step)}")
    print(f"\n{'config':18s}{'mode acc':>10s}{'macro F1':>10s}{'abst P':>8s}{'abst R':>8s}{'over-ask':>10s}")
    for mode, m in report["interaction"].items():
        print(f"{mode:18s}{m['mode_accuracy']:>10.3f}{m['mode_macro_f1']:>10.3f}"
              f"{m['abstain_precision']:>8.3f}{m['abstain_recall']:>8.3f}{m['over_clarification']:>10.3f}")
    print(f"\n{'hyp':4s}{'contrast':34s}{'metric':16s}{'n':>4s}{'left':>8s}{'right':>8s}{'W/L':>8s}{'p':>8s}")
    for c in report["contrasts"]:
        if "mean_difference" not in c:
            print(f"{c['hypothesis']:4s}{c['left'] + ' -> ' + c['right']:34s}{c['metric']:16s}{c['pair_count']:>4d}")
            continue
        print(f"{c['hypothesis']:4s}{c['left'] + ' -> ' + c['right']:34s}{c['metric']:16s}"
              f"{c['pair_count']:>4d}{c['left_mean']:>8.3f}{c['right_mean']:>8.3f}"
              f"{str(c['wins']) + '/' + str(c['losses']):>8s}{c['paired_sign_flip_p']:>8.4f}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
