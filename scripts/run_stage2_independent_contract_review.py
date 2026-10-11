"""Run an independent deterministic contract review for every stage 2 sample."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def review(sample: dict, processes: dict, evidence: dict) -> dict:
    errors = []
    process = processes.get(sample['process_id']) if sample['process_id'] else None
    if sample['scenario_type'] != 'out_of_scope':
        if process is None or process['item_id'] != sample['item_id'] or process['review']['status'] != 'verified':
            errors.append('process_not_verified')
        else:
            snapshot = set(process['evidence_snapshot']['evidence_ids'])
            claims = {claim['claim_id']: claim for claim in process['allowed_claims']}
            selected = sample['gold']['allowed_claim_ids']
            if any(identity not in claims for identity in selected):
                errors.append('unknown_claim')
            expected = {evidence_id for identity in selected if identity in claims for evidence_id in claims[identity]['evidence_ids']}
            actual = set(sample['gold']['supporting_evidence_ids'])
            if actual != expected:
                errors.append('claim_evidence_mismatch')
            if not actual <= snapshot:
                errors.append('evidence_outside_process')
            if any(identity not in evidence for identity in actual):
                errors.append('evidence_missing')
    return {'sample_id': sample['sample_id'], 'status': 'pass' if not errors else 'fail',
            'dimensions': {'item_mapping': 'pass' if not errors else 'fail',
                           'slot_and_follow_up': 'pending', 'process_structure': 'pass' if not errors else 'fail',
                           'claim_and_evidence': 'pass' if not errors else 'fail',
                           'version_applicability': 'pending', 'leakage_control': 'pass' if sample['leakage_control']['check_status'] == 'passed' else 'fail'},
            'errors': errors, 'reviewer': 'stage2-independent-contract-validator',
            'human_review_required': True}


def main():
    samples = [json.loads(line) for line in (ROOT / 'data/evaluation/stage2_samples.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    processes = {row['process_id']: row for row in (json.loads(line) for line in (ROOT / 'data/research/process_records.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
    evidence = {row['evidence_id']: row for row in (json.loads(line) for line in (ROOT / 'data/research/evidence_units.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
    results = [review(sample, processes, evidence) for sample in samples]
    out = ROOT / 'data/audit/stage2-independent-contract-review.jsonl'
    out.write_text(''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n' for row in results), encoding='utf-8')
    print(json.dumps({'sample_count': len(results), 'pass_count': sum(row['status'] == 'pass' for row in results),
                      'fail_count': sum(row['status'] == 'fail' for row in results), 'human_review_required': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
