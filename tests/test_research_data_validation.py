from __future__ import annotations

import copy
import unittest

from scripts.validate_research_data import (
    KNOWN_MISMATCH_IDS,
    ROOT,
    duplicate_values,
    load_json,
    validate_repository_audits,
    validate_schemas_and_fixtures,
    validate_target_links,
    validate_target_repository,
)


class ResearchDataValidationTests(unittest.TestCase):
    def test_target_schemas_accept_and_reject_declared_fixtures(self) -> None:
        errors, summary = validate_schemas_and_fixtures(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(2, summary["valid_fixtures_accepted"])
        self.assertEqual(4, summary["invalid_fixtures_rejected"])
        self.assertEqual(1, summary["invalid_link_fixtures_rejected"])

    def test_repository_audits_cover_all_legacy_records(self) -> None:
        errors, summary = validate_repository_audits(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(8, summary["manifest_sources"])
        self.assertEqual(30, summary["legacy_evidence_units"])
        self.assertEqual(8, summary["source_audit_rows"])
        self.assertEqual(30, summary["evidence_audit_rows"])
        self.assertEqual(10, summary["legacy_missing_publish_date"])
        self.assertEqual(len(KNOWN_MISMATCH_IDS), summary["known_mismatch_rows"])
        self.assertEqual(4, summary["migrated_legacy_rows"])
        self.assertEqual(26, summary["legacy_unmigrated_rows"])

    def test_duplicate_values_are_reported_deterministically(self) -> None:
        self.assertEqual(["A", "B"], duplicate_values(["B", "A", "B", "C", "A"]))

    def test_target_links_reject_unknown_source_relations(self) -> None:
        source = load_json(ROOT / "tests/fixtures/data/valid/source-record.json")
        related = copy.deepcopy(source)
        related["relations"] = [
            {
                "relation_type": "links_to",
                "target_source_id": "SRC_DOES_NOT_EXIST",
            }
        ]
        related["version"]["supersedes"] = ["SRC_MISSING_VERSION"]

        errors = validate_target_links([related], [])

        self.assertTrue(any("relation references unknown" in error for error in errors))
        self.assertTrue(any("version.supersedes" in error for error in errors))

    def test_target_links_require_reciprocal_attachment_relations(self) -> None:
        landing = load_json(ROOT / "tests/fixtures/data/valid/source-record.json")
        landing["source_id"] = "SRC_LANDING"
        landing["relations"] = [
            {
                "relation_type": "landing_page_for",
                "target_source_id": "SRC_ATTACHMENT",
            }
        ]
        attachment = copy.deepcopy(landing)
        attachment["source_id"] = "SRC_ATTACHMENT"
        attachment["relations"] = []

        errors = validate_target_links([landing, attachment], [])

        self.assertTrue(
            any("missing reciprocal attachment_of" in error for error in errors)
        )

    def test_repository_target_data_is_schema_valid_and_hash_consistent(self) -> None:
        errors, summary = validate_target_repository(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(5, summary["target_source_records"])
        self.assertEqual(5, summary["captured_source_files"])
        self.assertEqual(4, summary["verified_source_records"])
        self.assertEqual(12, summary["target_evidence_units"])
        self.assertEqual(12, summary["verified_target_evidence_units"])


if __name__ == "__main__":
    unittest.main()
