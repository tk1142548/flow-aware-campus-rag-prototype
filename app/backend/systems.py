"""The systems under comparison.

Every system receives the same things: the conversation and the evidence this run
retrieved. None of them receives a sample id, an item label, a process id, or any
gold field.

* ``baseline_a``        vector retrieval + direct answer
* ``baseline_b``        hybrid retrieval + rerank + explicit citations
* ``baseline_c``        baseline B's retrieval + close reading, then answer
* ``interaction``       baseline C + response-mode decision          (H3 vs baseline_c)
* ``full``              interaction + flow skeleton + claim verification
* ``full_no_skeleton``  full minus the skeleton                       (H1 vs full)
* ``full_no_verify``    full minus claim verification                 (H2 vs full)

``interaction`` and the three ``full*`` configurations share one pipeline whose
three components are switched independently, so each paired comparison differs in
exactly one component.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from .prompting import conversation_block, evidence_block
from .scoring_v2 import Prediction

EVIDENCE_ID_PATTERN = re.compile(r"\b(UG[A-Z]+\d+)\b")
CITATION_PATTERN = re.compile(r"\[(UG[A-Z]+\d+)\]")
SENTENCE_END = ("。", "；", "！", "？", ".", ";", "!", "?")

KNOWN_MODES = ("answer", "scoped_correction", "clarification", "version_qualified",
               "conversation_resolution", "abstention")
CONTENT_MODES = {"answer", "scoped_correction", "version_qualified", "conversation_resolution"}

BASE_SYSTEM = (
    "你是校园办事问答助手。只依据【证据】中的文字回答，"
    "不得使用证据之外的任何信息，也不要凭常识补充。"
)


# ------------------------------------------------------------------ helpers

def cited_ids(text: str, allowed: set[str]) -> list[str]:
    seen: list[str] = []
    for identity in EVIDENCE_ID_PATTERN.findall(text):
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
    must propagate: swallowing them turns an outage into an empty answer that then
    gets scored as if the system had failed.
    """
    try:
        value = client.chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _join_points(points: Any) -> str:
    """Render a reply's `key_points` back into prose, in order."""
    if not isinstance(points, list):
        return ""
    parts: list[str] = []
    for point in points:
        text = (str(point.get("text") or "") if isinstance(point, dict)
                else str(point or "")).strip()
        if text:
            parts.append(text if text.endswith(SENTENCE_END) else text + "。")
    return "".join(parts)


def answer_of(data: dict) -> str:
    """Read the answer out of a structured reply.

    Models occasionally put the answer prose under `key_points` and leave `answer`
    empty. The content is present, so it is read from there rather than being
    scored as a missing answer. This applies to every configuration alike.
    """
    answer = str(data.get("answer") or "").strip()
    return answer or _join_points(data.get("key_points"))


def _prediction(answer: str, evidence: Sequence[dict], *, mode: str = "answer",
                missing: Sequence[str] = (), follow_up: str | None = None) -> Prediction:
    allowed = {row["evidence_id"] for row in evidence}
    text = f"{follow_up}\n{answer}" if follow_up else answer
    return Prediction(
        answer_text=text.strip(),
        response_mode=mode,
        retrieved_evidence_ids=sorted(allowed),
        citations=cited_ids(text, allowed),
        missing_slot_ids=list(missing),
        follow_up_question=follow_up,
        item_id=None,
    )


# ---------------------------------------------------------------- baselines

def baseline_a(client: Any, turns: Sequence[dict], evidence: Sequence[dict]) -> Prediction:
    user = (f"【证据】\n{evidence_block(evidence)}\n\n【问题】\n{conversation_block(turns)}\n\n"
            "请直接回答问题。")
    return _prediction(_chat(client, BASE_SYSTEM, user), evidence)


BASELINE_B_SYSTEM = (
    BASE_SYSTEM
    + " 回答中的每一条实质性结论都必须在其后紧跟方括号形式的来源证据编号，例如 [UGP001]；"
      "没有证据支持的结论不要写。"
)


def baseline_b(client: Any, turns: Sequence[dict], evidence: Sequence[dict]) -> Prediction:
    user = (f"【证据】\n{evidence_block(evidence)}\n\n【问题】\n{conversation_block(turns)}\n\n"
            "请回答问题，并逐条标注来源证据编号。")
    return _prediction(_chat(client, BASELINE_B_SYSTEM, user), evidence)


READ_SYSTEM = (
    BASE_SYSTEM
    + " 采用两步作答：第一步逐条精读证据，整理出与问题相关的要点；"
      "第二步基于这些要点给出面向办事的回答。"
)

