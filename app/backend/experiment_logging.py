"""Serialize reproducible Stage 3 experiment metadata and result summaries."""
from __future__ import annotations

from datetime import datetime, timezone


def build_experiment_record(config_id: str, input_kind: str, query: str,
                            results: dict, model: str | None = None) -> dict:
    return {
        'config_id': config_id,
        'input_kind': input_kind,
        'query': query,
        'model': model,
        'formal_evaluation_enabled': False,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'results': {name: {'hit_count': len(result.get('hits', [])),
                           'validation_error_count': len(result.get('validation_errors', []))}
                    for name, result in results.items()},
    }
