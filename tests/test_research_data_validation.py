"""Contract tests for the research data validators.

Only stable, behaviour-level contracts live here. Data census numbers
(how many sources/evidence/processes exist today) are deliberately NOT
asserted: the repository is expected to grow, and freezing those counts
turns every legitimate data addition into a test failure.
"""
from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.validate_process_records import validate_process_records
from scripts.validate_research_data import (
    ROOT,
    TARGET_EVIDENCE_RECORDS_PATH,
    duplicate_values,
    load_json,
    load_jsonl,
    validate_schemas_and_fixtures,
    validate_stage2_fixture_links,
    validate_target_links,
    validate_target_repository,
)


class ResearchDataValidationTests(unittest.TestCase):
    def test_declared_fixtures_are_all_handled(self) -> None:
        """Every fixture file on disk must be exercised by the validator."""
        errors, summary = validate_schemas_and_fixtures(ROOT)

        self.assertEqual([], errors)
        valid_on_disk = len(list((ROOT / "tests/fixtures/data/valid").glob("*.json")))
        invalid_on_disk = len(list((ROOT / "tests/fixtures/data/invalid").glob("*.json")))
        self.assertGreaterEqual(summary["valid_fixtures_accepted"], valid_on_disk)
        self.assertGreaterEqual(summary["invalid_fixtures_rejected"], invalid_on_disk - 1)
        self.assertGreaterEqual(summary["invalid_link_fixtures_rejected"], 0)

    def test_process_record_validator_accepts_repository_data(self) -> None:
        errors, counts = validate_process_records(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(0, counts["errors"])
        self.assertGreater(counts["valid_records"], 0)

    def test_duplicate_values_are_reported_deterministically(self) -> None:
        self.assertEqual(["A", "B"], duplicate_values(["B", "A", "B", "C", "A"]))

    def test_stage2_fixture_links_reject_cross_field_inconsistency(self) -> None:
        process = load_json(ROOT / "tests/fixtures/data/valid/process-record.json")
        sample = load_json(ROOT / "tests/fixtures/data/valid/evaluation-sample.json")
        review = load_json(ROOT / "tests/fixtures/data/valid/evaluation-review-record.json")
        evidence = load_jsonl(ROOT / TARGET_EVIDENCE_RECORDS_PATH)

        process["evidence_snapshot"]["evidence_ids"].remove("UGP014")
        sample["gold"]["allowed_claim_ids"].append("CLM_999")
        review["secondary_review"]["reviewer"] = review["primary_annotation"]["reviewer"]

        errors = validate_stage2_fixture_links(process, sample, review, evidence)

        self.assertTrue(any("evidence_snapshot must exactly equal" in error for error in errors))
        self.assertTrue(any("gold.allowed_claim_ids" in error for error in errors))
        self.assertTrue(any("primary and secondary reviewers must differ" in error for error in errors))

    def test_target_links_reject_unknown_source_relations(self) -> None:
        source = load_json(ROOT / "tests/fixtures/data/valid/source-record.json")
        related = copy.deepcopy(source)
        related["relations"] = [
            {"relation_type": "links_to", "target_source_id": "SRC_DOES_NOT_EXIST"}
        ]
        related["version"]["supersedes"] = ["SRC_MISSING_VERSION"]

        errors = validate_target_links([related], [])

        self.assertTrue(any("relation references unknown" in error for error in errors))
        self.assertTrue(any("version.supersedes" in error for error in errors))

    def test_target_links_require_reciprocal_attachment_relations(self) -> None:
        landing = load_json(ROOT / "tests/fixtures/data/valid/source-record.json")
        landing["source_id"] = "SRC_LANDING"
        landing["relations"] = [
            {"relation_type": "landing_page_for", "target_source_id": "SRC_ATTACHMENT"}
        ]
        attachment = copy.deepcopy(landing)
        attachment["source_id"] = "SRC_ATTACHMENT"
        attachment["relations"] = []

        errors = validate_target_links([landing, attachment], [])

        self.assertTrue(any("missing reciprocal attachment_of" in error for error in errors))

    def test_repository_target_data_is_internally_consistent(self) -> None:
        """All evidence must be verified and locatable to a captured source."""
        errors, summary = validate_target_repository(ROOT)

        self.assertEqual([], errors)
        self.assertGreater(summary["target_source_records"], 0)
        self.assertGreater(summary["captured_source_files"], 0)
        self.assertEqual(
            summary["target_evidence_units"],
            summary["verified_target_evidence_units"],
        )
        self.assertEqual(
            summary["target_evidence_units"],
            summary["source_located_evidence_units"],
        )
        self.assertLessEqual(
            summary["verified_source_records"],
            summary["target_source_records"],
        )


if __name__ == "__main__":
    unittest.main()