READ_USER = """【证据】
{evidence}

【问题】
{question}
{outline}
输出 JSON：
{{"key_points": [{{"text": "要点", "evidence_ids": ["证据编号"]}}],
 "answer": "基于要点的完整回答，关键结论后附 [证据编号]"}}"""


def _read_and_answer(client: Any, turns: Sequence[dict], evidence: Sequence[dict],
                     outline: str = "") -> str:
    data = _json_or_empty(client, READ_SYSTEM, READ_USER.format(
        evidence=evidence_block(evidence), question=conversation_block(turns),
        outline=outline), 2000)
    return answer_of(data)


def baseline_c(client: Any, turns: Sequence[dict], evidence: Sequence[dict]) -> Prediction:
    return _prediction(_read_and_answer(client, turns, evidence), evidence)


# ------------------------------------------------------ interaction control

MODE_GUIDE = """先判定响应方式（response_mode 必填）：
- answer：条件完整，且提问的前提与证据的适用范围一致。
- scoped_correction：提问中的对象、步骤或材料前提与证据的规定不符（例如把研究生当成本科生、
  办理顺序颠倒、把两种材料各自的适用条件混在一起），必须先明确指出哪一部分不符，
  再给出适用于正确对象或条件的回答。
- clarification：问题缺少某个条件，且证据中该条件取值不同、答案就不同，必须先问清楚；
  如果无论条件取何值答案都一样，或者可以把各种情形一并说清，就直接回答。
  学生已经在对话中说明过的条件不要再问。默认提问者就是证据所适用的对象（如在校本科生），
  不要追问身份；只有学生明确说出的身份与证据适用对象不符时才处理。
  只追问证据中明确写出会导致不同办法的条件，不追问证据没有区分的情况。
  判定前先逐条核对：学生的话里是否已经出现了该条件的取值（如"外招生""2005届""三天"）；
  出现过就视为已知。
- version_qualified：【证据】里有两条来自不同时期来源的文字，且在所问要点上说法不同；
  此时说明依据的是哪个来源版本。学生口中的"以前""旧版""去年的通知"不算证据：
  如果证据里只有一个版本，就按现有证据回答（前提与证据不符时用 scoped_correction）。
- conversation_resolution：多轮对话中学生已补充了先前缺少的条件，合并上下文后作答。
- abstention：证据中没有任何内容能回答该问题。
不要为了回避而滥用 clarification 或 abstention；也不要把前提不符当成 answer 直接作答。"""

MODE_USER = """{skeleton}【证据】
{evidence}

【问题】
{question}

{mode_guide}

只做判定，不写回答。输出 JSON：
{{
  "response_mode": "{options}",
  "missing_conditions": ["问题中没有交代、但会改变答案的关键条件"],
  "follow_up_question": "需要追问时的问题；否则 null",
  "correction": "scoped_correction 时指出提问中哪一部分与证据不符；否则 null"
}}"""

MODE_SYSTEM = "你是校园办事问答的交互控制模块。只判定本次应当采用哪种响应方式，不写回答内容。"


@dataclass
class Decision:
    mode: str = "answer"
    missing: tuple[str, ...] = ()
    follow_up: str | None = None
    correction: str | None = None


def decide_mode(client: Any, turns: Sequence[dict], evidence: Sequence[dict],
                skeleton: dict | None = None) -> Decision:
    skeleton_part = f"【流程骨架】\n{skeleton_text(skeleton)}\n\n" if skeleton else ""
    data = _json_or_empty(client, MODE_SYSTEM, MODE_USER.format(
        skeleton=skeleton_part, evidence=evidence_block(evidence),
        question=conversation_block(turns), mode_guide=MODE_GUIDE,
        options=" | ".join(KNOWN_MODES)), 800)
    mode = str(data.get("response_mode") or "answer")
    mode = mode if mode in KNOWN_MODES else "answer"
    missing = tuple(str(m) for m in (data.get("missing_conditions") or []) if str(m).strip())
    follow_up = str(data["follow_up_question"]).strip() if data.get("follow_up_question") else None
    correction = str(data["correction"]).strip() if data.get("correction") else None
    if mode != "clarification":
        follow_up, missing = None, ()
    return Decision(mode, missing, follow_up, correction if mode == "scoped_correction" else None)


ABSTAIN_TEXT = "现有官方材料中没有涉及这个问题的内容，建议直接咨询相关办理部门。"


# ------------------------------------------------------------ flow skeleton

def skeleton_text(skeleton: dict | None) -> str:
    if not skeleton:
        return "（未抽取到要素）"
    labels = {"steps": "办理步骤", "conditions": "适用条件", "materials": "所需材料",
              "time_constraints": "时间要求", "entries": "办理入口"}
    lines = []
    for kind, label in labels.items():
        for number, element in enumerate(skeleton.get(kind) or [], 1):
            ids = "".join(f"[{i}]" for i in element.get("evidence_ids") or [])
            prefix = f"{number}. " if kind == "steps" else "- "
            lines.append(f"{label} {prefix}{element.get('text', '')}{ids}")
    return "\n".join(lines) or "（未抽取到要素）"


