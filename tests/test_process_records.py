from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_process_records import validate_process_records


ROOT = Path(__file__).resolve().parents[1]


class ProcessRecordValidationTests(unittest.TestCase):
    def _fixture_root(self, mutate=None) -> Path:
        temp = Path(tempfile.mkdtemp(prefix="process-records-"))
        (temp / "data/research").mkdir(parents=True)
        (temp / "data/schemas").mkdir(parents=True)
        for relative in (
            "data/schemas/process-record.schema.json",
            "data/schemas/evidence-unit.schema.json",
        ):
            target = temp / relative
            target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")

        process = json.loads(
            (ROOT / "tests/fixtures/data/valid/process-record.json").read_text(encoding="utf-8")
        )
        evidence_rows = [
            json.loads(line)
            for line in (ROOT / "data/research/evidence_units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        evidence_by_id = {row["evidence_id"]: row for row in evidence_rows}
        referenced = set(process["evidence_snapshot"]["evidence_ids"])
        subset = [evidence_by_id[evidence_id] for evidence_id in sorted(referenced)]
        # The repository fixture predates the one-claim/one-evidence rule.
        # Rebuild its claims from the same evidence so this test isolates the
        # generic validator contract.
        process["allowed_claims"] = [
            {
                "claim_id": f"CLM_{index:03d}",
                "claim_type": evidence["claim_type"],
                "text": evidence["normalized_claim"],
                "conditions": [],
                "applicable_step_ids": [],
                "evidence_ids": [evidence["evidence_id"]],
            }
            for index, evidence in enumerate(subset, 1)
        ]
        if mutate is not None:
            mutate(process, subset)
        evidence_path = temp / "data/research/evidence_units.jsonl"
        evidence_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in subset),
            encoding="utf-8",
        )
        process["evidence_snapshot"]["dataset_sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        (temp / "data/research/process_records.jsonl").write_text(
            json.dumps(process, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return temp

    def _run(self, mutate=None):
        root = self._fixture_root(mutate)
        return validate_process_records(root)

    def test_valid_record(self):
        errors, summary = self._run()
        self.assertEqual(errors, [])
        self.assertEqual(summary["records"], 1)
        self.assertEqual(summary["valid_records"], 1)

    def test_schema_error_is_reported(self):
        errors, summary = self._run(lambda process, _: process.__setitem__("process_id", "bad"))
        self.assertTrue(any("schema error" in error for error in errors))
        self.assertGreater(summary["schema_errors"], 0)

    def test_missing_evidence_breaks_exact_snapshot(self):
        def mutate(process, _):
            process["evidence_snapshot"]["evidence_ids"].pop()

        errors, summary = self._run(mutate)
        self.assertTrue(any("snapshot IDs must exactly equal" in error for error in errors))
        self.assertGreater(summary["snapshot_errors"], 0)

    def test_cross_item_evidence_is_rejected(self):
        def mutate(_, evidence):
            evidence[0]["item_id"] = "UG_STATUS_CHANGE"

        errors, summary = self._run(mutate)
        self.assertTrue(any("belongs to item" in error for error in errors))
        self.assertGreater(summary["evidence_errors"], 0)

    def test_condition_must_reference_declared_slot(self):
        def mutate(process, _):
            process["steps"][0]["conditions"][0]["slot_id"] = "SL_DOES_NOT_EXIST"

        errors, summary = self._run(mutate)
        self.assertTrue(any("references missing slot SL_DOES_NOT_EXIST" in error for error in errors))
        self.assertGreater(summary["condition_errors"], 0)

    def test_verified_review_requires_distinct_identities(self):
        def mutate(process, _):
            review = process["review"]
            review.update(
                {
                    "status": "verified",
                    "annotated_at": "2026-09-24T00:00:00+08:00",
                    "annotator": "同一复核者",
                    "reviewed_at": "2026-09-24T00:01:00+08:00",
                    "reviewer": "同一复核者",
                }
            )

        errors, summary = self._run(mutate)
        self.assertTrue(any("different annotator and reviewer" in error for error in errors))
        self.assertGreater(summary["review_errors"], 0)


if __name__ == "__main__":
    unittest.main()

