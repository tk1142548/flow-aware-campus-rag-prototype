"""Build the independent confirmatory evaluation set (120 samples).

Generation is seed-driven: a claim (and therefore its single evidence item) is
chosen first, and the question is written around it. That keeps the gold evidence
tight, the way the development set is annotated, and it keeps the sample anchored
to official text rather than to the model's prior.

Only the official evidence and the process records are read. No method output is
touched, so the set cannot be fitted to the systems it will later judge.

Composition is fixed in docs/experiments/INDEPENDENT_SET_PREREGISTRATION.md.

Usage:
    python scripts/build_independent_set.py [--limit N] [--workers 6]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import ApiClient
from app.backend.research_data import ResearchRepository

DATASET_ID = "CAMPUS_RAG_INDEPENDENT_V1"
DEV_SET = ROOT / "data/evaluation/stage2_samples.jsonl"
OUTPUT = ROOT / "data/evaluation/independent-set.jsonl"

SCENARIO_MODE = {
    "direct": "answer",
    "condition_missing": "clarification",
    "object_mismatch": "scoped_correction",
    "version_conflict": "version_qualified",
    "step_error": "scoped_correction",
    "material_confusion": "scoped_correction",
    "out_of_scope": "abstention",
    "multi_turn": "conversation_resolution",
}

SCENARIO_HINT = {
    "direct": "直接询问办理方式、材料、地点或时限，条件齐全，可直接作答。",
    "condition_missing": "问题缺少会改变答案的关键条件，必须先追问才能回答。",
    "object_mismatch": "提问者按不适用于自己的对象或分支来问，需要指出对象不符并给出适用口径。",
    "step_error": "提问者的办理顺序或做法有误，需要指出并修正。",
    "material_confusion": "提问者把材料搞混了，需要区分材料各自适用的条件。",
    "version_conflict": "提问涉及不同时期发布的规定之间的差异，或把旧版规定当作现行规定，需要说明依据的是哪个版本，且不得断言未经来源确认的版本替代关系。",
    "out_of_scope": "提问涉及现有官方材料完全没有覆盖的事项或环节，只能有边界地拒答，不得凭常识补充。",
    "multi_turn": "多轮对话：用户先说一句不完整的话，助手追问后用户补充，最后一条消息来自用户，需要合并上下文后作答。",
}

ANGLE = {
    "direct": ["需要准备的材料与份数", "办理地点与自助设备", "登录方式与账号密码",
               "办理时间与时限", "费用与免费额度", "适用的学生对象范围"],
    "condition_missing": ["未说明具体办理类型", "未说明在校还是已毕业", "未说明入学年份或届别",
                          "未说明内招生还是外招生", "未说明学籍或注册状态"],
    "object_mismatch": ["研究生按本科生口径提问", "已毕业学生按在校生口径提问",
                        "其他届别按当前届别口径提问", "外招生按内招生口径提问"],
    "step_error": ["跳过前置环节直接问下一步", "把两个分支的步骤混在一起",
                   "先交材料后办手续的顺序颠倒", "漏掉签章或核签环节"],
    "material_confusion": ["把两个分支的材料清单混用", "混淆证明材料的出具单位",
                           "漏掉必要附件", "混淆材料的份数或语言版本"],
    "version_conflict": ["旧版表格上的时间为准吗", "旧版流程页的对接单位还适用吗",
                         "往年通知的口径还能用吗", "旧版规定的适用对象有变化吗",
                         "两个版本的表述不一致时依据哪个"],
    "out_of_scope": ["咨询签证与公证等校外环节", "咨询奖学金与资助",
                     "咨询宿舍与后勤", "咨询成绩复核与申诉", "咨询实习与就业手续"],
    "multi_turn": ["补出办理类型", "补出学籍状态", "补出入学年份"],
}

# claim types that suit each scenario
TYPE_POOL = {
    "direct": ["step", "material", "service_location", "time_constraint", "fee", "entry"],
    "condition_missing": ["precondition", "applicable_audience", "exception", "time_constraint"],
    "object_mismatch": ["applicable_audience", "step", "material"],
    "step_error": ["step", "precondition"],
    "material_confusion": ["material", "exception"],
    "multi_turn": ["step", "material", "precondition"],
}

PLAN = {
    "CS": {"direct": 3, "condition_missing": 3, "object_mismatch": 2, "step_error": 2,
           "material_confusion": 2, "out_of_scope": 1, "multi_turn": 2},
    "CR": {"direct": 3, "condition_missing": 3, "object_mismatch": 2, "step_error": 2,
           "material_confusion": 2, "out_of_scope": 1, "multi_turn": 2},
    "LR": {"direct": 3, "condition_missing": 3, "object_mismatch": 2, "step_error": 2,
           "material_confusion": 2, "out_of_scope": 1, "multi_turn": 2},
    "MC": {"direct": 3, "condition_missing": 3, "object_mismatch": 2, "step_error": 2,
           "material_confusion": 2, "out_of_scope": 1, "multi_turn": 2},
    "SR": {"direct": 3, "condition_missing": 3, "object_mismatch": 2, "step_error": 2,
           "material_confusion": 2, "out_of_scope": 1, "multi_turn": 2},
    "PP": {"direct": 2, "condition_missing": 2, "object_mismatch": 1, "step_error": 1,
           "material_confusion": 2, "version_conflict": 5, "out_of_scope": 2},
    "WD": {"direct": 2, "condition_missing": 2, "object_mismatch": 1, "step_error": 1,
           "material_confusion": 2, "version_conflict": 5, "out_of_scope": 2},
    "SC": {"direct": 1, "condition_missing": 1, "object_mismatch": 3, "step_error": 3,
           "material_confusion": 1, "version_conflict": 5, "out_of_scope": 1},
}

CODE_ITEM = {
    "CR": "UG_CREDENTIAL_REISSUE",
    "CS": "UG_COURSE_SELECTION",
    "LR": "UG_LEAVE_REQUEST",
    "MC": "UG_MAJOR_CHANGE",
    "PP": "UG_PROOF_PRINT",
    "SC": "UG_STATUS_CHANGE",
    "SR": "UG_STUDENT_CARD_REISSUE",
    "WD": "UG_WITHDRAWAL",
}

DIFFICULTY = {
    "direct": "easy", "condition_missing": "medium", "object_mismatch": "medium",
    "step_error": "hard", "material_confusion": "hard", "version_conflict": "hard",
    "out_of_scope": "medium", "multi_turn": "medium",
}

SYSTEM = (
    "你在为一个校园办事问答系统的评测集出题。你只依据给出的官方证据与流程记录工作，"
    "不得使用你自己的常识补充任何事实。"
)

USER = """【事项】{item_title}
【场景类型】{scenario}：{hint}
【预期应答方式】{mode}
【本题限定角度】{angle}

