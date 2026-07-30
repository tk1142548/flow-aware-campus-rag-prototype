from __future__ import annotations

import copy
import unittest
from html.parser import HTMLParser

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

STAGE_1D_MIGRATIONS = {
    "UGP001": ["UGP001", "UGP012", "UGP013"],
    "UGP002": ["UGP002", "UGP014", "UGP015", "UGP016", "UGP017"],
    "UGP003": ["UGP003", "UGP018"],
    "UGP004": [
        "UGP004",
        "UGP019",
        "UGP020",
        "UGP021",
        "UGP022",
        "UGP023",
        "UGP024",
        "UGP025",
        "UGP026",
        "UGP027",
        "UGP028",
    ],
    "UGP005": ["UGP005", "UGP029", "UGP030", "UGP031", "UGP032"],
    "UGP006": ["UGP006", "UGP033", "UGP034", "UGP035", "UGP036"],
    "UGP007": [
        "UGP007",
        "UGP037",
        "UGP038",
        "UGP039",
        "UGP040",
        "UGP041",
        "UGP042",
        "UGP043",
        "UGP044",
        "UGP045",
    ],
    "UGP008": ["UGP008", "UGP046", "UGP047", "UGP048", "UGP049", "UGP050"],
    "UGP009": [
        "UGP009",
        "UGP051",
        "UGP052",
        "UGP053",
        "UGP054",
        "UGP055",
        "UGP056",
        "UGP057",
        "UGP058",
    ],
}

STAGE_1D_DYNAMIC_IDS = {
    "UGP009",
    "UGP012",
    "UGP014",
    "UGP017",
    "UGP029",
    "UGP032",
    "UGP033",
    "UGP035",
    "UGP036",
    "UGP037",
    "UGP040",
    "UGP046",
    "UGP047",
    "UGP048",
    "UGP049",
    "UGP050",
    "UGP051",
    "UGP052",
    "UGP053",
    "UGP054",
    "UGP055",
    "UGP056",
    "UGP057",
    "UGP058",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def normalized_html_text(text: str) -> str:
    parser = _TextExtractor()
    parser.feed(text)
    return " ".join(" ".join(parser.parts).replace("\xa0", " ").split())


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
        self.assertEqual(19, summary["migrated_legacy_rows"])
        self.assertEqual(11, summary["legacy_unmigrated_rows"])

    def test_stage_1c_migrations_are_verified_and_atomized(self) -> None:
        expected_mismatches = {
            "UGP002",
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

    def test_stage_1d_html_migrations_are_verified_and_atomized(self) -> None:
        _, evidence_audit = load_csv(ROOT / "data/audit/evidence-audit.csv")
        _, source_audit = load_csv(ROOT / "data/audit/source-audit.csv")
        source_records = load_jsonl(ROOT / "data/research/source_records.jsonl")
        target_evidence = load_jsonl(ROOT / TARGET_EVIDENCE_RECORDS_PATH)
        audit_by_id = {row["evidence_id"]: row for row in evidence_audit}
        source_audit_by_id = {row["source_id"]: row for row in source_audit}
        source_by_id = {row["source_id"]: row for row in source_records}
        target_by_id = {row["evidence_id"]: row for row in target_evidence}
        page_text = normalized_html_text(
            (
                ROOT / "data/sources/SRC_UG_PRINT_20210317/page.html"
            ).read_text(encoding="utf-8")
        )

        mapped_target_ids: list[str] = []
        for legacy_id, expected_target_ids in STAGE_1D_MIGRATIONS.items():
            audit = audit_by_id[legacy_id]
            actual_target_ids = audit["target_evidence_ids"].split("|")
            self.assertEqual(expected_target_ids, actual_target_ids)
            self.assertEqual("verified", audit["verbatim_text_status"])
            self.assertEqual("verified", audit["review_status"])
            self.assertEqual("migrated", audit["migration_status"])

            for target_id in actual_target_ids:
                target = target_by_id[target_id]
                self.assertEqual("SRC_UG_PRINT_20210317", target["source_id"])
                self.assertEqual("verified", target["review"]["status"])
                self.assertIn(
                    target["source_locator"]["anchor_text"],
                    target["verbatim_text"],
                )
                normalized_anchor = " ".join(
                    target["source_locator"]["anchor_text"]
                    .replace("\xa0", " ")
                    .split()
                )
                self.assertIn(normalized_anchor, page_text)
            mapped_target_ids.extend(actual_target_ids)

        self.assertEqual(56, len(mapped_target_ids))
        self.assertEqual(len(mapped_target_ids), len(set(mapped_target_ids)))
        actual_dynamic_ids = {
            target_id
            for target_id in mapped_target_ids
            if target_by_id[target_id]["claim_type"]
            in {"service_location", "fee", "contact"}
        }
        self.assertEqual(STAGE_1D_DYNAMIC_IDS, actual_dynamic_ids)
        for target_id in STAGE_1D_DYNAMIC_IDS:
            target = target_by_id[target_id]
            self.assertIsNone(target["applicability"]["effective_from"])
            self.assertIsNone(target["applicability"]["effective_to"])
            self.assertEqual(
                "页面更新于 2023-01-19；2026-07-17 快照",
                target["applicability"]["term_label"],
            )

        print_source_audit = source_audit_by_id["SRC_UG_PRINT_20210317"]
        self.assertEqual("complete", print_source_audit["locator_status"])
        self.assertEqual("verified", print_source_audit["content_review_status"])
        self.assertEqual("verified", print_source_audit["review_status"])
        print_source = source_by_id["SRC_UG_PRINT_20210317"]
        self.assertEqual("verified", print_source["review"]["status"])
        self.assertIsNotNone(print_source["review"]["reviewed_at"])
        self.assertIsNotNone(print_source["review"]["reviewer"])

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
        self.assertEqual(5, summary["verified_source_records"])
        self.assertEqual(89, summary["target_evidence_units"])
        self.assertEqual(89, summary["verified_target_evidence_units"])


if __name__ == "__main__":
    unittest.main()
