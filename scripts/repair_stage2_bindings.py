"""Rebuild evidence references from existing claims; invalidate review gates."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def repair_sample(sample: dict, processes: dict) -> dict:
    result = copy.deepcopy(sample)
    if sample['process_id'] is not None:
        process = processes[sample['process_id']]
        if process['item_id'] != sample['item_id']:
            raise ValueError('process item mismatch')
        claims = {c['claim_id']: c for c in process['allowed_claims']}
        bound = sorted({e for identity in sample['gold']['allowed_claim_ids']
                        for e in claims[identity]['evidence_ids']})
        if not set(bound) <= set(process['evidence_snapshot']['evidence_ids']):
            raise ValueError('claim evidence outside process snapshot')
        result['gold']['supporting_evidence_ids'] = bound
    result['review_status'] = 'draft'
    result['leakage_control'].update(check_status='pending', checked_at=None,
                                     checker=None, notes='待场景重建与重新复核。')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'data/evaluation/stage2_samples.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    processes = {p['process_id']: p for p in map(json.loads, (ROOT / 'data/research/process_records.jsonl').read_text(encoding='utf-8').splitlines())}
    repaired = [repair_sample(row, processes) for row in rows]
    changes = [{'sample_id': a['sample_id'], 'process_id': a['process_id'],
                'allowed_claim_ids': a['gold']['allowed_claim_ids'],
                'old_evidence_ids': a['gold']['supporting_evidence_ids'],
                'new_evidence_ids': b['gold']['supporting_evidence_ids']}
               for a, b in zip(rows, repaired)
               if set(a['gold']['supporting_evidence_ids']) != set(b['gold']['supporting_evidence_ids'])]
    if args.apply:
        report_path = ROOT / 'data/audit/stage2-binding-repairs.json'
        if report_path.exists():
            raise ValueError('repair ledger already exists; preserve previous audit')
        report_path.write_text(json.dumps({'status': '已完成待验证', 'basis': '流程允许声明的证据集合',
            'changed_sample_count': len(changes), 'review_reset_count': len(rows), 'changes': changes}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temp = path.with_suffix('.jsonl.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n' for row in repaired), encoding='utf-8')
        temp.replace(path)
    print(json.dumps({'changed_sample_count': len(changes), 'review_reset_count': len(rows), 'applied': args.apply}))


if __name__ == '__main__':
    main()
