"""Evaluation-side scoring that never requires the system to emit annotation ids.

The previous scorer compared `claim_id` values, which a generative system can
never produce, so every generative baseline scored zero. Here the gold side is
resolved to *text* and compared to the answer by content, so any system that
says the right thing scores well regardless of how it labels it.

This module is evaluation-only. It is expected to read `sample['gold']`; nothing
in the inference path may import it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

CLAUSE_SPLIT = re.compile(r"[\n。；;！!？?]+")
LEXICAL_THRESHOLD = 0.5
SEMANTIC_THRESHOLD = 0.72
REFUSAL_MODES = {"abstention"}
CONDITIONAL_MODES = {"clarification", "version_qualified"}


@dataclass
class Prediction:
    """What any system under test must return. Nothing here is annotation-derived."""

    answer_text: str
    response_mode: str
    retrieved_evidence_ids: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    missing_slot_ids: list[str] = field(default_factory=list)
    follow_up_question: str | None = None
    item_id: str | None = None


def char_bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"\s+", "", text)
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def lexical_containment(haystack: str, needle: str) -> float:
    """Fraction of `needle` character bigrams present in `haystack`."""
    needle_grams = char_bigrams(needle)
    if not needle_grams:
        return 1.0
    return len(needle_grams & char_bigrams(haystack)) / len(needle_grams)


def split_clauses(text: str) -> list[str]:
    return [part.strip() for part in CLAUSE_SPLIT.split(text) if part.strip()]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    ln = math.sqrt(sum(a * a for a in left))
    rn = math.sqrt(sum(b * b for b in right))
    return dot / (ln * rn) if ln and rn else 0.0


def resolve_gold_elements(repository: Any, sample: dict) -> list[dict]:
    """Turn gold ids into comparable text elements, using the process annotation."""
    gold = sample["gold"]
    process = repository.processes.get(sample["process_id"])
    if process is None:
        return []
    elements: list[dict] = []

    claims = {c["claim_id"]: c for c in process["allowed_claims"]}
    for cid in gold["allowed_claim_ids"]:
        claim = claims.get(cid)
        if claim:
            elements.append(
                {"kind": "claim", "id": cid, "text": claim["text"],
                 "evidence_ids": list(claim["evidence_ids"])}
            )

    steps = {s["step_id"]: s for s in process["steps"]}
    for sid in gold["ordered_step_ids"]:
        step = steps.get(sid)
        if step:
            elements.append(
                {"kind": "step", "id": sid, "text": f"{step.get('actor', '')}{step['action']}",
                 "order": step.get("order"), "evidence_ids": list(step["evidence_ids"])}
            )

    materials = {m["material_id"]: m for m in process["materials"]}
    for mid in gold["material_ids"]:
        material = materials.get(mid)
        if material:
            elements.append(
                {"kind": "material", "id": mid, "text": material["name"],
                 "evidence_ids": list(material["evidence_ids"])}
            )
    return elements


def resolve_gold_slot_names(repository: Any, sample: dict) -> list[str]:
    """Map gold slot ids to their slot names, so free text can be compared fairly.

    Systems describe missing conditions in their own words; comparing those words
    against ids such as ``SL_REQUEST_TYPE`` can only ever produce an empty
    intersection. The gold side is therefore resolved to a slot *name*.
    """
    process = repository.processes.get(sample["process_id"])
    if process is None:
        return []
    names = {slot["slot_id"]: slot.get("name") or slot["slot_id"]
             for slot in process.get("slots", [])}
    return [names.get(slot_id, slot_id) for slot_id in sample["gold"]["missing_slot_ids"]]


class ElementMatcher:
    """Coverage by content: lexical containment OR embedding similarity."""

    def __init__(
        self,
        client: Any | None = None,
        lexical_threshold: float = LEXICAL_THRESHOLD,
        semantic_threshold: float = SEMANTIC_THRESHOLD,
    ) -> None:
        self.client = client
        self.lexical_threshold = lexical_threshold
        self.semantic_threshold = semantic_threshold

    def match(
        self,
        answer_text: str,
        elements: Sequence[dict],
        *,
        answer_vectors: Sequence[Sequence[float]] | None = None,
        element_vectors: Sequence[Sequence[float]] | None = None,
    ) -> list[dict]:
        clauses = split_clauses(answer_text)
        if not clauses or not elements:
            return [
                {"element": el, "covered": False, "lexical": 0.0, "semantic": 0.0,
                 "best_clause": None}
                for el in elements
            ]
        if answer_vectors is None and self.client is not None:
            answer_vectors = self.client.embed(clauses)
        if element_vectors is None and self.client is not None:
            element_vectors = self.client.embed([el["text"] for el in elements])

        results: list[dict] = []
        for index, element in enumerate(elements):
            best_lex = max(lexical_containment(clause, element["text"]) for clause in clauses)
            best_sem = 0.0
            best_clause = None
            if answer_vectors and element_vectors:
                vector = element_vectors[index]
                for clause, clause_vector in zip(clauses, answer_vectors):
                    score = cosine(clause_vector, vector)
                    if score > best_sem:
                        best_sem, best_clause = score, clause
            covered = best_lex >= self.lexical_threshold or best_sem >= self.semantic_threshold
            results.append(
                {"element": element, "covered": covered, "lexical": best_lex,
                 "semantic": best_sem, "best_clause": best_clause}
            )
        return results


def _coverage_by_kind(matches: Sequence[dict]) -> dict[str, float]:
    totals: dict[str, list[bool]] = {}
    for match in matches:
        totals.setdefault(match["element"]["kind"], []).append(match["covered"])
    return {
        kind: sum(flags) / len(flags)
        for kind, flags in totals.items()
    }


def recall(found: Iterable[str], gold: Iterable[str]) -> float:
    gold_set = set(gold)
    if not gold_set:
        return 1.0
    return len(set(found) & gold_set) / len(gold_set)


def precision(found: Iterable[str], gold: Iterable[str]) -> float:
    found_set = set(found)
    if not found_set:
        return 1.0 if not set(gold) else 0.0
    return len(found_set & set(gold)) / len(found_set)


def _slot_f1_by_content(gold_names: Sequence[str], predicted: Sequence[str],
                        matcher: ElementMatcher) -> float:
    """Slot F1 on content, not on ids — the counterpart of the claim-side fix."""
    if not gold_names and not predicted:
        return 1.0
    if not gold_names or not predicted:
        return 0.0

    gold_elements = [{"kind": "slot", "id": name, "text": name} for name in gold_names]
    recalled = sum(1 for m in matcher.match("\n".join(predicted), gold_elements) if m["covered"])
    predicted_elements = [{"kind": "slot", "id": text, "text": text} for text in predicted]
    precise = sum(1 for m in matcher.match("\n".join(gold_names), predicted_elements)
                  if m["covered"])

    recall_value = recalled / len(gold_names)
    precision_value = precise / len(predicted)
    total = recall_value + precision_value
    return 2 * recall_value * precision_value / total if total else 0.0


def response_mode_matches(predicted: str, gold: str) -> bool:
    if predicted == gold:
        return True
    # A resolved conversation still delivers an answer; accept either label.
    return {predicted, gold} == {"answer", "conversation_resolution"}


def score_prediction(
    repository: Any,
    sample: dict,
    prediction: Prediction,
    matcher: ElementMatcher,
    *,
    answer_vectors: Sequence[Sequence[float]] | None = None,
    element_vectors: Sequence[Sequence[float]] | None = None,
) -> dict:
    """Score one prediction. Returns metrics plus per-element detail."""
    gold = sample["gold"]
    elements = resolve_gold_elements(repository, sample)
    matches = matcher.match(
        prediction.answer_text,
        elements,
        answer_vectors=answer_vectors,
        element_vectors=element_vectors,
    )
    coverage = _coverage_by_kind(matches)

    retrieved = set(prediction.retrieved_evidence_ids)
    citation_validity = (
        sum(1 for c in prediction.citations if c in retrieved) / len(prediction.citations)
        if prediction.citations
        else 1.0
    )

    item_correct = float(prediction.item_id == sample["item_id"])
    mode_ok = float(response_mode_matches(prediction.response_mode, gold["response_mode"]))
    slot_f1 = _slot_f1_by_content(
        resolve_gold_slot_names(repository, sample), prediction.missing_slot_ids, matcher
    )
    follow_up_ok = float(bool(prediction.follow_up_question) == bool(gold["follow_up_question"]))

    metrics = {
        "item_correct": item_correct,
        "response_mode_accuracy": mode_ok,
        "evidence_recall": recall(prediction.retrieved_evidence_ids, gold["supporting_evidence_ids"]),
        "evidence_precision": precision(prediction.retrieved_evidence_ids, gold["supporting_evidence_ids"]),
        "missing_slot_f1": slot_f1,
        "follow_up_correct": follow_up_ok,
        "citation_validity": citation_validity,
    }
    for kind in ("claim", "step", "material"):
        metrics[f"{kind}_coverage"] = coverage.get(kind, 1.0)
    metrics["answer_quality"] = (
        sum(m["covered"] for m in matches) / len(matches) if matches else 1.0
    )

    if gold["response_mode"] in REFUSAL_MODES:
        # Nothing should be asserted; coverage is vacuous and the mode is the test.
        ok = mode_ok == 1.0
    else:
        ok = (
            item_correct == 1.0
            and mode_ok == 1.0
            and metrics["missing_slot_f1"] == 1.0
            and metrics["follow_up_correct"] == 1.0
            and metrics["citation_validity"] == 1.0
            and metrics["evidence_recall"] == 1.0
            and all(metrics[f"{kind}_coverage"] == 1.0 for kind in coverage)
        )
    metrics["overall_success"] = float(ok)

    return {
        "metrics": metrics,
        "elements": [
            {
                "kind": m["element"]["kind"],
                "id": m["element"]["id"],
                "text": m["element"]["text"],
                "covered": m["covered"],
                "lexical": round(m["lexical"], 4),
                "semantic": round(m["semantic"], 4),
            }
            for m in matches
        ],
    }


def summarise(records: Sequence[dict]) -> dict:
    """Average every metric across scored samples and collect a failure tally."""
    if not records:
        return {"sample_count": 0, "metrics": {}}
    keys = sorted(records[0]["metrics"])
    summary = {
        key: sum(r["metrics"][key] for r in records) / len(records) for key in keys
    }
    failures: dict[str, int] = {}
    for record in records:
        for element in record["elements"]:
            if not element["covered"]:
                failures[f"{element['kind']}:{element['id']}"] = (
                    failures.get(f"{element['kind']}:{element['id']}", 0) + 1
                )
    return {"sample_count": len(records), "metrics": summary, "uncovered_elements": failures}


JUDGE_SYSTEM = (
    "你是严格的事实核验员。判断【回答】中的每条实质性陈述是否被【证据】支持。"
    "只依据给定证据，不使用你自己的常识补充。"
)

JUDGE_USER = """【问题】
{question}

