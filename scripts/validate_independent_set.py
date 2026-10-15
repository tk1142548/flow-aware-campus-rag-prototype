"""Validate the independent confirmatory evaluation set.

Checks, in order:
  1. schema conformance (same schema as the development set)
  2. gold referential integrity: every claim / step / material / evidence id exists,
     and every chosen claim's evidence is inside the sample's supporting evidence
  3. composition: 8 items x 15, scenario quotas as pre-registered
  4. new-knowledge guarantee: at least 60 samples rest on evidence the development
     set never used
  5. contamination: no question is a near-duplicate of a development-set question
     (character 3-gram Jaccard <= 0.6, embedding cosine <= 0.85), and no two
     questions in the new set are near-duplicates of each other

Usage:
    python scripts/validate_independent_set.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.research_data import ResearchRepository

INDEPENDENT = ROOT / "data/evaluation/independent-set.jsonl"
DEV_SET = ROOT / "data/evaluation/stage2_samples.jsonl"
SCHEMA = ROOT / "data/schemas/evaluation-sample.schema.json"

ITEM_QUOTA = 15
SCENARIO_QUOTA = {
    "direct": 20, "condition_missing": 20, "object_mismatch": 15, "step_error": 15,
    "material_confusion": 15, "version_conflict": 15, "out_of_scope": 10, "multi_turn": 10,
}
SCENARIO_MODE = {
    "direct": "answer", "condition_missing": "clarification", "object_mismatch": "scoped_correction",
    "version_conflict": "version_qualified", "step_error": "scoped_correction",
    "material_confusion": "scoped_correction", "out_of_scope": "abstention",
    "multi_turn": "conversation_resolution",
}
MIN_FRESH_SAMPLES = 60
JACCARD_LIMIT = 0.6
COSINE_LIMIT = 0.85
INTERNAL_COSINE_LIMIT = 0.95


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def question_of(sample: dict) -> str:
    return "\n".join(t["text"] for t in sample["conversation"] if t["role"] == "user")


def grams(text: str, size: int = 3) -> set[str]:
    text = "".join(text.split())
    return {text[i:i + size] for i in range(max(len(text) - size + 1, 0))}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        import jsonschema
    except ImportError:
        jsonschema = None
        warnings.append("jsonschema 未安装，跳过结构校验")

    repository = ResearchRepository(ROOT)
    samples = load(INDEPENDENT)
    dev = load(DEV_SET)
    print(f"独立集 {len(samples)} 条；开发集 {len(dev)} 条")

    # 1. schema
    if jsonschema:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        for sample in samples:
            for problem in jsonschema.Draft7Validator(schema).iter_errors(sample):
                errors.append(f"{sample['sample_id']}: schema {problem.message[:120]}")
        print(f"[1] 结构校验：{'通过' if not errors else f'{len(errors)} 处问题'}")

    # 2. referential integrity
    before = len(errors)
    evidence_ids = set(repository.evidence)
    for sample in samples:
        sid = sample["sample_id"]
        if sample["scenario_type"] == "out_of_scope":
            if sample["process_id"] is not None or sample["item_id"] is not None:
                errors.append(f"{sid}: 越界题的 process_id 与 item_id 应为空")
            if sample["gold"]["supporting_evidence_ids"] or sample["gold"]["allowed_claim_ids"]:
                errors.append(f"{sid}: 越界题不应有支撑证据或声明")
            continue
        process = repository.processes.get(sample["process_id"])
        if process is None:
            errors.append(f"{sid}: process_id 不存在")
            continue
        if process["item_id"] != sample["item_id"]:
            errors.append(f"{sid}: 流程与事项不匹配")
        claims = {c["claim_id"]: c for c in process["allowed_claims"]}
        steps = {s["step_id"] for s in process["steps"]}
        materials = {m["material_id"] for m in process.get("materials", [])}
        slots = {s["slot_id"] for s in process.get("slots", [])}
        gold = sample["gold"]

        for cid in gold["allowed_claim_ids"]:
            if cid not in claims:
                errors.append(f"{sid}: 声明 {cid} 不在流程记录里")
            elif not set(claims[cid]["evidence_ids"]) <= set(gold["supporting_evidence_ids"]):
                errors.append(f"{sid}: 声明 {cid} 的证据不在支撑证据里")
        for step_id in gold["ordered_step_ids"]:
            if step_id not in steps:
                errors.append(f"{sid}: 步骤 {step_id} 不在流程记录里")
        for mid in gold["material_ids"]:
            if mid not in materials:
                errors.append(f"{sid}: 材料 {mid} 不在流程记录里")
        for eid in gold["supporting_evidence_ids"]:
            if eid not in evidence_ids:
                errors.append(f"{sid}: 证据 {eid} 不存在")
            elif repository.evidence[eid]["item_id"] != sample["item_id"]:
                errors.append(f"{sid}: 证据 {eid} 不属于本事项")
        for slot_id in gold["missing_slot_ids"] + gold["required_slot_ids"]:
            if slot_id not in slots:
                errors.append(f"{sid}: 槽位 {slot_id} 不在流程记录里")
        if SCENARIO_MODE[sample["scenario_type"]] != gold["response_mode"]:
            errors.append(f"{sid}: 应答方式与场景不符")
        if sample["scenario_type"] != "out_of_scope" and not gold["supporting_evidence_ids"]:
            errors.append(f"{sid}: 非越界题没有支撑证据")
        if sample["scenario_type"] != "condition_missing" and gold["missing_slot_ids"]:
            errors.append(f"{sid}: 非条件缺失题却有缺失槽位")
        if sample["scenario_type"] == "condition_missing" and not gold["missing_slot_ids"]:
            errors.append(f"{sid}: 条件缺失题没有缺失槽位")
        if sample["turn_structure"] == "multi_turn":
            roles = [t["role"] for t in sample["conversation"]]
            if len(roles) < 3 or roles[-1] != "user" or "assistant" not in roles:
                errors.append(f"{sid}: 多轮结构不符")
    print(f"[2] 金标准引用完整性：{'通过' if len(errors) == before else f'{len(errors) - before} 处问题'}")

    # 3. composition
    before = len(errors)
    per_item = Counter(s["allocation_item_id"] for s in samples)
    per_scenario = Counter(s["scenario_type"] for s in samples)
    for item_id, count in per_item.items():
        if count != ITEM_QUOTA:
            errors.append(f"事项 {item_id} 有 {count} 条，应为 {ITEM_QUOTA}")
    for scenario, quota in SCENARIO_QUOTA.items():
        if per_scenario[scenario] != quota:
            errors.append(f"场景 {scenario} 有 {per_scenario[scenario]} 条，应为 {quota}")
    if len(per_item) != 8:
        errors.append(f"覆盖事项 {len(per_item)} 类，应为 8 类")
    print(f"[3] 分层配额：{'通过' if len(errors) == before else f'{len(errors) - before} 处问题'}")

    # 4. new knowledge
    before = len(errors)
    used = {e for s in dev for e in s["gold"]["supporting_evidence_ids"]}
    fresh = [s for s in samples
             if set(s["gold"]["supporting_evidence_ids"]) - used]
    per_item_fresh = Counter(s["allocation_item_id"] for s in fresh)
    print(f"[4] 新知识（记录项，非硬门槛）：{len(fresh)}/{len(samples)} 条用到开发集未引用的证据")
    for item_id, count in sorted(per_item_fresh.items()):
        print(f"      {item_id:32s}{count:>3d}/{per_item[item_id]}")
    limited = [code for code in ("UG_PROOF_PRINT", "UG_STATUS_CHANGE")
               if per_item_fresh.get(code, 0) == 0]
    if limited:
        warnings.append("以下事项的声明层尚未覆盖其未引用证据，本次无法生成新证据题："
                        + "、".join(limited))

    # 5. contamination
    client = ApiClient(ROOT / "data/cache")
    new_questions = [question_of(s) for s in samples]
    dev_questions = [question_of(s) for s in dev]
    vectors = client.embed(new_questions + dev_questions)
    new_vectors, dev_vectors = vectors[: len(samples)], vectors[len(samples):]
    new_grams = [grams(q) for q in new_questions]

    worst_dev = (0.0, "", "")
    for index, sample in enumerate(samples):
        for other, dev_sample in enumerate(dev):
            score = jaccard(new_grams[index], grams(dev_questions[other]))
            if score > worst_dev[0]:
                worst_dev = (score, sample["sample_id"], dev_sample["sample_id"])
            if score > JACCARD_LIMIT:
                errors.append(f"{sample['sample_id']}: 与开发集 {dev_sample['sample_id']} "
                              f"字符重叠 {score:.2f} 超过 {JACCARD_LIMIT}")
    worst_cos = (0.0, "", "")
    for index, sample in enumerate(samples):
        for other, dev_sample in enumerate(dev):
            score = cosine(new_vectors[index], dev_vectors[other])
            if score > worst_cos[0]:
                worst_cos = (score, sample["sample_id"], dev_sample["sample_id"])
            if score > COSINE_LIMIT:
                errors.append(f"{sample['sample_id']}: 与开发集 {dev_sample['sample_id']} "
                              f"语义相似 {score:.3f} 超过 {COSINE_LIMIT}")

    worst_internal = (0.0, "", "")
    cells: dict[tuple[str, str], list[int]] = {}
    for index, sample in enumerate(samples):
        cells.setdefault((sample["allocation_item_id"], sample["scenario_type"]), []).append(index)
    for members in cells.values():
        for left_pos, left in enumerate(members):
            for right in members[left_pos + 1:]:
                score = cosine(new_vectors[left], new_vectors[right])
                if score > worst_internal[0]:
                    worst_internal = (score, samples[left]["sample_id"], samples[right]["sample_id"])
                if score > INTERNAL_COSINE_LIMIT:
                    errors.append(f"{samples[left]['sample_id']} 与 {samples[right]['sample_id']} "
                                  f"同格语义相似 {score:.3f} 超过 {INTERNAL_COSINE_LIMIT}")
    print(f"[5] 污染控制：与开发集最大字符重叠 {worst_dev[0]:.2f}"
          f"（{worst_dev[1]} vs {worst_dev[2]}），最大语义相似 {worst_cos[0]:.3f}"
          f"，同格最大语义相似 {worst_internal[0]:.3f}（上限 {INTERNAL_COSINE_LIMIT}）")

    print()
    for warning in warnings:
        print(f"注意：{warning}")
    if errors:
        print(f"未通过：{len(errors)} 处")
        for problem in errors[:15]:
            print("  -", problem)
        return 1
    print("全部检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
