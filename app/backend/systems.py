"""The four systems under comparison.

Every system receives the same things: the user question and the evidence this
run retrieved. None of them receives a sample id, an item label, a process id,
or any gold field. The only differences are the method's own machinery, which is
exactly what the申报书 wants to compare.

* ``baseline_a`` - vector retrieval + direct generation (the plainest RAG)
* ``baseline_b`` - hybrid retrieval + rerank + explicit citations
* ``baseline_c`` - restricted workflow: retrieve, read closely, organise, then answer
* ``method``    - flow skeleton + assertion verification + interaction control
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from .scoring_v2 import Prediction

EVIDENCE_ID_PATTERN = re.compile(r"\b(UG[A-Z]+\d+)\b")
ANSWER_MODES = {"answer", "clarification", "version_qualified", "abstention",
                "conversation_resolution"}

BASE_SYSTEM = (
    "你是校园办事问答助手。只依据【证据】中的文字回答，"
    "不得使用证据之外的任何信息，也不要凭常识补充。"
)


def evidence_block(rows: Sequence[dict]) -> str:
    if not rows:
        return "（无）"
    return "\n".join(
        f"[{row['evidence_id']}] {row.get('normalized_claim', '')}\n"
        f"    原文：{row.get('verbatim_text', '')}"
        for row in rows
    )


def cited_ids(text: str, allowed: set[str]) -> list[str]:
    found = [i for i in EVIDENCE_ID_PATTERN.findall(text)]
    seen: list[str] = []
    for identity in found:
        if identity in allowed and identity not in seen:
            seen.append(identity)
    return seen


def _chat(client: Any, system: str, user: str, max_tokens: int = 1200) -> str:
    return client.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=max_tokens,
    )


def _json_or_empty(client: Any, system: str, user: str, max_tokens: int = 1600) -> dict:
    try:
        return client.chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
    except (ValueError, RuntimeError):
        return {}


# --------------------------------------------------------------- baseline A

def baseline_a(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    user = (f"【证据】\n{evidence_block(evidence)}\n\n【问题】\n{question}\n\n"
            "请直接回答问题。")
    answer = _chat(client, BASE_SYSTEM, user)
    allowed = {row["evidence_id"] for row in evidence}
    return Prediction(
        answer_text=answer,
        response_mode="answer",
        retrieved_evidence_ids=sorted(allowed),
        citations=cited_ids(answer, allowed),
        item_id=None,
    )


# --------------------------------------------------------------- baseline B

BASELINE_B_SYSTEM = (
    BASE_SYSTEM
    + " 回答中的每一条实质性结论都必须在其后紧跟方括号形式的来源证据编号，例如 [UGP001]；"
      "没有证据支持的结论不要写。"
)


def baseline_b(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    user = (f"【证据】\n{evidence_block(evidence)}\n\n【问题】\n{question}\n\n"
            "请回答问题，并逐条标注来源证据编号。")
    answer = _chat(client, BASELINE_B_SYSTEM, user)
    allowed = {row["evidence_id"] for row in evidence}
    return Prediction(
        answer_text=answer,
        response_mode="answer",
        retrieved_evidence_ids=sorted(allowed),
        citations=cited_ids(answer, allowed),
        item_id=None,
    )


# --------------------------------------------------------------- baseline C

BASELINE_C_SYSTEM = (
    BASE_SYSTEM
    + " 采用两步作答：第一步逐条精读证据，整理出与问题相关的要点；"
      "第二步基于这些要点给出面向办事的回答。"
)


def baseline_c(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    user = (f"【证据】\n{evidence_block(evidence)}\n\n【问题】\n{question}\n\n"
            "输出 JSON：\n"
            '{"key_points": [{"text": "要点", "evidence_ids": ["证据编号"]}],'
            ' "answer": "基于要点的完整回答，关键结论后附 [证据编号]"}')
    data = _json_or_empty(client, BASELINE_C_SYSTEM, user)
    answer = str(data.get("answer") or "")
    allowed = {row["evidence_id"] for row in evidence}
    return Prediction(
        answer_text=answer,
        response_mode="answer",
        retrieved_evidence_ids=sorted(allowed),
        citations=cited_ids(answer, allowed) or cited_ids(str(data.get("key_points")), allowed),
        item_id=None,
    )


# ------------------------------------------------------------------ method

METHOD_SYSTEM = (
    BASE_SYSTEM
    + " 你还会收到一份由证据抽取的【流程骨架】，它是本次回答的结构依据。"
      "回答必须按「适用对象—办理步骤—所需材料—时间要求—办理入口」组织。"
)

METHOD_USER = """【流程骨架】
{skeleton}