【答案依据（本题答案必须且只能建立在这几条证据上）】
{seed}

【这些证据对应的允许声明】
{claims}

【该事项的办理步骤（供你判断顺序，不必全部用上）】
{steps}

【材料清单（供你判断，不必全部用上）】
{materials}

【槽位（提问者需要交代的条件）】
{slots}

请出一道题，并给出金标准标注，输出 JSON：
{{
  "conversation": [{{"role": "user", "text": "..."}}{extra_turn}],
  "provided_slots": [{{"slot_id": "SL_XXX", "value": "提问者已经说出的取值"}}],
  "missing_slot_ids": ["需要追问才能拿到的槽位编号"],
  "follow_up_question": "需要追问时的问题；否则 null",
  "allowed_claim_ids": ["回答应当覆盖的允许声明编号，只能取上面列出的"],
  "ordered_step_ids": ["回答应当覆盖的步骤编号，按顺序"],
  "material_ids": ["回答应当覆盖的材料编号"],
  "answer_boundary": "一句话说明这道题的作答边界",
  "notes": "这道题想考什么"
}}

要求：
- 问句要像学生说的话，可以口语、省略、带指代，不要照抄证据原文的措辞。
- allowed_claim_ids 只能从上面列出的允许声明里选，且尽量不要全选。
- ordered_step_ids 从上面的步骤编号里选，可以只选相关的一两步。
- 除 out_of_scope 外，allowed_claim_ids 与 ordered_step_ids 都不能为空。
- 场景为 condition_missing 时，missing_slot_ids 不能为空，且不能出现在 provided_slots 里。
- 场景为 out_of_scope 时，上面的证据只作为背景；问题要问一个这些材料完全没有覆盖的事情，
  allowed_claim_ids、ordered_step_ids、material_ids 全部留空数组。
