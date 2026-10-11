"""Build a traceable manual review checklist without asserting review completion."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    samples = [json.loads(line) for line in (ROOT / 'data/evaluation/stage2_samples.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    processes = {json.loads(line)['process_id']: json.loads(line) for line in (ROOT / 'data/research/process_records.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()}
    checklist = []
    for sample in samples:
        process = processes.get(sample['process_id']) if sample['process_id'] else None
        checklist.append({
            'sample_id': sample['sample_id'], 'review_status': 'pending',
            'review_dimensions': ['item_mapping', 'slot_and_follow_up', 'process_structure',
                                  'claim_and_evidence', 'version_applicability', 'leakage_control'],
            'process_id': sample['process_id'],
            'process_verified': bool(process and process['review']['status'] == 'verified'),
            'claim_ids': sample['gold']['allowed_claim_ids'],
            'evidence_ids': sample['gold']['supporting_evidence_ids'],
            'conversation_turn_count': len(sample['conversation']),
            'decision': None, 'reviewer': None, 'notes': None,
        })
    out = ROOT / 'data/audit/stage2-independent-review-checklist.jsonl'
    out.write_text(''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n' for row in checklist), encoding='utf-8')
    print(json.dumps({'sample_count': len(checklist), 'status': 'pending'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