def skeleton_outline(skeleton: dict | None) -> str:
    """The skeleton as an answer outline for the generation prompt."""
    if not skeleton or not any(skeleton.get(k) for k in ("steps", "materials", "conditions",
                                                          "time_constraints", "entries")):
        return ""
    return (
        "\n【回答提纲（由证据抽取的流程骨架）】\n"
        f"{skeleton_text(skeleton)}\n"
        "回答须按提纲中的办理步骤顺序组织；提纲中与问题相关的步骤、材料、时间要求和办理入口"
        "都要写进回答，与问题无关的可以略去，但不得写入提纲和证据之外的内容。\n"
    )


# ------------------------------------------------------- claim verification

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

NO_SUPPORTED_CLAIM_NOTE = "（核验后没有留下可由证据直接支持的断言。）"


def _rebuild_from_claims(claims: Sequence[Any], allowed: set[str]) -> str:
    """Keep only assertions the retrieved evidence supports, in their original order.

    Recomposition is deterministic: the model never rewrites the answer, so a
    dropped assertion cannot reappear in a paraphrase.
    """
    lines: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict) or str(claim.get("verdict") or "").strip() != "supported":
            continue
        body = CITATION_PATTERN.sub("", str(claim.get("text") or "")).strip()
        ids = list(dict.fromkeys(str(i) for i in claim.get("evidence_ids") or []
                                 if str(i) in allowed))
        if not body or not ids:
            continue
        closing = "" if body.endswith(SENTENCE_END) else "。"
        lines.append(body + closing + "".join(f"[{i}]" for i in ids))
    return "\n".join(lines)


def verify_claims(client: Any, evidence: Sequence[dict], draft: str) -> str:
    """Falls back to the draft only when the check could not run at all."""
    allowed = {row["evidence_id"] for row in evidence}
    data = _json_or_empty(client, CLAIM_VERIFY_SYSTEM, CLAIM_VERIFY_USER.format(
        evidence=evidence_block(evidence), draft=draft), 2000)
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        return draft
    return _rebuild_from_claims(claims, allowed) or NO_SUPPORTED_CLAIM_NOTE


# ---------------------------------------------------------- shared pipeline

def controlled(client: Any, turns: Sequence[dict], evidence: Sequence[dict],
               skeleton: dict | None, *, verify: bool) -> Prediction:
    """Interaction control, optionally with the skeleton and claim verification.

    With ``skeleton=None`` and ``verify=False`` this is the ``interaction``
    configuration. The skeleton, when given, informs the mode decision and is the
    outline of the generated answer.
    """
    decision = decide_mode(client, turns, evidence, skeleton)
    if decision.mode == "abstention":
        return _prediction(ABSTAIN_TEXT, evidence, mode="abstention")
    if decision.mode == "clarification":
        return _prediction("", evidence, mode="clarification",
                           missing=decision.missing,
                           follow_up=decision.follow_up or "请补充办理所需的条件。")

    outline = skeleton_outline(skeleton)
    if decision.correction:
        outline += f"\n【需要先纠正的前提】\n{decision.correction}\n回答开头先指出这一点，再给出正确做法。\n"
    draft = _read_and_answer(client, turns, evidence, outline)
    final = verify_claims(client, evidence, draft) if verify and draft else draft
    return _prediction(final, evidence, mode=decision.mode)


def interaction(client: Any, turns: Sequence[dict], evidence: Sequence[dict]) -> Prediction:
    return controlled(client, turns, evidence, None, verify=False)


def full(client: Any, turns: Sequence[dict], evidence: Sequence[dict],
         skeleton: dict) -> Prediction:
    return controlled(client, turns, evidence, skeleton, verify=True)


def full_no_skeleton(client: Any, turns: Sequence[dict], evidence: Sequence[dict]) -> Prediction:
    return controlled(client, turns, evidence, None, verify=True)


def full_no_verify(client: Any, turns: Sequence[dict], evidence: Sequence[dict],
                   skeleton: dict) -> Prediction:
    return controlled(client, turns, evidence, skeleton, verify=False)


SYSTEMS = {
    "baseline_a": baseline_a,
    "baseline_b": baseline_b,
    "baseline_c": baseline_c,
    "interaction": interaction,
    "full": full,
    "full_no_skeleton": full_no_skeleton,
    "full_no_verify": full_no_verify,
}

USES_SKELETON = ("full", "full_no_verify")
