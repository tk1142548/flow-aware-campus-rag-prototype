"""Error taxonomy across the four system layers.

Design rule: classification is driven by the scorer's output, never by the
sample's `scenario_type`. Passing an evaluation label into the classifier would
let the taxonomy "explain" failures using information the system never had.

Layers are checked in the order a system actually fails, so the first hit is the
earliest point where the pipeline broke.

    retrieval -> process -> verification -> generation -> interaction
"""
from __future__ import annotations

from typing import Iterable, Sequence

LAYER_ORDER = ("retrieval", "process", "verification", "generation", "interaction")

CODES = {
    # 检索层
    "retrieval_miss": "retrieval",
    "partial_retrieval": "retrieval",
    # 流程层
    "step_coverage_gap": "process",
    "material_gap": "process",
    # 核验层
    "citation_outside_retrieval": "verification",
    "unsupported_assertion": "verification",
    # 生成层
    "answer_omission": "generation",
    "answer_over_generalization": "generation",
    # 交互层
    "wrong_response_mode": "interaction",
    "missing_slot_mismatch": "interaction",
    "follow_up_mismatch": "interaction",
    "none": "none",
}

GENERATION_CODES = {code for code, layer in CODES.items() if layer == "generation"}


def classify_errors(metrics: dict, unsupported_ratio: float | None = None) -> list[str]:
    """Return every failing code, most fundamental layer first."""
    codes: list[str] = []

    recall = metrics.get("evidence_recall", 1.0)
    if recall <= 0.0:
        codes.append("retrieval_miss")
    elif recall < 1.0:
        codes.append("partial_retrieval")

    if metrics.get("step_coverage", 1.0) < 1.0:
        codes.append("step_coverage_gap")
    if metrics.get("material_coverage", 1.0) < 1.0:
        codes.append("material_gap")

    if metrics.get("citation_validity", 1.0) < 1.0:
        codes.append("citation_outside_retrieval")
    if unsupported_ratio is not None and unsupported_ratio > 0.0:
        codes.append("unsupported_assertion")

    if metrics.get("claim_coverage", 1.0) < 1.0:
        codes.append("answer_omission")
    # All required elements present but wording strays beyond them: the answer
    # generalised past what the evidence supports.
    if (metrics.get("answer_quality", 1.0) >= 1.0
            and metrics.get("evidence_precision", 1.0) < 0.5):
        codes.append("answer_over_generalization")

    if metrics.get("response_mode_accuracy", 1.0) < 1.0:
        codes.append("wrong_response_mode")
    if metrics.get("missing_slot_f1", 1.0) < 1.0:
        codes.append("missing_slot_mismatch")
    if metrics.get("follow_up_correct", 1.0) < 1.0:
        codes.append("follow_up_mismatch")

    return codes or ["none"]


def primary_error(codes: Sequence[str]) -> str:
    """The earliest failing layer, used as a single label for reporting."""
    for layer in LAYER_ORDER:
        for code in codes:
            if CODES.get(code) == layer:
                return code
    return "none"


def layer_of(codes: Iterable[str]) -> str:
    for layer in LAYER_ORDER:
        if any(CODES.get(code) == layer for code in codes):
            return layer
    return "none"
