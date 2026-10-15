"""Build two human-reviewable sheets out of the annotation outputs.

The existing sheets put three long answers side by side, which makes them hard to
read. These split the work into one decision per row and phrase the question in
plain language, so a reviewer can go through them without reading the codebase.

Usage:
    python scripts/build_review_sheets.py

Outputs (empty judgement columns to be filled in):
    data/evaluation/task-completion-review.csv   one row per (sample, configuration)
    data/evaluation/judge-calibration-review.csv one row per judge-flagged claim
Then fill the columns and run scripts/apply_review_sheets.py.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.research_data import ResearchRepository

CONFIGS = ('baseline_c', 'ablation_no_flow', 'method_v2')
CONFIG_LABEL = {
    'baseline_c': '基线C（只作答，不追问不拒答）',
    'ablation_no_flow': '对照：有追问拒答、不用流程骨架',
    'method_v2': '本项目方法（用流程骨架决定追问/拒答）',
}
TC_OUT = ROOT / 'data/evaluation/task-completion-review.csv'
JC_OUT = ROOT / 'data/evaluation/judge-calibration-review.csv'


def question_of(sample: dict) -> str:
    return ' / '.join(t['text'] for t in sample['conversation'] if t['role'] == 'user')


def main() -> int:
    repository = ResearchRepository(ROOT)
    results = json.loads(
        (ROOT / 'data/experiments/baselines-final.json').read_text(encoding='utf-8'))
    samples = {row['sample_id']: row for row in
               (json.loads(line) for line in
                (ROOT / 'data/evaluation/stage2_samples.jsonl')
                .read_text(encoding='utf-8').splitlines() if line)}

    # ------------------------------------------------ sheet 1: task completion
    with (ROOT / 'data/evaluation/task-completion-sheet.csv').open(
            encoding='utf-8-sig', newline='') as handle:
        selected = [row['样本号'] for row in csv.DictReader(handle)]
    answers = {config: {r['sample_id']: r for r in results['samples'][config]}
               for config in CONFIGS}

    with TC_OUT.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['题号', '学生问的是什么', '回答者', '这一份回答',
                         '照着这份回答，下一步能直接办吗？（填：能 / 勉强 / 不能）', '备注'])
        for index, sample_id in enumerate(selected, 1):
            sample = samples[sample_id]
            for config in CONFIGS:
                writer.writerow([
                    index,
                    question_of(sample),
                    CONFIG_LABEL[config],
                    answers[config][sample_id]['prediction']['answer_text'],
                    '', '',
                ])

    # ------------------------------------------------ sheet 2: judge calibration
    payload = json.loads(
        (ROOT / 'data/experiments/judge-calibration.json').read_text(encoding='utf-8'))
    with JC_OUT.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['序号', '场景', '判官说这句话没有依据', '当时手上能用的材料（原文要点）',
                         '这句话有依据吗？（填：支持 / 部分 / 不支持）', '备注'])
        index = 0
        for row in payload['rows']:
            evidence = '；'.join(
                f"[{eid}] {(repository.evidence[eid].get('normalized_claim') or '')}"
                for eid in row['evidence_ids'] if eid in repository.evidence)
            for item in row['judge_items']:
                if item.get('verdict') != 'unsupported':
                    continue
                index += 1
                writer.writerow([index, row['scenario_type'], item.get('claim', ''),
                                 evidence, '', ''])

    print(f'任务完成率复核表：{len(selected) * len(CONFIGS)} 行 -> {TC_OUT.name}')
    print(f'判官校准复核表：  {index} 行 -> {JC_OUT.name}')
    print('两份表都只留了待填列，填完运行 scripts/apply_review_sheets.py 汇总。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