- 场景为 multi_turn 时，conversation 至少三条消息：用户先说一句不完整的话，助手追问一句，
  用户再补充一句（最后一条必须是用户）。其他场景只有一条用户消息。"""


def seed_claims(process: dict, scenario: str, source_of: dict, label_of: dict,
                uncited: set[str], rng: random.Random) -> list[dict]:
    """Pick the one or two claims the question will be built around."""
    claims = process["allowed_claims"]
    fresh = [c for c in claims if any(e in uncited for e in c["evidence_ids"])]

    if scenario == "version_conflict":
        by_label: dict[str, list[dict]] = defaultdict(list)
        for claim in claims:
            for eid in claim["evidence_ids"]:
                label = label_of.get(source_of.get(eid, ""), "")
                if label:
                    by_label[label].append(claim)
        labels = sorted(by_label, key=lambda l: -len(by_label[l]))
        if len(labels) >= 2:
            rng.shuffle(labels)
            return [rng.choice(by_label[labels[0]]), rng.choice(by_label[labels[1]])]
        fresh.sort(key=lambda c: len(c["text"]))
        return fresh[:2] or claims[:2]

    pool = [c for c in claims if c["claim_type"] in TYPE_POOL.get(scenario, [])] or claims
    pool = [c for c in pool if any(e in uncited for e in c["evidence_ids"])] or pool
    rng.shuffle(pool)
    if scenario == "direct":
        pool.sort(key=lambda c: len(c["text"]), reverse=True)
    return pool[:1] if scenario in ("condition_missing",) else pool[:2]


def attempts(reply: dict, scenario: str, allowed_claim_ids: set[str],
             step_ids: set[str], material_ids: set[str], slot_ids: set[str]) -> list[str]:
    """Reasons the draft has to be redone; empty means acceptable.

    Thresholds follow the development set's annotation habits: 1-2 claims and 1-2
    evidence items per question, steps optional, materials mostly empty, and
    `missing_slot_ids` used only by condition-missing questions.
    """
    problems = []
    turns = reply.get("conversation") or []
    if not turns:
        problems.append("没有对话")
        return problems
    if len("".join(str(t.get("text") or "") for t in turns)) < 8:
        problems.append("问句过短")
    if scenario == "multi_turn":
        if len(turns) < 3 or str(turns[-1].get("role")) != "user":
            problems.append("多轮结构不符")
        if not any(str(t.get("role")) == "assistant" for t in turns):
            problems.append("多轮缺助手发言")
    elif len(turns) != 1:
        problems.append("单轮题消息数不为 1")

    missing = [s for s in (reply.get("missing_slot_ids") or []) if s in slot_ids]
    provided = {str(e.get("slot_id")) for e in (reply.get("provided_slots") or [])}
    if scenario == "condition_missing":
        if not missing:
            problems.append("条件缺失题没有缺失槽位")
        if set(missing) & provided:
            problems.append("缺失槽位与已提供槽位冲突")
    elif missing:
        problems.append("非条件缺失题不应有缺失槽位")

    if scenario == "out_of_scope":
        if reply.get("allowed_claim_ids") or reply.get("ordered_step_ids"):
            problems.append("越界题不应有声明或步骤")
        return problems

    chosen = [c for c in (reply.get("allowed_claim_ids") or []) if c in allowed_claim_ids]
    if not chosen:
        problems.append("没有选出可用的允许声明")
    elif len(chosen) > 2:
        problems.append("允许声明过多")
    bad_steps = [s for s in (reply.get("ordered_step_ids") or []) if s not in step_ids]
    if bad_steps:
        problems.append("步骤编号不存在")
    elif len(reply.get("ordered_step_ids") or []) > 3:
        problems.append("步骤过多")
    bad_materials = [m for m in (reply.get("material_ids") or []) if m not in material_ids]
    if bad_materials:
        problems.append("材料编号不存在")
    if scenario == "condition_missing":
        if reply.get("material_ids"):
            problems.append("条件缺失题不应列材料")
        if len(reply.get("ordered_step_ids") or []) > 2:
            problems.append("条件缺失题步骤过多")
    if scenario == "version_conflict" and reply.get("material_ids"):
        problems.append("版本冲突题不应列材料")
    if scenario == "object_mismatch":
        text = "".join(str(t.get("text") or "") for t in turns)
        if not any(k in text for k in ("研究生", "硕士", "博士", "毕业", "届", "外招生",
                                       "内招生", "外籍", "港澳台", "专科", "学院")):
            problems.append("对象错配题没有点明提问者身份")
    return problems


def question_guard(guard: dict, client: ApiClient, text: str,
                   cell: tuple[str, str]) -> list[str]:
    """Reject a question too close to the development set, or to one already accepted
    inside the same (item, scenario) cell. The cell scoping matters: questions about
    the same single slot are inherently similar, and the guard exists to stop the set
    from padding a stratum, not to force artificial paraphrase."""
    from validate_independent_set import grams, jaccard, cosine
    vector = client.embed([text])[0]
    mine = grams(text)
    with guard["lock"]:
        for other in guard["dev_grams"]:
            if jaccard(mine, other) > 0.6:
                return ["问句与开发集字符重叠过高"]
        for other in guard["dev_vectors"]:
            if cosine(vector, other) > 0.85:
                return ["问句与开发集语义过于接近"]
        for other in guard["cells"].get(cell, {"grams": [], "vectors": []})["grams"]:
            if jaccard(mine, other) > 0.6:
                return ["同一分格内问句字符重叠过高"]
        for other in guard["cells"].setdefault(cell, {"grams": [], "vectors": []})["vectors"]:
            if cosine(vector, other) > 0.95:
                return ["同一分格内问句语义过于接近"]
        guard["cells"][cell]["grams"].append(mine)
        guard["cells"][cell]["vectors"].append(vector)
    return []


def build_sample(repository: ResearchRepository, client: ApiClient, item_code: str,
                 scenario: str, index: int, uncited: set[str], variant: int = 0,
                 guard: dict | None = None) -> dict:
    item_id = CODE_ITEM[item_code]
    processes = [p for p in repository.processes.values() if p["item_id"] == item_id]
    process = max(processes, key=lambda p: len(p["allowed_claims"]))
    rows = [r for r in repository.all_verified_evidence() if r["item_id"] == item_id]
    evidence_by_id = {r["evidence_id"]: r for r in rows}
    source_of = {r["evidence_id"]: r["source_id"] for r in rows}
    label_of = {}
    for source_id, source in repository.sources.items():
        label_of[source_id] = source.get("version", {}).get("label") or source["title"]

    sample_id = f"ISE-{item_code}-{index:03d}"
    seed_value = int(hashlib.sha256(f"{sample_id}#{variant}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_value)
    angles = ANGLE[scenario]
    angle = angles[(index - 1 + variant) % len(angles)]

    if scenario == "out_of_scope":
        pool = [r for r in rows if r["evidence_id"] in uncited] or rows
        rng.shuffle(pool)
        seed = pool[:2]
        usable = []
    else:
        chosen_claims = seed_claims(process, scenario, source_of, label_of, uncited, rng)
        seed_ids = []
        for claim in chosen_claims:
            for eid in claim["evidence_ids"]:
                if eid not in seed_ids:
                    seed_ids.append(eid)
        seed = [evidence_by_id[e] for e in seed_ids if e in evidence_by_id]
        usable = [c for c in process["allowed_claims"]
                  if set(c["evidence_ids"]) <= set(seed_ids)]

    if not seed:
        raise RuntimeError(f"{sample_id}: 没有可用种子证据")

    allowed_steps = {s["step_id"] for s in process["steps"]}
    allowed_materials = {m["material_id"] for m in process.get("materials", [])}
    slot_ids = {s["slot_id"] for s in process.get("slots", [])}
    extra_turn = ('，{{"role": "assistant", "text": "..."}}, '
                  '{{"role": "user", "text": "..."}}') if scenario == "multi_turn" else ""

    prompt = USER.format(
        item_title=process["title"], scenario=scenario, hint=SCENARIO_HINT[scenario],
        mode=SCENARIO_MODE[scenario], angle=angle,
        seed="\n".join(f"[{r['evidence_id']}] {r['normalized_claim']}" for r in seed),
        claims="\n".join(f"[{c['claim_id']}] {c['text']}" for c in usable) or "（本题没有可用声明）",
        steps="\n".join(f"[{s['step_id']}] {s['action']}" for s in process["steps"]) or "（无）",
        materials="\n".join(f"[{m['material_id']}] {m['name']}"
                            for m in process.get("materials", [])) or "（无）",
        slots="\n".join(f"[{s['slot_id']}] {s['name']}"
                        for s in process.get("slots", [])) or "（无）",
        extra_turn=extra_turn)

    reply, problems = {}, []
    for attempt in range(4):
        reply = client.chat_json(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.3 + 0.3 * attempt, max_tokens=1500)
        problems = attempts(reply, scenario, {c["claim_id"] for c in usable},
                            allowed_steps, allowed_materials, slot_ids)
        if not problems and guard is not None:
            problems = question_guard(guard, client, "\n".join(
                str(t.get("text") or "") for t in (reply.get("conversation") or [])
                if str(t.get("role")) == "user"), (item_code, scenario))
        if not problems:
            break
        prompt = prompt + f"\n\n【上一次未通过：{'；'.join(problems)}，请重出，务必满足全部要求。】"

    if problems:
        raise RuntimeError(f"{sample_id}: 出题未通过校验 - {'；'.join(problems)}")

    provided = []
    for entry in reply.get("provided_slots") or []:
        slot_id = str(entry.get("slot_id") or "")
        if slot_id in slot_ids:
            provided.append({"slot_id": slot_id, "value": str(entry.get("value") or ""),
                             "value_status": "known"})
    provided_ids = {p["slot_id"] for p in provided}
    missing = sorted({s for s in (reply.get("missing_slot_ids") or [])
                      if s in slot_ids} - provided_ids) if scenario == "condition_missing" else []

    usable_ids = {c["claim_id"] for c in usable}
    if scenario == "out_of_scope":
        allowed_claims, ordered_steps, material_ids = [], [], []
    else:
        allowed_claims = list(dict.fromkeys(
            c for c in (reply.get("allowed_claim_ids") or []) if c in usable_ids))
        ordered_steps = list(dict.fromkeys(
            s for s in (reply.get("ordered_step_ids") or []) if s in allowed_steps))
        material_ids = list(dict.fromkeys(
            m for m in (reply.get("material_ids") or [])
            if m in {x["material_id"] for x in process.get("materials", [])}))

    seed_ids = [r["evidence_id"] for r in seed]
    source_ids = sorted({source_of[e] for e in seed_ids})
    labels = {label_of[s] for s in source_ids}
    if scenario == "version_conflict":
        version_risk = "cross_version_conflict"
    elif len(source_ids) > 1:
        version_risk = "version_sensitive"
    else:
        version_risk = "stable"

    turns = []
    for number, turn in enumerate(reply.get("conversation") or [], 1):
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        role = "assistant" if str(turn.get("role")) == "assistant" else "user"
        turns.append({"turn_id": f"T{number:02d}", "role": role, "text": text})

    prohibited = ["未被来源支持的其他事项规则", "将其他对象或版本的条件泛化到本样本"]
    if scenario == "version_conflict":
        prohibited.append("把历史版本的规定直接表述为现行规则")
    if scenario == "object_mismatch":
        prohibited.append("把不适用对象或分支的口径套用到本题提问者")

    out_of_scope = scenario == "out_of_scope"
    return {
        "schema_version": "1.0",
        "dataset_id": DATASET_ID,
        "sample_id": sample_id,
        "allocation_item_id": item_id,
        "item_id": None if out_of_scope else item_id,
        "process_id": None if out_of_scope else process["process_id"],
        "split": "test",
        "scenario_type": scenario,
        "difficulty": DIFFICULTY[scenario],
        "version_risk": version_risk,
        "turn_structure": "multi_turn" if scenario == "multi_turn" else "single_turn",
        "conversation": turns,
        "input_context": {
            "provided_slots": provided,
            "requested_as_of": None,
            "source_version_ids": source_ids,
        },
        "gold": {
            "response_mode": SCENARIO_MODE[scenario],
            "target_item_id": None if out_of_scope else item_id,
            "required_slot_ids": sorted(provided_ids | set(missing)),
            "missing_slot_ids": missing,
            "follow_up_question": (str(reply.get("follow_up_question")).strip()
                                   if reply.get("follow_up_question") else None),
            "ordered_step_ids": ordered_steps,
            "material_ids": material_ids,
            "allowed_claim_ids": allowed_claims,
            "supporting_evidence_ids": [] if out_of_scope else seed_ids,
            "prohibited_claims": prohibited,
            "answer_boundary": str(reply.get("answer_boundary") or "").strip()
                              or f"依据{process['title']}与所列来源回答，仅使用选定声明。",
        },
        "leakage_control": {
            "template_family_id": f"TPL_ISE_{item_code}_{scenario.upper()}",
            "source_version_group_ids": [f"SVG_{item_code}_VERIFIED"],
            "semantic_cluster_id": f"SEM_ISE_{item_code}_{index:03d}",
            "construction_origin": "official_source_derived",
            "prohibited_overlap_sample_ids": [],
            "check_status": "pending",
            "checked_at": None,
            "checker": None,
            "notes": (str(reply.get("notes") or "")[:180]
                      + f"；角度：{angle}；出处版本标签：{'、'.join(sorted(labels))}")[:300],
        },
        "review_status": "draft",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    started = time.perf_counter()
    repository = ResearchRepository(ROOT)
    client = ApiClient(ROOT / "data/cache")

    from validate_independent_set import grams as _grams, question_of as _question_of
    import threading
    dev_rows = [json.loads(line) for line in DEV_SET.read_text(encoding="utf-8").splitlines() if line]
    dev_questions = [_question_of(row) for row in dev_rows]
    guard = {
        "lock": threading.Lock(),
        "dev_grams": [_grams(q) for q in dev_questions],
        "dev_vectors": client.embed(dev_questions),
        "cells": {},
    }
    print(f"污染守卫已载入开发集 {len(dev_questions)} 条问句", flush=True)

    used = {e for s in dev_rows for e in s["gold"]["supporting_evidence_ids"]}
    uncited = {row["evidence_id"] for row in repository.all_verified_evidence()} - used

    counted: dict[str, int] = defaultdict(int)
    jobs = []
    for code in sorted(PLAN):
        for scenario, count in PLAN[code].items():
            for _ in range(count):
                counted[code] += 1
                jobs.append((code, scenario, counted[code]))
    if args.limit:
        jobs = jobs[: args.limit]
    print(f"计划生成 {len(jobs)} 条", flush=True)

    records, failures = [], []
    pending = list(jobs)
    for round_no in range(4):
        if not pending:
            break
        print(f"第 {round_no + 1} 轮：{len(pending)} 条", flush=True)
        made, left = [], []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(build_sample, repository, client, c, s, i, uncited,
                                   round_no, guard): (c, s, i) for c, s, i in pending}
            for done, (future, key) in enumerate(futures.items(), 1):
                try:
                    made.append(future.result())
                except Exception as error:  # noqa: BLE001 - recorded, not swallowed
                    left.append(key)
                    if round_no == 3:
                        failures.append({"key": key,
                                         "error": f"{type(error).__name__}: {error}"[:300]})
                if done % 20 == 0:
                    print(f"  {done}/{len(pending)}", flush=True)
        records.extend(made)
        pending = left
    records.sort(key=lambda r: r["sample_id"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(f"\n写出 {len(records)} 条 -> {OUTPUT.relative_to(ROOT)}")
    print(f"失败 {len(failures)}")
    for failure in failures[:5]:
        print("  ", failure)
    print(f"cost: {client.cost_summary()}")
    print(f"elapsed: {time.perf_counter() - started:.1f}s")
    print(f"completed_at: {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
