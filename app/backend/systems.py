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
    """Parse the model's JSON reply, tolerating a malformed reply.

    Only a malformed reply is tolerated (ValueError). Transport and quota errors
    (`ApiError`, a RuntimeError) must propagate: swallowing them turns an outage
    into an empty answer that then gets scored, so the run looks like the system
    failed on those items while the failure list stays empty.
    """
    try:
        return client.chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
    except ValueError:
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

BASELINE_C_USER = """【证据】
{evidence}

【问题】
{question}

输出 JSON：
{{"key_points": [{{"text": "要点", "evidence_ids": ["证据编号"]}}],
 "answer": "基于要点的完整回答，关键结论后附 [证据编号]"}}"""


def baseline_c(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    data = _json_or_empty(client, BASELINE_C_SYSTEM,
                          BASELINE_C_USER.format(evidence=evidence_block(evidence),
                                                 question=question))
    answer = answer_of(data)
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

MODE_GUIDE_INTRO = "先判定响应方式，再作答（response_mode 必填）："
MODE_GUIDE_BULLETS = (
    ("answer", "answer：条件完整，且提问的前提与证据的适用范围一致。"),
    ("scoped_correction",
     "scoped_correction：提问中的对象、步骤或材料前提与证据的适用范围不符（例如把研究生当成本科生、\n"
     "  按已不适用的步骤办理、把两种材料各自的适用条件混在一起），必须先明确指出哪一部分不适用，\n"
     "  再给出适用于正确对象或条件的回答。"),
    ("clarification",
     "clarification：问题缺少会改变答案的关键条件（对象、学历层次、学籍状态、时间等），必须先问清楚。"),
    ("version_qualified",
     "version_qualified：证据中同一事项存在不同版本且互相矛盾，或问题涉及未经正式文件确认的新版本；\n"
     "  此时说明依据的是哪个来源版本，并明确未获证据确认的部分不能当事实。"),
    ("conversation_resolution",
     "conversation_resolution：多轮对话，需先合并前一轮遗留的条件或指代，再作答。"),
    ("abstention", "abstention：证据中没有任何内容能回答该问题。"),
)
MODE_GUIDE_FOOTER = "不要为了回避而滥用 clarification 或 abstention；也不要把前提不符当成 answer 直接作答。"

ALL_MODE_NAMES = tuple(key for key, _ in MODE_GUIDE_BULLETS)
MODE_OPTIONS = " | ".join(ALL_MODE_NAMES)


def build_mode_guide(drop: tuple[str, ...] = ()) -> tuple[str, str]:
    """Compose the response-mode guide and its option list.

    ``drop`` removes whole response modes, which is how the registered ablations
    ("without version qualification") switch a single component off while every
    other prompt stays identical.
    """
    bullets = [text for key, text in MODE_GUIDE_BULLETS if key not in drop]
    names = [key for key, _ in MODE_GUIDE_BULLETS if key not in drop]
    footer = MODE_GUIDE_FOOTER
    if {"clarification", "abstention"} <= set(drop):
        footer = "不要把前提不符当成 answer 直接作答。"
    return "\n".join([MODE_GUIDE_INTRO, *(f"- {text}" for text in bullets), footer]), " | ".join(names)


MODE_GUIDE, MODE_OPTIONS_DEFAULT = build_mode_guide()

METHOD_USER = """【流程骨架】
{skeleton}

【证据】
{evidence}

【问题】
{question}

{mode_guide}

输出 JSON：
{{
  "item": "事项名称；无法判断则空串",
  "response_mode": "answer | scoped_correction | clarification | version_qualified | conversation_resolution | abstention",
  "missing_conditions": ["问题中没有交代、但会改变答案的关键条件"],
  "follow_up_question": "需要追问时的问题；否则 null",
  "key_points": [{{"text": "逐条精读证据整理出的与问题相关的要点", "evidence_ids": ["证据编号"]}}],
  "answer": "基于 key_points 的完整回答；每条实质性结论后附 [证据编号]",
  "conflicts": [{{"text": "证据之间对同一事实的互相矛盾之处", "evidence_ids": []}}],
  "dropped": ["因证据不足而未写入回答的内容"]
}}"""

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

KNOWN_MODES = {"answer", "scoped_correction", "clarification", "version_qualified",
               "conversation_resolution", "abstention"}


def _skeleton_text(skeleton: Any) -> str:
    """Render the extracted skeleton for a prompt; ``None`` means it is withheld."""
    if skeleton is None:
        return "（本次未使用流程骨架）"
    return "\n".join(
        f"- {kind}: " + "; ".join(
            (element.get("text") or "") + f" {element.get('evidence_ids') or []}"
            for element in skeleton.get(kind, [])
        )
        for kind in ("steps", "conditions", "materials", "time_constraints", "entries")
    ) or "（未抽取到要素）"


def _method_pass(client: Any, question: str, evidence: Sequence[dict], skeleton: Any,
                 *, verify: bool) -> Prediction:
    allowed = {row["evidence_id"] for row in evidence}
    data = _json_or_empty(client, METHOD_SYSTEM, METHOD_USER.format(
        skeleton=_skeleton_text(skeleton), evidence=evidence_block(evidence),
        question=question, mode_guide=MODE_GUIDE), 2000)

    draft = answer_of(data)
    mode = str(data.get("response_mode") or "answer")
    mode = mode if mode in KNOWN_MODES else "answer"
    missing = [str(m) for m in (data.get("missing_conditions") or []) if str(m).strip()]
    follow_up = data.get("follow_up_question")
    follow_up = str(follow_up) if follow_up else None

    # Assertion-level verification, then re-collect citations from what survived.
    final = draft
    if verify and draft and mode in {"answer", "scoped_correction", "version_qualified"}:
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


def method(client: Any, question: str, evidence: Sequence[dict], skeleton: dict) -> Prediction:
    return _method_pass(client, question, evidence, skeleton, verify=True)


def ablation_no_skeleton(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    """Identical to `method` except the flow skeleton is withheld.

    ``ablation_no_flow`` also drops the skeleton, but it generates in baseline C's
    two-step style, so it confounds "no skeleton" with "different prompt shape".
    This one holds every other part of the method's prompt fixed.
    """
    return _method_pass(client, question, evidence, None, verify=True)


MODE_ONLY_SYSTEM = (
    "你是校园办事问答的交互控制模块。只判定本次应当采用哪种响应方式，不写回答内容。"
)

MODE_ONLY_USER = """【流程骨架】
{skeleton}

【证据】
{evidence}

【问题】
{question}

{mode_guide}

只做判定，不写回答。输出 JSON：
{{
  "response_mode": "{mode_options}",
  "missing_conditions": ["问题中没有交代、但会改变答案的关键条件"],
  "follow_up_question": "需要追问时的问题；否则 null"
}}"""


def _skeleton_text(skeleton: Any) -> str:
    if skeleton is None:
        return "（本次未使用流程骨架）"
    return "\n".join(
        f"- {kind}: " + "; ".join(
            (element.get("text") or "") + f" {element.get('evidence_ids') or []}"
            for element in skeleton.get(kind, [])
        )
        for kind in ("steps", "conditions", "materials", "time_constraints", "entries")
    ) or "（未抽取到要素）"


def method_v2(client: Any, question: str, evidence: Sequence[dict], skeleton: dict) -> Prediction:
    """Flow skeleton drives the interaction decision, not the answer text.

    `method` dumps the skeleton into the generation prompt, where it measurably
    hurts. Here the skeleton is read once to decide the response mode; the answer
    is then generated in the same two-step style every other configuration uses,
    without the skeleton in the prompt.
    """
    return _v2_pass(client, question, evidence, skeleton, verify="weak")


def ablation_no_verify(client: Any, question: str, evidence: Sequence[dict],
                       skeleton: dict) -> Prediction:
    """Original method design minus assertion verification: isolates H2 there."""
    return _method_pass(client, question, evidence, skeleton, verify=False)


# ------------------------------------------- claim-level (strong form) verification

CLAIM_VERIFY_SYSTEM = (
    "你是断言级核验员。把【草稿回答】拆成互不重叠的原子断言，逐条判定它是否被【证据】直接支持。"
    "判定只看证据中是否有文字能直接支撑该断言，不使用你自己的常识补充。"
)

CLAIM_VERIFY_USER = """【证据】
{evidence}

【草稿回答】
{draft}

输出 JSON：
{{"claims": [
  {{"text": "原子断言的原文",
    "verdict": "supported | partial | unsupported",
    "evidence_ids": ["直接支撑该断言的证据编号"]}}
]}}

要求：
- 把草稿拆成原子断言，一条只讲一件事；合并重复的表述。
- verdict=supported 仅当证据中有文字能直接支撑它；只是常识上说得通、或需要从证据外推的，判 partial 或 unsupported。
- 每条 supported 的断言必须给出至少一个证据编号；给不出证据编号的按 unsupported 处理。
- 不要新增草稿中不存在的内容，也不要改写断言的意思。"""

CITATION_PATTERN = re.compile(r"\[(UG[A-Z]+\d+)\]")
SENTENCE_END = ("。", "；", "！", "？", ".", ";", "!", "?")

# Emitted when the assertion check runs and finds nothing it can stand behind.
NO_SUPPORTED_CLAIM_NOTE = "（核验后没有留下可由证据直接支持的断言。）"


def _join_points(points: Any) -> str:
    """Render a reply's `key_points` back into prose, in order."""
    if not isinstance(points, list):
        return ""
    parts: list[str] = []
    for point in points:
        text = (str(point.get("text") or "") if isinstance(point, dict)
                else str(point or "")).strip()
        if not text:
            continue
        parts.append(text if text.endswith(SENTENCE_END) else text + "。")
    return "".join(parts)


def answer_of(data: dict) -> str:
    """Read the answer out of a structured reply, tolerating one model habit.

    The prompts ask for both `key_points` (the close reading) and `answer` (the
    prose built from them). Models occasionally fill `key_points` with answer
    prose and omit `answer` altogether; the reply is then complete and valid but
    the answer field is empty. Reading only `answer` turns that into an empty
    response, which the runner has to treat as a failure — a formatting slip
    becomes a missing answer and silently depresses the configuration's score.
    The content is present, so it is read from `key_points` instead.

    This applies to every configuration, so it cannot advantage one of them.
    """
    answer = str(data.get("answer") or "").strip()
    return answer or _join_points(data.get("key_points"))


def _rebuild_from_claims(claims: Sequence[Any], allowed: set[str]) -> str:
    """Keep only assertions the retrieved evidence supports, in their original order.

    Recomposition is deterministic: the model is never asked to rewrite the answer,
    so a dropped assertion cannot reappear in a paraphrase. Every surviving
    assertion carries the evidence ids that were checked against it.
    """
    lines: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        if str(claim.get("verdict") or "").strip() != "supported":
            continue
        body = CITATION_PATTERN.sub("", str(claim.get("text") or "")).strip()
        if not body:
            continue
        ids: list[str] = []
        for identity in claim.get("evidence_ids") or []:
            identity = str(identity)
            if identity in allowed and identity not in ids:
                ids.append(identity)
        if not ids:
            continue
        closing = "" if body.endswith(SENTENCE_END) else "。"
        lines.append(body + closing + "".join(f"[{i}]" for i in ids))
    return "\n".join(lines)


def verify_claims(client: Any, evidence: Sequence[dict], draft: str) -> str:
    """Strong form of assertion verification.

    Returns the rebuilt answer. Falls back to the draft only when the check could
    not be run at all (unparsable reply, or no assertions reported), never when it
    ran and found claims unsupported.

    When the check runs and no assertion survives, the reply says so instead of
    being empty: an empty answer is indistinguishable from a failed call, and the
    runner would record a deliberate result as an outage.
    """
    allowed = {row["evidence_id"] for row in evidence}
    data = _json_or_empty(client, CLAIM_VERIFY_SYSTEM, CLAIM_VERIFY_USER.format(
        evidence=evidence_block(evidence), draft=draft), 2000)
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        return draft
    return _rebuild_from_claims(claims, allowed) or NO_SUPPORTED_CLAIM_NOTE


def _v2_pass(client: Any, question: str, evidence: Sequence[dict], skeleton: Any,
             *, verify: str | None, drop_modes: tuple[str, ...] = ()) -> Prediction:
    """The v2 design with a switchable verification stage.

    ``verify`` is ``None`` (no verification), ``"weak"`` (the model deletes
    unsupported sentences) or ``"strong"`` (assertions are checked one by one and
    the answer is rebuilt deterministically from those that passed). Holding the
    decision, retrieval and generation prompts fixed while varying only this
    switch is what makes the verification contrast interpretable.

    ``drop_modes`` removes whole response modes from the interaction guide, which
    is how "without version qualification" is switched off while everything else
    in the prompt stays byte-identical.
    """
    allowed = {row["evidence_id"] for row in evidence}
    skeleton_text = _skeleton_text(skeleton)
    mode_guide, mode_options = build_mode_guide(drop_modes)

    decision = _json_or_empty(client, MODE_ONLY_SYSTEM, MODE_ONLY_USER.format(
        skeleton=skeleton_text, evidence=evidence_block(evidence), question=question,
        mode_guide=mode_guide, mode_options=mode_options), 800)
    mode = str(decision.get("response_mode") or "answer")
    mode = mode if mode in KNOWN_MODES and mode not in drop_modes else "answer"
    missing = [str(m) for m in (decision.get("missing_conditions") or []) if str(m).strip()]
    follow_up = decision.get("follow_up_question")
    follow_up = str(follow_up) if follow_up else None

    data = _json_or_empty(client, BASELINE_C_SYSTEM, BASELINE_C_USER.format(
        evidence=evidence_block(evidence), question=question), 2000)
    draft = answer_of(data)
    final = draft
    verifiable = draft and mode in {"answer", "scoped_correction", "version_qualified"}
    if verifiable and verify == "weak":
        verified = _json_or_empty(client, VERIFY_SYSTEM, VERIFY_USER.format(
            evidence=evidence_block(evidence), draft=draft), 1600)
        candidate = str(verified.get("final_answer") or "").strip()
        if candidate:
            final = candidate
    elif verifiable and verify == "strong":
        final = verify_claims(client, evidence, draft)

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


def method_v3(client: Any, question: str, evidence: Sequence[dict], skeleton: dict) -> Prediction:
    """v2 design with the strong form of assertion verification."""
    return _v2_pass(client, question, evidence, skeleton, verify="strong")


def ablation_v2_no_verify(client: Any, question: str, evidence: Sequence[dict],
                          skeleton: dict) -> Prediction:
    """v2 design minus verification: the clean floor for the H2 contrast."""
    return _v2_pass(client, question, evidence, skeleton, verify=None)


def ablation_v2_no_skeleton(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    """v2 design minus the skeleton: the clean floor for the H1 contrast."""
    return _v2_pass(client, question, evidence, None, verify="weak")


def ablation_no_version_limit(client: Any, question: str, evidence: Sequence[dict],
                              skeleton: dict) -> Prediction:
    """v2 design minus version qualification: the contrast for the version rule.

    Everything else — retrieval, skeleton, generation, verification — is
    identical to `method_v2`; only the version_qualified mode is withheld.
    """
    return _v2_pass(client, question, evidence, skeleton, verify="weak",
                    drop_modes=("version_qualified",))


# ------------------------------------------------- ablation: interaction control only

ABLATION_NO_FLOW_SYSTEM = (
    BASE_SYSTEM
    + " 采用两步作答：第一步逐条精读证据，整理出与问题相关的要点；"
      "第二步基于这些要点给出面向办事的回答。"
      " 回答必须保留 [证据编号] 标注。\n\n"
    + MODE_GUIDE
)

ABLATION_NO_FLOW_USER = """【证据】
{evidence}

【问题】
{question}

{mode_guide}

输出 JSON：
{{
  "response_mode": "answer | scoped_correction | clarification | version_qualified | conversation_resolution | abstention",
  "missing_conditions": ["问题中没有交代、但会改变答案的关键条件"],
  "follow_up_question": "需要追问时的问题；否则 null",
  "key_points": [{{"text": "要点", "evidence_ids": ["证据编号"]}}],
  "answer": "基于要点的完整回答，关键结论后附 [证据编号]"
}}"""


def ablation_no_flow(client: Any, question: str, evidence: Sequence[dict]) -> Prediction:
    """Baseline C's generation plus the same interaction control, without the flow
    skeleton and without assertion verification. This is the control that separates
    "flow-aware machinery" from "merely having a response-mode decision at all"."""
    data = _json_or_empty(client, ABLATION_NO_FLOW_SYSTEM, ABLATION_NO_FLOW_USER.format(
        evidence=evidence_block(evidence), question=question, mode_guide=MODE_GUIDE), 2000)
    answer = answer_of(data)
    mode = str(data.get("response_mode") or "answer")
    mode = mode if mode in KNOWN_MODES else "answer"
    missing = [str(m) for m in (data.get("missing_conditions") or []) if str(m).strip()]
    follow_up = data.get("follow_up_question")
    follow_up = str(follow_up) if follow_up else None
    allowed = {row["evidence_id"] for row in evidence}
    prefix = f"{follow_up}\n" if follow_up else ""
    return Prediction(
        answer_text=prefix + answer,
        response_mode=mode,
        retrieved_evidence_ids=sorted(allowed),
        citations=cited_ids(prefix + answer, allowed) or cited_ids(str(data.get("key_points")), allowed),
        missing_slot_ids=missing,
        follow_up_question=follow_up,
        item_id=None,
    )


SYSTEMS = {
    "baseline_a": baseline_a,
    "baseline_b": baseline_b,
    "baseline_c": baseline_c,
    "ablation_no_flow": ablation_no_flow,
    "ablation_no_verify": ablation_no_verify,
    "ablation_no_skeleton": ablation_no_skeleton,
    "ablation_v2_no_verify": ablation_v2_no_verify,
    "ablation_v2_no_skeleton": ablation_v2_no_skeleton,
    "ablation_no_version_limit": ablation_no_version_limit,
    "method_v2": method_v2,
    "method_v3": method_v3,
    "method": method,
}
