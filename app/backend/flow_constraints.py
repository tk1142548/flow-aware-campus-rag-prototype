"""Derive process steps and materials whose supporting evidence was retrieved."""
from __future__ import annotations


def supported_process_context(process: dict, retrieved_ids: set[str]) -> dict:
    snapshot = set(process['evidence_snapshot']['evidence_ids'])
    usable = retrieved_ids & snapshot
    claims = [claim for claim in process['allowed_claims']
              if set(claim['evidence_ids']) <= usable]
    claim_ids = {claim['claim_id'] for claim in claims}
    claim_evidence = {e for claim in claims for e in claim['evidence_ids']}
    steps = [step for step in process.get('steps', [])
             if set(step.get('evidence_ids', [])) <= claim_evidence]
    materials = [material for material in process.get('materials', [])
                 if set(material.get('evidence_ids', [])) <= claim_evidence]
    return {'process_id': process['process_id'], 'claim_ids': sorted(claim_ids),
            'step_ids': [step['step_id'] for step in steps],
            'material_ids': [material['material_id'] for material in materials],
            'evidence_ids': sorted(claim_evidence)}
