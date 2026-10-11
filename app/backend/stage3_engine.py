"""Stage 3 retrieval foundation over the verified research repository."""
from __future__ import annotations

from pathlib import Path

from .research_data import ResearchRepository
from .sparse_retrieval import SparseRetriever
from .claim_validation import validate_claims
from .flow_constraints import supported_process_context


class Stage3Engine:
    """Run deterministic evidence retrieval with process-local claim support."""

    def __init__(self, root: Path):
        self.repository = ResearchRepository(Path(root))

    def query(self, item_id: str, query: str, source_ids: set[str] | None = None,
              process_id: str | None = None, top_k: int = 5) -> dict:
        item_processes = [p for p in self.repository.processes.values() if p["item_id"] == item_id]
        if not item_processes:
            raise ValueError(f"unknown item_id: {item_id}")
        if not query.strip():
            raise ValueError("query must not be empty")
        evidence = self.repository.verified_evidence(item_id, source_ids)
        hits = SparseRetriever(evidence).search(query, top_k)
        hit_rows = [{"evidence": row, "score": round(score, 8)} for row, score in hits]
        claims = []
        flow_context = None
        if process_id is not None:
            process = self.repository.processes.get(process_id)
            if not process or process["item_id"] != item_id:
                raise ValueError(f"process does not belong to item: {process_id}")
            claims = self.repository.supported_claims(
                process_id, {row["evidence"]["evidence_id"] for row in hit_rows}
            )
            errors = validate_claims(process, {row['evidence']['evidence_id'] for row in hit_rows}, claims)
            if errors:
                raise ValueError(f'invalid process claim bindings: {errors}')
            flow_context = supported_process_context(
                process, {row['evidence']['evidence_id'] for row in hit_rows})
        return {"item_id": item_id, "query": query,
                "source_ids": sorted(source_ids) if source_ids else None,
                "hits": hit_rows, "supported_claims": claims,
                "flow_context": flow_context}
