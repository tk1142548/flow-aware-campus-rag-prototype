"""Extract a lightweight process skeleton from retrieved evidence.

This is the piece the申报书 stage 3 actually asked for and the repository never
had: the earlier "流程中间表示" was hand-annotated and then read back at
inference time, which is not extraction. Here the model receives only the user
question and the evidence this run retrieved, and must produce the five element
kinds, each bound to the evidence ids it used.

The hand-annotated process records stay on the evaluation side as gold.
"""
from __future__ import annotations

import json
from typing import Any, Sequence

ELEMENT_KINDS = ("steps", "conditions", "materials", "time_constraints", "entries")

SYSTEM = (
    "你是校园办事流程信息抽取器。只依据【证据】中出现的文字抽取流程要素，"
    "不得使用你自己的常识补充任何未在证据中出现的信息。"
    "每条要素都必须给出来源证据编号。证据不足时宁可少抽，不要编。"
)

USER_TEMPLATE = """【用户问题】
{question}

【本次检索到的证据】
{evidence}

请抽取面向该问题的办事流程骨架，输出 JSON：
{{
  "item": "你判断的事项名称；无法判断则空串",
  "steps": [{{"order": 1, "action": "办理动作，含办理主体", "evidence_ids": ["证据编号"]}}],
  "conditions": [{{"text": "适用条件（对象/学历层次/年级/学籍状态等）", "evidence_ids": ["证据编号"]}}],
  "materials": [{{"name": "所需材料名称", "evidence_ids": ["证据编号"]}}],
  "time_constraints": [{{"text": "时间或期限要求", "evidence_ids": ["证据编号"]}}],
  "entries": [{{"text": "办理入口、部门或地点", "evidence_ids": ["证据编号"]}}],
  "conflicts": [{{"text": "证据之间互相矛盾之处；没有则空数组", "evidence_ids": ["证据编号"]}}],
  "insufficient": false
}}

约束：
- steps 必须按真实办理先后排序。
- 每条 evidence_ids 只能取自【证据】中出现的编号，不得新增。
- 如果证据中没有任何与问题相关的内容，把 insufficient 设为 true 并让各数组为空。
- 只输出 JSON，不要解释。"""


def format_evidence(rows: Sequence[dict]) -> str:
    blocks = []
    for row in rows:
        claim = row.get("normalized_claim") or ""
        verbatim = row.get("verbatim_text") or ""
        blocks.append(f"[{row['evidence_id']}] {claim}\n    原文：{verbatim}")
    return "\n".join(blocks) if blocks else "（无）"


def empty_skeleton(reason: str = "") -> dict:
    skeleton = {"item": "", "insufficient": True, "reason": reason}
    for kind in ELEMENT_KINDS:
        skeleton[kind] = []
    skeleton["conflicts"] = []
    return skeleton


def normalise(raw: Any) -> dict:
    """Coerce a model reply into the skeleton contract."""
    if not isinstance(raw, dict):
        return empty_skeleton("reply was not an object")
    out = {
        "item": str(raw.get("item") or ""),
        "insufficient": bool(raw.get("insufficient", False)),
        "reason": "",
    }
    for kind in ELEMENT_KINDS:
        items = raw.get(kind) or []
        cleaned = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = item.get("action") or item.get("text") or item.get("name") or ""
                text = str(text).strip()
                if not text:
                    continue
                ids = item.get("evidence_ids") or []
                ids = [str(i) for i in ids if isinstance(i, (str, int))]
                entry = {"text": text, "evidence_ids": ids}
                if kind == "steps":
                    try:
                        entry["order"] = int(item.get("order") or len(cleaned) + 1)
                    except (TypeError, ValueError):
                        entry["order"] = len(cleaned) + 1
                cleaned.append(entry)
        out[kind] = cleaned
    conflicts = raw.get("conflicts") or []
    out["conflicts"] = [
        {"text": str(c.get("text", "")).strip(),
         "evidence_ids": [str(i) for i in (c.get("evidence_ids") or [])]}
        for c in conflicts if isinstance(c, dict) and c.get("text")
    ] if isinstance(conflicts, list) else []
    if out["steps"]:
        out["steps"].sort(key=lambda s: s["order"])
    return out


def extract(client: Any, question: str, evidence_rows: Sequence[dict]) -> dict:
    """Extract a skeleton from the evidence retrieved for this question."""
    if not evidence_rows:
        return empty_skeleton("no evidence retrieved")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER_TEMPLATE.format(
            question=question, evidence=format_evidence(evidence_rows))},
    ]
    reply = client.chat(messages, temperature=0.0, max_tokens=2000)
    try:
        raw = json.loads(reply[reply.find("{"): reply.rfind("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return empty_skeleton("reply was not parseable JSON")
    return normalise(raw)


def binding_validity(skeleton: dict, allowed_ids: set[str]) -> dict:
    """Every extracted element must cite evidence from this run's retrieved set."""
    total = 0
    bound = 0
    invented: list[str] = []
    for kind in ELEMENT_KINDS:
        for element in skeleton.get(kind, []):
            total += 1
            ids = set(element.get("evidence_ids") or [])
            if ids and ids <= allowed_ids:
                bound += 1
            elif ids:
                invented.extend(sorted(ids - allowed_ids))
    return {
        "elements": total,
        "bound_to_retrieved": bound,
        "binding_rate": (bound / total) if total else 1.0,
        "invented_evidence_ids": sorted(set(invented)),
    }


def order_consistency(extracted_steps: Sequence[dict], gold_order: Sequence[str],
                      gold_text_by_id: dict[str, str]) -> float:
    """Kendall-tau-like agreement between extracted step order and gold order.

    Steps are matched to gold by best text overlap; unmatched extracted steps are
    ignored so the score reflects ordering, not recall.
    """
    if not extracted_steps or not gold_order:
        return 1.0
    gold_rank = {sid: rank for rank, sid in enumerate(gold_order)}
    observed: list[tuple[int, int]] = []
    for position, step in enumerate(extracted_steps):
        best_id, best_score = None, 0.0
        from .scoring_v2 import lexical_containment

        for sid in gold_order:
            score = lexical_containment(step["text"], gold_text_by_id[sid])
            if score > best_score:
                best_id, best_score = sid, score
        if best_id and best_score >= 0.3:
            observed.append((gold_rank[best_id], position))
    if len(observed) < 2:
        return 1.0
    concordant = discordant = 0
    for i in range(len(observed)):
        for j in range(i + 1, len(observed)):
            delta_gold = observed[i][0] - observed[j][0]
            delta_pos = observed[i][1] - observed[j][1]
            if delta_gold * delta_pos > 0:
                concordant += 1
            elif delta_gold * delta_pos < 0:
                discordant += 1
    total = concordant + discordant
    return (concordant / total) if total else 1.0
