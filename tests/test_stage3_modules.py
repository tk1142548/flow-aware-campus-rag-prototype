import json
import tempfile
import unittest
from pathlib import Path

from app.backend.research_data import ResearchRepository, read_records
from app.backend.sparse_retrieval import SparseRetriever
from app.backend.stage3_engine import Stage3Engine


class Stage3ModuleTests(unittest.TestCase):
    def test_duplicate_records_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text('{"id":"X"}\n{"id":"X"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                read_records(path, "id")

    def repository(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        directory = root / "data/research"
        directory.mkdir(parents=True)
        rows = {
            "source_records.jsonl": [{"source_id": "SRC_X", "capture": {"status": "captured"}, "review": {"status": "verified"}}],
            "evidence_units.jsonl": [{"evidence_id": "E001", "item_id": "ITEM", "source_id": "SRC_X", "review": {"status": "verified"}}],
            "process_records.jsonl": [{"process_id": "P", "item_id": "ITEM", "evidence_snapshot": {"evidence_ids": ["E001"]}, "allowed_claims": [{"claim_id": "C", "evidence_ids": ["E001"]}]}],
        }
        for name, records in rows.items():
            (directory / name).write_text("".join(json.dumps(r)+"\n" for r in records), encoding="utf-8")
        return ResearchRepository(root)

    def test_claim_requires_retrieved_evidence(self):
        repo = self.repository()
        self.assertEqual([], repo.supported_claims("P", set()))
        self.assertEqual(["C"], [r["claim_id"] for r in repo.supported_claims("P", {"E001"})])

    def test_unverified_source_and_version_filter(self):
        repo = self.repository()
        self.assertEqual([], repo.verified_evidence("ITEM", {"SRC_OTHER"}))
        repo.sources["SRC_X"]["review"]["status"] = "in_review"
        self.assertEqual([], repo.verified_evidence("ITEM"))
        self.assertEqual([], repo.supported_claims("P", {"E001"}))

    def test_retrieval_empty_and_unmatched_query(self):
        self.assertEqual([], SparseRetriever([]).search("照片"))
        row = {"evidence_id": "E001", "normalized_claim": "照片材料", "verbatim_text": "照片材料", "keywords": []}
        self.assertEqual([], SparseRetriever([row]).search("zzzz"))

    def test_retrieval_is_order_independent(self):
        rows = [{"evidence_id": identity, "normalized_claim": "照片材料", "verbatim_text": "照片材料", "keywords": []} for identity in ["E002", "E001"]]
        hits = SparseRetriever(rows).search("照片")
        self.assertEqual(hits, SparseRetriever(list(reversed(rows))).search("照片"))
        self.assertEqual(["E001", "E002"], [row["evidence_id"] for row, _ in hits])

    def test_engine_returns_process_local_claims(self):
        root = Path(__file__).resolve().parents[1]
        result = Stage3Engine(root).query(
            "UG_CREDENTIAL_REISSUE", "学位证明书照片材料",
            {"SRC_UG_CREDENTIAL_DEGREE_20210317"},
            "PROC_UG_CREDENTIAL_DEGREE_V001", 5)
        self.assertTrue(result["hits"])
        hit_ids = {hit["evidence"]["evidence_id"] for hit in result["hits"]}
        self.assertTrue(all(set(c["evidence_ids"]) <= hit_ids for c in result["supported_claims"]))


if __name__ == "__main__":
    unittest.main()
