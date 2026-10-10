"""Validate structured answer claims against retrieved, process-local evidence."""
from __future__ import annotations


def validate_claims(process: dict, retrieved_ids: set[str], answer_claims: list[dict]) -> list[dict]:
    allowed = {c['claim_id']: c for c in process['allowed_claims']}
    snapshot = set(process['evidence_snapshot']['evidence_ids'])
    errors = []
    seen = set()
    for claim in answer_claims:
        identity = claim.get('claim_id')
        if identity in seen:
            errors.append({'claim_id': identity, 'code': 'duplicate_claim'})
        seen.add(identity)
        expected = allowed.get(identity)
        if expected is None:
            errors.append({'claim_id': identity, 'code': 'unknown_claim'})
            continue
        citations = claim.get('evidence_ids')
        if not isinstance(citations, list) or not citations or not all(isinstance(e, str) for e in citations):
            errors.append({'claim_id': identity, 'code': 'invalid_citations'})
            continue
        cited = set(citations)
        if len(cited) != len(citations) or cited != set(expected['evidence_ids']):
            errors.append({'claim_id': identity, 'code': 'citation_binding_mismatch'})
        if not cited <= retrieved_ids & snapshot:
            errors.append({'claim_id': identity, 'code': 'citation_outside_candidates'})
        if claim.get('text') != expected['text']:
            errors.append({'claim_id': identity, 'code': 'claim_text_mismatch'})
    return errors
