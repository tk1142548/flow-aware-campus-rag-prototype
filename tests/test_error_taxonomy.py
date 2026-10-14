"""Contract tests for the layered error taxonomy."""
from __future__ import annotations

import unittest

from app.backend.error_taxonomy import CODES, classify_errors, layer_of, primary_error

CLEAN = {
    "evidence_recall": 1.0, "evidence_precision": 0.8, "citation_validity": 1.0,
    "claim_coverage": 1.0, "step_coverage": 1.0, "material_coverage": 1.0,
    "answer_quality": 1.0, "response_mode_accuracy": 1.0, "missing_slot_f1": 1.0,
    "follow_up_correct": 1.0,
}

LAYERS = {"retrieval", "process", "verification", "generation", "interaction", "none"}


def metrics(**overrides) -> dict:
    return {**CLEAN, **overrides}


class ErrorTaxonomyTests(unittest.TestCase):
    def test_clean_run_reports_none(self) -> None:
        self.assertEqual(["none"], classify_errors(metrics()))
        self.assertEqual("none", primary_error(["none"]))
        self.assertEqual("none", layer_of(["none"]))

    def test_retrieval_outranks_everything_else(self) -> None:
        codes = classify_errors(metrics(evidence_recall=0.0, step_coverage=0.5,
                                        response_mode_accuracy=0.0))

        self.assertEqual("retrieval_miss", primary_error(codes))
        self.assertEqual("retrieval", layer_of(codes))

    def test_partial_recall_is_distinguished_from_a_total_miss(self) -> None:
        self.assertEqual("partial_retrieval",
                         primary_error(classify_errors(metrics(evidence_recall=0.5))))

    def test_process_layer_beats_verification_and_generation(self) -> None:
        codes = classify_errors(metrics(step_coverage=0.5, citation_validity=0.0,
                                        claim_coverage=0.0))

        self.assertEqual("step_coverage_gap", primary_error(codes))
        self.assertEqual("process", layer_of(codes))

    def test_citation_outside_retrieval_is_a_verification_error(self) -> None:
        codes = classify_errors(metrics(citation_validity=0.5))

        self.assertEqual("citation_outside_retrieval", primary_error(codes))
        self.assertEqual("verification", layer_of(codes))

    def test_judge_can_add_an_unsupported_assertion(self) -> None:
        codes = classify_errors(metrics(), unsupported_ratio=0.25)

        self.assertIn("unsupported_assertion", codes)
        self.assertEqual("verification", layer_of(codes))

    def test_missing_required_claim_is_a_generation_error(self) -> None:
        codes = classify_errors(metrics(claim_coverage=0.5))

        self.assertEqual("answer_omission", primary_error(codes))
        self.assertEqual("generation", layer_of(codes))

    def test_interaction_errors_are_reported_last(self) -> None:
        codes = classify_errors(metrics(response_mode_accuracy=0.0, missing_slot_f1=0.0))

        self.assertEqual("wrong_response_mode", primary_error(codes))
        self.assertEqual("interaction", layer_of(codes))

    def test_every_code_maps_to_a_known_layer(self) -> None:
        for code, layer in CODES.items():
            self.assertIn(layer, LAYERS, code)


if __name__ == "__main__":
    unittest.main()
