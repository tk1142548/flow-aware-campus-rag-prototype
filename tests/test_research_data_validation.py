from __future__ import annotations

import copy
import unittest
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlparse

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
    validate_stage2_fixture_links,
    validate_stage2a_contract,
    validate_stage2b_withdrawal_contract,
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

STAGE_1E_MIGRATIONS = {
    "UGP010": [
        "UGP010",
        "UGP059",
        "UGP060",
        "UGP061",
        "UGP062",
        "UGP063",
        "UGP064",
        "UGP065",
        "UGP066",
        "UGP067",
        "UGP068",
        "UGP069",
        "UGP070",
        "UGP071",
        "UGP072",
        "UGP073",
        "UGP074",
        "UGP075",
        "UGP076",
        "UGP077",
    ],
    "UGP011": ["UGP011", "UGP078", "UGP079", "UGP080"],
    "UGS007": ["UGS007", "UGS043"],
    "UGS008": ["UGS008", "UGS044", "UGS045"],
    "UGS009": ["UGS009", "UGS046", "UGS047", "UGS048"],
    "UGS010": ["UGS008", "UGS045", "UGS048"],
    "UGS015": ["UGS015", "UGS049", "UGS050", "UGS051"],
    "UGS016": ["UGS016", "UGS052", "UGS053", "UGS054"],
    "UGS017": ["UGS017", "UGS055", "UGS056"],
    "UGS018": ["UGS051", "UGS052", "UGS055", "UGS056"],
    "UGS019": ["UGS019", "UGS057", "UGS058"],
}

STAGE_1E_SOURCE_IDS = {
    "UGP010": "SRC_UG_GRAD_NOTICE_20250617",
    "UGP011": "SRC_GS_CERT_20130903",
    "UGS007": "SRC_UG_SUSPEND_PROCESS_20190418",
    "UGS008": "SRC_UG_SUSPEND_PROCESS_20190418",
    "UGS009": "SRC_UG_SUSPEND_PROCESS_20190418",
    "UGS010": "SRC_UG_SUSPEND_PROCESS_20190418",
    "UGS015": "SRC_UG_RESUME_PROCESS_20190418",
    "UGS016": "SRC_UG_RESUME_PROCESS_20190418",
    "UGS017": "SRC_UG_RESUME_PROCESS_20190418",
    "UGS018": "SRC_UG_RESUME_PROCESS_20190418",
    "UGS019": "SRC_UG_UNREGISTERED_20250321",
}

STAGE_1_SOURCE_IDS = {
    "SRC_UG_PRINT_20210317",
    "SRC_UG_SUSPEND_FORM_PDF_202504",
    "SRC_UG_RESUME_FORM_PDF_202504",
    "SRC_UG_GRAD_NOTICE_20250617",
    "SRC_GS_CERT_20130903",
    "SRC_UG_SUSPEND_PROCESS_20190418",
    "SRC_UG_RESUME_PROCESS_20190418",
    "SRC_UG_UNREGISTERED_20250321",
}

CANDIDATE_SURVEY_COLUMNS = [
    "candidate_id",
    "candidate_name",
    "data_baseline_status",
    "official_source_urls",
    "source_checked_at",
    "source_availability",
    "evidence_completeness_score",
    "condition_branch_score",
    "version_risk_score",
    "evaluation_value_score",
    "annotation_cost_score",
    "observed_evidence",
    "remaining_gap",
    "stage_2_option_group",
    "survey_status",
]