【证据】
{evidence}

【回答】
{answer}

只输出 JSON：
{{"supported": [{{"claim": "回答中的一条实质陈述", "verdict": "supported|unsupported|unclear", "evidence_id": "支撑它的证据编号，没有则空串"}}],
 "unsupported_ratio": 0.0,
 "reason": "一句话理由"}}

要求：
- 逐条拆出回答中的实质性陈述（办理主体、对象、步骤、材料、时间、地点、费用、版本）。
- verdict=supported 仅当证据中有文字能直接支撑该陈述。
- unsupported_ratio = verdict 为 unsupported 的条数 / 总条数。"""


def judge_support(client: Any, question: str, answer: str, evidence: Sequence[dict]) -> dict:
    """LLM-as-judge pass for citation faithfulness. Calibrate on a human slice."""
    evidence_block = "\n".join(
        f"[{e['evidence_id']}] {e.get('normalized_claim') or e.get('verbatim_text', '')}"
        for e in evidence
    )
    payload = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": JUDGE_USER.format(
            question=question, evidence=evidence_block, answer=answer)},
    ]
    try:
        result = client.chat_json(payload, temperature=0.0, max_tokens=1200)
    except (ValueError, RuntimeError) as error:
        return {"error": str(error), "unsupported_ratio": None, "supported": []}
    items = result.get("supported") or []
    unsupported = [i for i in items if i.get("verdict") == "unsupported"]
    return {
        "supported": items,
        "unsupported_ratio": (len(unsupported) / len(items)) if items else 0.0,
        "reason": result.get("reason", ""),
    }