【证据】
{evidence}

【问题】
{question}

请按以下规则作答，并输出 JSON：
{{
  "item": "事项名称；无法判断则空串",
  "response_mode": "answer | clarification | version_qualified | abstention",
  "missing_conditions": ["问题中没有交代、但会改变答案的关键条件"],
  "follow_up_question": "需要追问时的问题；否则 null",
  "answer": "完整回答；每条实质性结论后附 [证据编号]",
  "conflicts": [{{"text": "证据之间对同一事实的互相矛盾之处", "evidence_ids": []}}],
  "dropped": ["因证据不足而未写入回答的内容"]
}}

判定应使用的响应方式：
- clarification：问题缺少会改变答案的关键条件（对象、学历层次、学籍状态、时间等），
  必须先问清楚。
- version_qualified：证据中同一事项存在不同版本且互相矛盾，或问题涉及未经正式文件确认的新版本；
  此时说明依据的是哪个来源版本，并明确未获证据确认的部分不能当事实。
- abstention：证据中没有任何内容能回答该问题。
- answer：其余情况。
不要为了回避而滥用 clarification 或 abstention。"""

VERIFY_SYSTEM = (
    "你是严格的核验员。逐条检查【草稿回答】中的实质性结论是否被【证据】支持，"
    "删除没有证据支持的结论，保留其余内容，输出修订后的回答。"
)

VERIFY_USER = """【证据】
{evidence}

【草稿回答】
{draft}

输出 JSON：
{{"kept": ["保留的结论"], "removed": ["因无证据支持而删除的结论"],
 "final_answer": "修订后的完整回答，保留原有 [证据编号] 标注"}}"""

KNOWN_MODES = {"answer", "clarification", "version_qualified", "abstention"}


def method(client: Any, question: str, evidence: Sequence[dict], skeleton: dict) -> Prediction:
    allowed = {row["evidence_id"] for row in evidence}
    skeleton_text = "\n".join(
        f"- {kind}: " + "; ".join(
            (element.get("text") or "") + f" {element.get('evidence_ids') or []}"
            for element in skeleton.get(kind, [])
        )
        for kind in ("steps", "conditions", "materials", "time_constraints", "entries")
    ) or "（未抽取到要素）"

    data = _json_or_empty(client, METHOD_SYSTEM, METHOD_USER.format(
        skeleton=skeleton_text, evidence=evidence_block(evidence), question=question), 2000)

    draft = str(data.get("answer") or "")
    mode = str(data.get("response_mode") or "answer")
    mode = mode if mode in KNOWN_MODES else "answer"
    missing = [str(m) for m in (data.get("missing_conditions") or []) if str(m).strip()]
    follow_up = data.get("follow_up_question")
    follow_up = str(follow_up) if follow_up else None

    # Assertion-level verification, then re-collect citations from what survived.
    final = draft
    if draft and mode in {"answer", "version_qualified"}:
        verified = _json_or_empty(client, VERIFY_SYSTEM, VERIFY_USER.format(
            evidence=evidence_block(evidence), draft=draft), 1600)
        candidate = str(verified.get("final_answer") or "").strip()
        if candidate:
            final = candidate

    prefix = f"{follow_up}\n" if follow_up else ""
    return Prediction(
        answer_text=prefix + final,
        response_mode=mode,
        retrieved_evidence_ids=sorted(allowed),
        citations=cited_ids(prefix + final, allowed),
        missing_slot_ids=missing,
        follow_up_question=follow_up,
        item_id=None,
    )


SYSTEMS = {
    "baseline_a": baseline_a,
    "baseline_b": baseline_b,
    "baseline_c": baseline_c,
}
