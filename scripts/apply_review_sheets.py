"""Merge the filled review sheets back into the canonical annotation files.

Reads the two review sheets produced by build_review_sheets.py, writes the verdicts
back into task-completion-sheet.csv / judge-calibration.csv, then recomputes the
summaries in data/experiments/task-completion.json and judge-calibration.json.

Usage:
    python scripts/apply_review_sheets.py [--check]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.stage4_statistics import holm_adjust, paired_analysis

CONFIGS = ('baseline_c', 'ablation_no_flow', 'method_v2')
CONFIG_LABEL = {
    'baseline_c': '基线C（只作答，不追问不拒答）',
    'ablation_no_flow': '对照：有追问拒答、不用流程骨架',
    'method_v2': '本项目方法（用流程骨架决定追问/拒答）',
}
TC_REVIEW = ROOT / 'data/evaluation/task-completion-review.csv'
JC_REVIEW = ROOT / 'data/evaluation/judge-calibration-review.csv'
TC_SHEET = ROOT / 'data/evaluation/task-completion-sheet.csv'
JC_SHEET = ROOT / 'data/experiments/judge-calibration.csv'
TC_JSON = ROOT / 'data/experiments/task-completion.json'

TC_COL = '照着这份回答，下一步能直接办吗？（填：能 / 勉强 / 不能）'
TC_SCALE = {'能': 1.0, '勉强': 0.5, '不能': 0.0}
SHEET_SCALE = {'完成': 1.0, '部分': 0.5, '未完成': 0.0}
TC_TO_SHEET = {'能': '完成', '勉强': '部分', '不能': '未完成'}
SHEET_COL = '{config} 是否足以支撑下一步（完成/未完成/部分）'
JC_COL = '这句话有依据吗？（填：支持 / 部分 / 不支持）'


def sheet_column(config: str) -> str:
    return SHEET_COL.format(config=config)


def load(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='只报告填写进度，不写回')
    args = parser.parse_args()

    # ------------------------------------------------------ task completion
    review_rows = load(TC_REVIEW)
    collected: dict[tuple[int, str], str] = {}
    for row in review_rows:
        verdict = (row.get(TC_COL) or '').strip()
        if verdict in TC_SCALE:
            collected[(int(row['题号']), row['回答者'])] = TC_TO_SHEET[verdict]
    missing = len(review_rows) - len(collected)

    print(f'任务完成率复核表：{len(review_rows)} 行，已填 {len(collected)}，未填 {missing}')
    if args.check:
        return 0

    sheet = load(TC_SHEET)
    for position, row in enumerate(sheet, 1):
        for config in CONFIGS:
            verdict = collected.get((position, CONFIG_LABEL[config]))
            if verdict:
                row[sheet_column(config)] = verdict
    with TC_SHEET.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sheet[0].keys()))
        writer.writeheader()
        writer.writerows(sheet)

    summary = {}
    for config in CONFIGS:
        column = sheet_column(config)
        values = [SHEET_SCALE[row[column].strip()] for row in sheet
                  if (row.get(column) or '').strip() in SHEET_SCALE]
        summary[config] = {
            'labelled': len(values),
            'task_completion_rate': sum(values) / len(values) if values else None,
            'distribution': dict(Counter(row[column].strip() for row in sheet
                                         if (row.get(column) or '').strip() in SHEET_SCALE)),
        }

    baseline = CONFIGS[-1]
    comparisons = []
    for config in CONFIGS[:-1]:
        pairs = [(row['样本号'], SHEET_SCALE[row[sheet_column(config)].strip()],
                  SHEET_SCALE[row[sheet_column(baseline)].strip()])
                 for row in sheet
                 if (row.get(sheet_column(config)) or '').strip() in SHEET_SCALE
                 and (row.get(sheet_column(baseline)) or '').strip() in SHEET_SCALE]
        if not pairs:
            continue
        stat = paired_analysis([p[1] for p in pairs], [p[2] for p in pairs],
                               [p[0] for p in pairs], 10000, 0)
        comparisons.append({'left': config, 'right': baseline,
                            'metric': 'task_completion_rate', **stat})
    for comparison, adjusted in zip(comparisons,
                                    holm_adjust([c['paired_sign_flip_p'] for c in comparisons])):
        comparison['holm_adjusted_p'] = adjusted

    TC_JSON.write_text(json.dumps({
        'status': '已汇总',
        'protocol': {'scale': TC_SCALE, 'baseline': baseline},
        'item_count': len(sheet),
        'summary': summary,
        'paired_comparisons': comparisons,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f"{'回答者':<34}{'完成率':>9}{'完成':>5}{'部分':>6}{'未完成':>7}")
    for config, entry in summary.items():
        dist = entry['distribution']
        rate = entry['task_completion_rate']
        print(f"{config:<34}{(f'{rate:.4f}' if rate is not None else 'n/a'):>9}"
              f"{dist.get('完成', 0):>5}{dist.get('部分', 0):>6}{dist.get('未完成', 0):>7}")

    # ------------------------------------------------------ judge calibration
    review = load(JC_REVIEW)
    filled = [r for r in review if (r.get(JC_COL) or '').strip() in {'支持', '部分', '不支持'}]
    print()
    print(f'判官校准复核表：{len(review)} 行，已填 {len(filled)}，未填 {len(review) - len(filled)}')
    if filled:
        counts = Counter(r[JC_COL].strip() for r in filled)
        agree = counts['不支持']
        total = len(filled)
        print(f"  仍判不支持 {agree} / 部分 {counts['部分']} / 判为支持 {counts['支持']}")
        print(f"  完全一致率 {agree / total:.4f}，部分计半一致率 "
              f"{(agree + counts['部分'] * 0.5) / total:.4f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