SECOND_REVIEW_COLUMNS = [
    "review_id",
    "evidence_id",
    "source_id",
    "selection_reason",
    "locator_recheck",
    "verbatim_recheck",
    "claim_recheck",
    "applicability_recheck",
    "result",
    "reviewed_at",
    "reviewer",
    "notes",
]


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
        self.assertEqual(6, summary["valid_fixtures_accepted"])
        self.assertEqual(8, summary["invalid_fixtures_rejected"])
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
        self.assertEqual(30, summary["migrated_legacy_rows"])
        self.assertEqual(0, summary["legacy_unmigrated_rows"])

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

    def test_stage_1e_remaining_migrations_are_verified_and_locatable(self) -> None:
        _, evidence_audit = load_csv(ROOT / "data/audit/evidence-audit.csv")
        _, source_audit = load_csv(ROOT / "data/audit/source-audit.csv")
        source_records = load_jsonl(ROOT / "data/research/source_records.jsonl")
        target_evidence = load_jsonl(ROOT / TARGET_EVIDENCE_RECORDS_PATH)
        audit_by_id = {row["evidence_id"]: row for row in evidence_audit}
        source_audit_by_id = {row["source_id"]: row for row in source_audit}
        source_by_id = {row["source_id"]: row for row in source_records}
        target_by_id = {row["evidence_id"]: row for row in target_evidence}

        normalized_source_text: dict[str, str] = {}
        for source_id in STAGE_1_SOURCE_IDS:
            source = source_by_id[source_id]
            self.assertEqual("captured", source["capture"]["status"])
            local_path = ROOT / source["capture"]["local_path"]
            if source["content_format"] == "html":
                normalized_source_text[source_id] = normalized_html_text(
                    local_path.read_text(encoding="utf-8")
                )

        mapped_target_ids: list[str] = []
        for legacy_id, expected_target_ids in STAGE_1E_MIGRATIONS.items():
            audit = audit_by_id[legacy_id]
            actual_target_ids = audit["target_evidence_ids"].split("|")
            self.assertEqual(expected_target_ids, actual_target_ids)
            self.assertEqual("verified", audit["verbatim_text_status"])
            self.assertEqual("verified", audit["review_status"])
            self.assertEqual("migrated", audit["migration_status"])

            expected_source_id = STAGE_1E_SOURCE_IDS[legacy_id]
            for target_id in actual_target_ids:
                target = target_by_id[target_id]
                self.assertEqual(expected_source_id, target["source_id"])
                self.assertEqual("verified", target["review"]["status"])
                anchor_text = target["source_locator"]["anchor_text"]
                self.assertIn(anchor_text, target["verbatim_text"])
                normalized_anchor = " ".join(
                    anchor_text.replace("\xa0", " ").split()
                )
                self.assertIn(normalized_anchor, normalized_source_text[expected_source_id])
            mapped_target_ids.extend(actual_target_ids)

        self.assertEqual(47, len(set(mapped_target_ids)))
        self.assertEqual(30, sum(
            row["migration_status"] == "migrated" for row in evidence_audit
        ))

        expected_attachment_relations = {
            "SRC_UG_GRAD_NOTICE_20250617": {
                "SRC_UG_GRAD_NOTICE_ATTACHMENT3_20250618",
                "SRC_UG_GRAD_NOTICE_ATTACHMENT4_20250618",
            },
            "SRC_UG_UNREGISTERED_20250321": {
                "SRC_UG_UNREGISTERED_NOTICE_TEMPLATE_20250321",
                "SRC_UG_UNREGISTERED_SUMMARY_20250321",
            },
        }
        for landing_id, attachment_ids in expected_attachment_relations.items():
            landing_targets = {
                relation["target_source_id"]
                for relation in source_by_id[landing_id]["relations"]
                if relation["relation_type"] == "landing_page_for"
            }
            self.assertEqual(attachment_ids, landing_targets)
            for attachment_id in attachment_ids:
                attachment = source_by_id[attachment_id]
                self.assertEqual("captured", attachment["capture"]["status"])
                self.assertTrue((ROOT / attachment["capture"]["local_path"]).is_file())
                self.assertIn(
                    {
                        "relation_type": "attachment_of",
                        "target_source_id": landing_id,
                    },
                    attachment["relations"],
                )

        unavailable = source_by_id["SRC_GS_CERT_20140616"]
        self.assertEqual("failed", unavailable["capture"]["status"])
        self.assertEqual(410, unavailable["capture"]["http_status"])
        self.assertIsNone(unavailable["capture"]["local_path"])
        self.assertIn("SRC_GS_CERT_20130903", {
            relation["target_source_id"] for relation in unavailable["relations"]
        })

        for source_id in {
            "SRC_UG_GRAD_NOTICE_20250617",
            "SRC_GS_CERT_20140616",
            "SRC_UG_SUSPEND_PROCESS_20190418",
            "SRC_UG_RESUME_PROCESS_20190418",
            "SRC_UG_UNREGISTERED_20250321",
        }:
            self.assertEqual("verified", source_audit_by_id[source_id]["review_status"])

    def test_stage_1f_candidate_survey_and_second_review_are_complete(self) -> None:
        survey_path = ROOT / "data/research/candidate-item-survey.csv"
        review_path = ROOT / "data/audit/stage1-second-review.csv"
        report_path = ROOT / "docs/data/STAGE_1_DATA_AUDIT.md"

        survey_headers, survey_rows = load_csv(survey_path)
        review_headers, review_rows = load_csv(review_path)
        target_evidence = load_jsonl(ROOT / TARGET_EVIDENCE_RECORDS_PATH)
        _, evidence_audit = load_csv(ROOT / "data/audit/evidence-audit.csv")
        target_by_id = {row["evidence_id"]: row for row in target_evidence}

        self.assertEqual(CANDIDATE_SURVEY_COLUMNS, survey_headers)
        self.assertEqual(9, len(survey_rows))
        self.assertEqual(
            {"UG_PROOF_PRINT", "UG_STATUS_CHANGE"},
            {
                row["candidate_id"]
                for row in survey_rows
                if row["data_baseline_status"] == "已验证"
            },
        )
        for row in survey_rows:
            self.assertEqual("已验证", row["survey_status"])
            self.assertLessEqual(date.fromisoformat(row["source_checked_at"]), date.today())
            urls = row["official_source_urls"].split("|")
            self.assertGreaterEqual(len(urls), 1)
            for url in urls:
                parsed = urlparse(url)
                self.assertEqual("https", parsed.scheme)
                self.assertTrue(
                    parsed.hostname == "jwc.jnu.edu.cn"
                    or parsed.hostname == "gs.jnu.edu.cn"
                )
            for field in {
                "evidence_completeness_score",
                "condition_branch_score",
                "version_risk_score",
                "evaluation_value_score",
                "annotation_cost_score",
            }:
                self.assertIn(int(row[field]), range(4))
            self.assertTrue(row["observed_evidence"].strip())
            self.assertTrue(row["remaining_gap"].strip())

        self.assertEqual(SECOND_REVIEW_COLUMNS, review_headers)
        self.assertEqual(30, len(review_rows))
        reviewed_ids = [row["evidence_id"] for row in review_rows]
        self.assertEqual(len(reviewed_ids), len(set(reviewed_ids)))
        self.assertTrue(set(reviewed_ids) <= set(target_by_id))
        self.assertEqual(
            STAGE_1_SOURCE_IDS,
            {row["source_id"] for row in review_rows},
        )
        for row in review_rows:
            self.assertEqual(target_by_id[row["evidence_id"]]["source_id"], row["source_id"])
            for field in {
                "locator_recheck",
                "verbatim_recheck",
                "claim_recheck",
                "applicability_recheck",
            }:
                self.assertEqual("通过", row[field])
            self.assertEqual("已验证", row["result"])
            self.assertTrue(row["reviewer"].strip())
            self.assertTrue(row["notes"].strip())

        reviewed_id_set = set(reviewed_ids)
        for audit in evidence_audit:
            if audit["claim_review_status"] != "known_mismatch":
                continue
            self.assertTrue(
                reviewed_id_set
                & set(audit["target_evidence_ids"].split("|")),
                audit["evidence_id"],
            )

        report_text = report_path.read_text(encoding="utf-8")
        for marker in {
            "# 阶段 1 数据审计报告",
            "30 条旧证据",
            "136 条目标证据",
            "第二次独立复核",
            "候选事项普查",
            "阶段 1 验收结论",
        }:
            self.assertIn(marker, report_text)

    def test_duplicate_values_are_reported_deterministically(self) -> None:
        self.assertEqual(["A", "B"], duplicate_values(["B", "A", "B", "C", "A"]))

    def test_stage2a_scope_allocation_and_annotation_contract_are_complete(
        self,
    ) -> None:
        errors, summary = validate_stage2a_contract(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(8, summary["stage2_formal_items"])
        self.assertEqual(200, summary["stage2_allocated_samples"])
        self.assertEqual(7, summary["stage2_source_migration_rows"])
        self.assertEqual(100, summary["stage2_second_review_target_percent"])
        self.assertEqual(1, summary["stage2_allocation_frozen"])
        self.assertEqual(0, summary["stage2_content_frozen"])
        self.assertEqual(1, summary["stage2_fixture_link_sets_validated"])

    def test_stage2_fixture_links_reject_cross_field_inconsistency(self) -> None:
        process = load_json(
            ROOT / "tests/fixtures/data/valid/process-record.json"
        )
        sample = load_json(
            ROOT / "tests/fixtures/data/valid/evaluation-sample.json"
        )
        review = load_json(
            ROOT / "tests/fixtures/data/valid/evaluation-review-record.json"
        )
        evidence = load_jsonl(ROOT / TARGET_EVIDENCE_RECORDS_PATH)

        process["evidence_snapshot"]["evidence_ids"].remove("UGP014")
        sample["gold"]["allowed_claim_ids"].append("CLM_999")
        review["secondary_review"]["reviewer"] = review[
            "primary_annotation"
        ]["reviewer"]

        errors = validate_stage2_fixture_links(
            process,
            sample,
            review,
            evidence,
        )

        self.assertTrue(
            any("evidence_snapshot must exactly equal" in error for error in errors)
        )
        self.assertTrue(
            any("gold.allowed_claim_ids" in error for error in errors)
        )
        self.assertTrue(
            any("primary and secondary reviewers must differ" in error for error in errors)
        )

    def test_stage2b_withdrawal_sources_evidence_processes_and_reviews_close(
        self,
    ) -> None:
        errors, summary = validate_stage2b_withdrawal_contract(ROOT)

        self.assertEqual([], errors)
        self.assertEqual(10, summary["stage2b_withdrawal_sources"])
        self.assertEqual(7, summary["stage2b_withdrawal_captured_sources"])
        self.assertEqual(3, summary["stage2b_withdrawal_failed_sources"])
        self.assertEqual(113, summary["stage2b_withdrawal_evidence"])
        self.assertEqual(5, summary["stage2b_withdrawal_process_records"])
        self.assertEqual(113, summary["stage2b_withdrawal_second_reviews"])
        self.assertEqual(4, summary["stage2b_withdrawal_positive_examples"])
        self.assertEqual(5, summary["stage2b_withdrawal_negative_examples"])
        self.assertEqual(4, summary["stage2b_withdrawal_version_groups"])
        self.assertEqual(10, summary["stage2b_withdrawal_capture_plan_rows"])
        self.assertEqual(
            3,
            summary["stage2b_withdrawal_primary_access_failures"],
        )

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
        self.assertEqual(34, summary["target_source_records"])
        self.assertEqual(29, summary["captured_source_files"])
        self.assertEqual(31, summary["verified_source_records"])
        self.assertEqual(309, summary["target_evidence_units"])
        self.assertEqual(309, summary["verified_target_evidence_units"])
        self.assertEqual(309, summary["source_located_evidence_units"])


if __name__ == "__main__":
    unittest.main()
