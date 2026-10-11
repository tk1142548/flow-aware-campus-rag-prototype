"""Build a citation-complete answer context from process-constrained retrieval."""
from __future__ import annotations


def build_answer_context(process: dict, claims: list[dict], flow_context: dict) -> dict:
    claim_map = {claim['claim_id']: claim for claim in claims}
    allowed_claim_ids = set(flow_context['claim_ids'])
    selected_claims = [claim_map[identity] for identity in flow_context['claim_ids'] if identity in claim_map]
    evidence_ids = sorted({evidence for claim in selected_claims for evidence in claim['evidence_ids']})
    return {
        'process_id': process['process_id'],
        'claims': [{'claim_id': claim['claim_id'], 'text': claim['text'], 'evidence_ids': claim['evidence_ids']}
                   for claim in selected_claims if claim['claim_id'] in allowed_claim_ids],
        'step_ids': flow_context['step_ids'],
        'material_ids': flow_context['material_ids'],
        'evidence_ids': evidence_ids,
        'answer_boundary': '仅生成上述声明、步骤和材料；每条声明必须保留对应证据编号。',
    }
