from __future__ import annotations

import copy
import unittest

from scripts.validate_research_data import (
    KNOWN_MISMATCH_IDS,
    ROOT,
    TARGET_EVIDENCE_RECORDS_PATH,
    duplicate_values,
    load_csv,
    load_json,
    load_jsonl,
    validate_repository_audits,
    validate_schemas_and_fixtures,
    validate_target_links,
    validate_target_repository,
)

STAGE_1C_MIGRATIONS = {
    "UGS001": ["UGS001"],
    "UGS004": [
        "UGS004",
        "UGS028",
        "UGS029",
        "UGS030",
        "UGS031",
        "UGS032",
        "UGS033",
    ],
    "UGS005": ["UGS005", "UGS034", "UGS035"],
    "UGS006": ["UGS006", "UGS036", "UGS037"],
    "UGS011": ["UGS011"],
    "UGS012": ["UGS012", "UGS038", "UGS039", "UGS040", "UGS041", "UGS042"],
}

STAGE_1C_SOURCE_IDS = {
    "UGS001": "SRC_UG_SUSPEND_FORM_PDF_202504",
    "UGS004": "SRC_UG_SUSPEND_FORM_PDF_202504",
    "UGS005": "SRC_UG_SUSPEND_FORM_PDF_202504",
    "UGS006": "SRC_UG_SUSPEND_FORM_PDF_202504",
    "UGS011": "SRC_UG_RESUME_FORM_PDF_202504",
    "UGS012": "SRC_UG_RESUME_FORM_PDF_202504",
}


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
        self.assertEqual(10, summary["migrated_legacy_rows"])
        self.assertEqual(20, summary["legacy_unmigrated_rows"])

    def test_stage_1c_migrations_are_verified_and_atomized(self) -> None:
        expected_mismatches = {
            "UGS002",
            "UGS003",
            "UGS004",
            "UGS012",
            "UGS013",
            "UGS014",
        }
        self.assertEqual(expected_mismatches, KNOWN_MISMATCH_IDS)

        _, evidence_audit = load_csv(ROOT / "data/audit/evidence-audit.csv")
        _, source_audit = load_csv(ROOT / "data/audit/source-audit.csv")
        target_evidence = load_jsonl(ROOT / TARGET_EVIDENCE_RECORDS_PATH)
        audit_by_id = {row["evidence_id"]: row for row in evidence_audit}
        source_audit_by_id = {row["source_id"]: row for row in source_audit}
        target_by_id = {row["evidence_id"]: row for row in target_evidence}

        mapped_target_ids: list[str] = []
        for legacy_id, expected_target_ids in STAGE_1C_MIGRATIONS.items():
            audit = audit_by_id[legacy_id]
            actual_target_ids = audit["target_evidence_ids"].split("|")
            self.assertEqual(expected_target_ids, actual_target_ids)
            self.assertEqual("verified", audit["verbatim_text_status"])
            self.assertEqual("verified", audit["review_status"])
            self.assertEqual("migrated", audit["migration_status"])

            expected_source_id = STAGE_1C_SOURCE_IDS[legacy_id]
            for target_id in actual_target_ids:
                target = target_by_id[target_id]
                self.assertEqual(expected_source_id, target["source_id"])
                self.assertEqual("verified", target["review"]["status"])
                self.assertIn(
                    target["source_locator"]["anchor_text"],
                    target["verbatim_text"],
                )
            mapped_target_ids.extend(actual_target_ids)

        self.assertEqual(len(mapped_target_ids), len(set(mapped_target_ids)))
        for source_id in {
            "SRC_UG_SUSPEND_FORM",
            "SRC_UG_RESUME_FORM",
        }:
            source_audit_row = source_audit_by_id[source_id]
            self.assertEqual("complete", source_audit_row["locator_status"])
            self.assertEqual("verified", source_audit_row["content_review_status"])
            self.assertEqual("verified", source_audit_row["review_status"])

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
        self.assertEqual(33, summary["target_evidence_units"])
        self.assertEqual(33, summary["verified_target_evidence_units"])


if __name__ == "__main__":
    unittest.main()
