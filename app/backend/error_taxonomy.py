"""Stable error categories for Stage 3 development evaluation."""
from __future__ import annotations


ERROR_CODES = {
    'object_mismatch', 'version_conflict', 'step_error', 'material_confusion',
    'unsupported_claim', 'retrieval_miss', 'process_binding_error', 'none'
}


def classify_error(scenario_type: str | None, validation_errors: list[dict], hit_count: int) -> str:
    if validation_errors:
        codes = {error.get('code') for error in validation_errors}
        if codes & {'citation_outside_candidates', 'citation_binding_mismatch', 'unknown_claim'}:
            return 'unsupported_claim'
        return 'process_binding_error'
    if not hit_count:
        return 'retrieval_miss'
    if scenario_type in ERROR_CODES:
        return scenario_type
    return 'none'
