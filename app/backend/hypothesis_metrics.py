"""Per-hypothesis metrics, computed offline from scored run records.

Each hypothesis gets a metric that can move when the component it tests works,
instead of the seven-way conjunction, which a single unrelated miss sets to zero.

H1 (flow skeleton) - on samples whose gold has at least ``MULTI_STEP`` steps:
    step_recall      share of gold steps the answer covers
    step_order       Kendall-style agreement between the order covered gold steps
                     appear in the answer and their gold order
    material_recall  share of gold materials the answer covers. Precision (extra
                     materials the answer invents) is measured on the H2 side,
                     since an invented material is an unsupported assertion

H2 (claim verification) - on content answers:
    unsupported_rate share of answer assertions a judge finds unsupported by the
                     retrieved evidence (needs judge output; see judge_assertions)

H3 (interaction control) - on all samples:
    mode_macro_f1    macro F1 over the response modes present in the gold
    abstain_precision / abstain_recall
    over_clarification share of answerable samples where the system asked instead

Everything here reads only stored records; nothing calls a model.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

from .scoring_v2 import split_clauses, lexical_containment

MULTI_STEP = 3
EQUIVALENT_MODES = {"conversation_resolution": "answer"}


def canonical_mode(mode: str) -> str:
    return EQUIVALENT_MODES.get(mode, mode)


# --------------------------------------------------------------------- H1

def _first_position(answer: str, text: str, threshold: float = 0.5) -> int | None:
    """Index of the first answer clause that covers ``text``; None if none does."""
    best_index, best_score = None, 0.0
    for index, clause in enumerate(split_clauses(answer)):
        score = lexical_containment(clause, text)
        if score > best_score:
            best_index, best_score = index, score
    return best_index if best_score >= threshold else None


def step_order(answer: str, steps: Sequence[dict]) -> float | None:
    """Concordant share of covered gold-step pairs, by position in the answer.

    ``steps`` are the gold step elements in gold order, as stored by the scorer.
    Returns None when fewer than two gold steps are located in the answer.
    """
    located = []
    for rank, step in enumerate(steps):
        if not step.get("covered"):
            continue
        position = _first_position(answer, step["text"], threshold=0.3)
        if position is not None:
            located.append((rank, position))
    if len(located) < 2:
        return None
    concordant = discordant = 0
    for i in range(len(located)):
        for j in range(i + 1, len(located)):
            delta = (located[i][0] - located[j][0]) * (located[i][1] - located[j][1])
            if delta > 0:
                concordant += 1
            elif delta < 0:
                discordant += 1
    total = concordant + discordant
    return concordant / total if total else 1.0


def flow_metrics(record: dict) -> dict:
    elements = record.get("elements") or []
    steps = [e for e in elements if e["kind"] == "step"]
    materials = [e for e in elements if e["kind"] == "material"]
    answer = record["prediction"]["answer_text"]
    out: dict[str, Any] = {"gold_steps": len(steps)}
    if steps:
        out["step_recall"] = sum(e["covered"] for e in steps) / len(steps)
        out["step_order"] = step_order(answer, steps)
    if materials:
        out["material_recall"] = sum(e["covered"] for e in materials) / len(materials)
    return out


# --------------------------------------------------------------------- H3

def mode_table(records: Iterable[dict], gold_modes: dict[str, str]) -> Counter:
    table: Counter = Counter()
    for record in records:
        gold = canonical_mode(gold_modes[record["sample_id"]])
        predicted = canonical_mode(record["prediction"]["response_mode"])
        table[(gold, predicted)] += 1
    return table


def interaction_metrics(records: Sequence[dict], gold_modes: dict[str, str]) -> dict:
    table = mode_table(records, gold_modes)
    golds = sorted({g for g, _ in table})
    per_mode = {}
    for mode in golds:
        tp = table[(mode, mode)]
        fp = sum(n for (g, p), n in table.items() if p == mode and g != mode)
        fn = sum(n for (g, p), n in table.items() if g == mode and p != mode)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_mode[mode] = {"precision": precision, "recall": recall, "f1": f1,
                          "support": tp + fn}
    answerable = [r for r in records
                  if canonical_mode(gold_modes[r["sample_id"]]) not in {"clarification", "abstention"}]
    over_asked = sum(1 for r in answerable if r["prediction"]["response_mode"] == "clarification")
    return {
        "mode_accuracy": sum(table[(m, m)] for m in golds) / max(1, sum(table.values())),
        "mode_macro_f1": sum(v["f1"] for v in per_mode.values()) / len(per_mode) if per_mode else 0.0,
        "per_mode": per_mode,
        "abstain_precision": per_mode.get("abstention", {}).get("precision", 0.0),
        "abstain_recall": per_mode.get("abstention", {}).get("recall", 0.0),
        "over_clarification": over_asked / len(answerable) if answerable else 0.0,
        "confusion": {f"{g}->{p}": n for (g, p), n in sorted(table.items())},
    }


# --------------------------------------------------------------- per-sample

def per_sample_scores(record: dict, gold_mode: str) -> dict:
    """Continuous per-sample scores for paired tests.

    ``mode_correct`` is binary. Flow scores are only defined where the gold has
    steps or materials; callers restrict the H1 test to multi-step samples.
    """
    scores = {"mode_correct": float(canonical_mode(record["prediction"]["response_mode"])
                                    == canonical_mode(gold_mode))}
    scores.update({k: v for k, v in flow_metrics(record).items() if v is not None})
    return scores
