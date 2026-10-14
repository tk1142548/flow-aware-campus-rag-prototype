import json
import tempfile
import unittest
from pathlib import Path

from app.backend.research_data import ResearchRepository, read_records
from app.backend.sparse_retrieval import SparseRetriever


class ResearchDataAndRetrievalTests(unittest.TestCase):
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
            "process_records.jsonl": [{"process_id": "P", "item_id": "ITEM", "evidence_snapshot": {"evidence_ids": ["E001"]}}],
        }
        for name, records in rows.items():
            (directory / name).write_text("".join(json.dumps(r)+"\n" for r in records), encoding="utf-8")
        return ResearchRepository(root)

    def test_unverified_source_is_excluded_from_the_pool(self):
        repo = self.repository()
        self.assertEqual(["E001"], [r["evidence_id"] for r in repo.all_verified_evidence()])
        self.assertEqual([], repo.verified_evidence("ITEM", {"SRC_OTHER"}))

        repo.sources["SRC_X"]["review"]["status"] = "in_review"

        self.assertEqual([], repo.verified_evidence("ITEM"))
        self.assertEqual([], repo.all_verified_evidence())

    def test_retrieval_empty_and_unmatched_query(self):
        self.assertEqual([], SparseRetriever([]).search("照片"))
        row = {"evidence_id": "E001", "normalized_claim": "照片材料", "verbatim_text": "照片材料", "keywords": []}
        self.assertEqual([], SparseRetriever([row]).search("zzzz"))

    def test_retrieval_is_order_independent(self):
        rows = [{"evidence_id": identity, "normalized_claim": "照片材料", "verbatim_text": "照片材料", "keywords": []} for identity in ["E002", "E001"]]
        hits = SparseRetriever(rows).search("照片")
        self.assertEqual(hits, SparseRetriever(list(reversed(rows))).search("照片"))
        self.assertEqual(["E001", "E002"], [row["evidence_id"] for row, _ in hits])


if __name__ == "__main__":
    unittest.main()
