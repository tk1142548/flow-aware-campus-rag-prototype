import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_stage2_content import audit


class ContentAuditTests(unittest.TestCase):
    def run_audit(self, duplicate=False, outside=False, version=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/evaluation").mkdir(parents=True)
            (root / "data/research").mkdir(parents=True)
            sample = {"sample_id": "X", "dataset_version": "1.0.0", "process_id": "P", "conversation": [{"role": "user", "text": "测试问题"}], "gold": {"supporting_evidence_ids": ["E002" if outside else "E001"], "allowed_claim_ids": ["C"]}}
            process = {"process_id": "P", "evidence_snapshot": {"evidence_ids": ["E001"]}, "allowed_claims": [{"claim_id": "C", "evidence_ids": ["E001"]}]}
            (root / "data/evaluation/stage2_samples.jsonl").write_text(json.dumps(sample)+"\n"+(json.dumps(sample)+"\n" if duplicate else ""), encoding="utf-8")
            (root / "data/research/process_records.jsonl").write_text(json.dumps(process)+"\n", encoding="utf-8")
            (root / "data/research/stage2-evaluation-plan.json").write_text(json.dumps({"dataset_release_version": "2.0.0" if version else "1.0.0"}), encoding="utf-8")
            return audit(root)

    def test_consistent_records(self):
        self.assertEqual([], self.run_audit()["link_errors"])

    def test_actual_duplicates_are_detected(self):
        self.assertEqual(1, self.run_audit(duplicate=True)["duplicate_excess"])

    def test_foreign_evidence_and_version_are_detected(self):
        codes = {e["code"] for e in self.run_audit(outside=True, version=True)["link_errors"]}
        self.assertEqual({"evidence_outside_process", "claim_evidence_mismatch", "release_version_mismatch"}, codes)
