"""Contract tests for the id-free scorer."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.backend.research_data import ResearchRepository
from app.backend.scoring_v2 import (
    ElementMatcher,
    Prediction,
    lexical_containment,
    resolve_gold_elements,
    response_mode_matches,
    score_prediction,
    summarise,
)


class ScoringV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.repo = ResearchRepository(cls.root)
        cls.samples = [
            json.loads(line)
            for line in (cls.root / "data/evaluation/stage2_samples.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]

    def sample_with_claims(self) -> dict:
        return next(
            s for s in self.samples
            if s["gold"]["allowed_claim_ids"] and s["gold"]["response_mode"] == "answer"
        )

    def test_gold_elements_resolve_to_text(self) -> None:
        elements = resolve_gold_elements(self.repo, self.sample_with_claims())

        self.assertTrue(elements)
        self.assertTrue(all(e["text"].strip() for e in elements))
        self.assertTrue(all(e["kind"] in {"claim", "step", "material"} for e in elements))

    def test_restating_the_gold_fully_covers_it(self) -> None:
        sample = self.sample_with_claims()
        elements = resolve_gold_elements(self.repo, sample)
        answer = "\n".join(e["text"] for e in elements)

        result = score_prediction(
            self.repo, sample,
            Prediction(answer_text=answer, response_mode="answer",
                       retrieved_evidence_ids=list(sample["gold"]["supporting_evidence_ids"]),
                       citations=list(sample["gold"]["supporting_evidence_ids"]),
                       item_id=sample["item_id"]),
            ElementMatcher(),
        )

        self.assertEqual(1.0, result["metrics"]["answer_quality"])
        self.assertEqual(1.0, result["metrics"]["claim_coverage"])

    def test_unrelated_answer_covers_nothing(self) -> None:
        sample = self.sample_with_claims()

        result = score_prediction(
            self.repo, sample,
            Prediction(answer_text="今天天气不错，宿舍楼下的猫又在晒太阳。",
                       response_mode="answer", item_id=sample["item_id"]),
            ElementMatcher(),
        )

        self.assertEqual(0.0, result["metrics"]["answer_quality"])

    def test_scoring_never_requires_annotation_ids(self) -> None:
        """A prediction carrying no ids at all can still score perfectly."""
        sample = self.sample_with_claims()
        answer = "\n".join(e["text"] for e in resolve_gold_elements(self.repo, sample))

        result = score_prediction(
            self.repo, sample,
            Prediction(answer_text=answer, response_mode="answer",
                       retrieved_evidence_ids=list(sample["gold"]["supporting_evidence_ids"]),
                       item_id=sample["item_id"]),
            ElementMatcher(),
        )

        self.assertEqual(1.0, result["metrics"]["overall_success"])

    def test_citation_outside_retrieved_set_breaks_validity(self) -> None:
        sample = self.sample_with_claims()
        answer = "\n".join(e["text"] for e in resolve_gold_elements(self.repo, sample))

        result = score_prediction(
            self.repo, sample,
            Prediction(answer_text=answer, response_mode="answer",
                       retrieved_evidence_ids=list(sample["gold"]["supporting_evidence_ids"]),
                       citations=["EVIDENCE_NOT_RETRIEVED"], item_id=sample["item_id"]),
            ElementMatcher(),
        )

        self.assertEqual(0.0, result["metrics"]["citation_validity"])
        self.assertEqual(0.0, result["metrics"]["overall_success"])

    def test_response_mode_accepts_resolved_conversation(self) -> None:
        self.assertTrue(response_mode_matches("answer", "conversation_resolution"))
        self.assertTrue(response_mode_matches("clarification", "clarification"))
        self.assertFalse(response_mode_matches("answer", "abstention"))

    def test_abstention_is_judged_on_mode_alone(self) -> None:
        sample = next(
            s for s in self.samples if s["gold"]["response_mode"] == "abstention"
        )

        right = score_prediction(
            self.repo, sample,
            Prediction(answer_text="现有证据不足以确认该事项。", response_mode="abstention",
                       item_id=sample["item_id"]),
            ElementMatcher(),
        )
        wrong = score_prediction(
            self.repo, sample,
            Prediction(answer_text="直接去教务处办理即可。", response_mode="answer",
                       item_id=sample["item_id"]),
            ElementMatcher(),
        )

        self.assertEqual(1.0, right["metrics"]["overall_success"])
        self.assertEqual(0.0, wrong["metrics"]["overall_success"])

    def test_lexical_containment_direction(self) -> None:
        self.assertGreater(lexical_containment("需提交书面退学申请材料", "书面退学申请"), 0.5)
        self.assertLess(lexical_containment("今天天气不错", "书面退学申请"), 0.2)

    def test_summarise_reports_uncovered_elements(self) -> None:
        sample = self.sample_with_claims()
        record = score_prediction(
            self.repo, sample,
            Prediction(answer_text="无关回答。", response_mode="answer", item_id=sample["item_id"]),
            ElementMatcher(),
        )

        summary = summarise([record])

        self.assertEqual(1, summary["sample_count"])
        self.assertTrue(summary["uncovered_elements"])


if __name__ == "__main__":
    unittest.main()
