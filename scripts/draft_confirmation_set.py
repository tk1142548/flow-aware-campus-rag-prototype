"""Draft the confirmation set: the gold is chosen from the process records first,
and the model only phrases the student's question.

Each sample is built from a plan the script derives from the records:

  procedure   a multi-step "how do I" question whose gold is the process's
              steps (and materials) in order                      -> answer
  fact        a single claim (time, place, fee, material)         -> answer
  premise     the question states something the evidence
              contradicts (wrong order, wrong office, wrong
              material, wrong audience)                           -> scoped_correction
  missing     a slot that changes the answer is left out          -> clarification
  version     two dated sources differ on the asked point         -> version_qualified
  outside     the evidence covers nothing of the question         -> abstention
  dialogue    clarification, then the student supplies the slot   -> conversation_resolution

The question writer is kimi-k2.6, a different family from the systems under test.
Every draft is reviewed by a person before use (see build_review_sheet.py).

Usage:
    python scripts/draft_confirmation_set.py [--limit N] [--workers 4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.api_client import judge_client
from app.backend.research_data import ResearchRepository

OUTPUT = ROOT / "data/evaluation/confirm-draft.jsonl"
DEV_SET = ROOT / "data/evaluation/dev-set.jsonl"
DATASET_ID = "CAMPUS_RAG_CONFIRM_V1"

ITEM_CODE = {
    "UG_CREDENTIAL_REISSUE": "CR", "UG_COURSE_SELECTION": "CS", "UG_LEAVE_REQUEST": "LR",
    "UG_MAJOR_CHANGE": "MC", "UG_PROOF_PRINT": "PP", "UG_STATUS_CHANGE": "SC",
    "UG_STUDENT_CARD_REISSUE": "SR", "UG_WITHDRAWAL": "WD",
}

# Version pairs the evidence actually contains, checked by hand against the
# process records: (old process, old claim, new process, new claim, asked point).
VERSION_PAIRS = (
    ("PROC_UG_WITHDRAWAL_V003", "CLM_009", "PROC_UG_WITHDRAWAL_V004", "CLM_012",
     "主动退学的集中受理时间"),
    (None, None, "PROC_UG_WITHDRAWAL_V004", "CLM_002",
     "主动退学申请是否要附家长知情同意书（2011 年表格无此要求）"),
    ("PROC_UG_RESUME_LEGACY_V001", "CLM_004", "PROC_UG_RESUME_PROCESS_V001", "CLM_002",
     "复学申请的提交时限"),
    ("PROC_UG_RESUME_LEGACY_V001", "CLM_010", "PROC_UG_RESUME_PROCESS_V001", "CLM_014",
     "领取复学通知后要做什么"),
    ("PROC_UG_RESUME_LEGACY_V001", "CLM_005", "PROC_UG_RESUME_PROCESS_V001", "CLM_007",
     "因病休学后复学需要什么证明"),
)

# Distinct framings so repeated plans on one process do not produce one question.
PERSONAS = (
    "第一次办这件事、什么都不清楚的学生",
    "时间很紧、想尽快办完的学生",
    "说话比较随意、带点口头禅的学生",
    "已经开始办但卡在中途、想确认后面怎么走的学生",
    "说话很简短、只问一句的学生",
    "比较礼貌、会先说明自己情况的学生",
)

OUTSIDE_TOPICS = (
    "宿舍调换", "奖学金评定", "成绩复核与申诉", "实习证明", "签证与出入境",
    "校园网开通", "食堂饭卡充值", "毕业生档案转递", "医保报销", "图书馆借书逾期",
)

# missing and dialogue use each of the six answer-changing slots once.
PLAN = {"procedure": 52, "fact": 24, "premise": 24, "missing": 6, "version": 10,
        "outside": 10, "dialogue": 6}

MODE = {"procedure": "answer", "fact": "answer", "premise": "scoped_correction",
        "missing": "clarification", "version": "version_qualified", "outside": "abstention",
        "dialogue": "conversation_resolution"}

SYSTEM = ("你在为校园办事问答系统的评测集写学生提问。你只负责把给定的考查要点改写成"
          "一个真实学生会说的问题，不负责判断答案，不得引入要点之外的事实。")

PROMPT = {
    "procedure": """事项：{plain}
学生身份：{audience}
请写一个学生想知道"怎么办理{plain}"的完整流程的问题。问题要口语化，可以带上自己的处境，
但不要提到具体步骤名称，也不要问"需要几步"，不要提表格版本、年份或"新流程"。只写一个问题。""",
    "fact": """事项：{title}
考查要点（学生不知道、想问清楚的事实）：{claim}
请写一个学生会问、而且答案正好是这条要点的问题。不要在问题里透露答案。只写一个问题。""",
    "premise": """事项：{title}
官方规定：{claim}
学生的错误理解：{wrong}
请写一个学生带着这个错误理解来问的问题（例如"我是不是……就可以了？"）。
错误理解要自然地体现在问题里，但不要写出官方规定。只写一个问题。""",
    "missing": """事项：{title}
答案取决于这个条件：{slot}（可能的取值：{values}）
请写一个学生的问题，学生想办这件事，但没有交代"{slot}"。问题中不能出现、也不能暗示
上面任何一个取值（例如不能说出自己的具体情况属于哪一种）。不要提及这个条件本身。只写一个问题。""",
    "version": """事项：{title}
考查点：{point}
旧版规定（{old_label}）：{old}
新版规定（{new_label}）：{new}
请写一个学生的问题：学生手里拿着或听说过旧版的说法，想确认现在是否还这样。
问题里要能看出学生说的是旧版的说法，但不要写出新版规定。只写一个问题。""",
    "outside": """请写一个本科生会问的关于"{topic}"的办事问题，口语化，只写一个问题。""",
    "dialogue": """事项：{title}
答案取决于这个条件：{slot}（取值：{value}）
请写一段三轮对话：学生先问办理{title}的事但没说"{slot}"；助手追问"{slot}"；
学生回答"{value}"（用自己的话）。输出 JSON：
{{"turns": ["学生第一句", "助手追问", "学生补充"]}}""",
}

WRONG_TEMPLATES = (
    ("order", "把第 {a} 步和第 {b} 步的先后顺序弄反了：以为先「{sb}」再「{sa}」"),
    ("skip", "以为可以跳过「{sa}」这一步，直接「{sb}」"),
)


def stable_rng(key: str) -> random.Random:
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))


def claim_evidence(process: dict, claim_ids) -> list[str]:
    claims = {c["claim_id"]: c for c in process["allowed_claims"]}
    ids: list[str] = []
    for cid in claim_ids:
        for e in claims[cid]["evidence_ids"]:
            if e not in ids:
                ids.append(e)
    return ids


def element_evidence(process: dict, step_ids=(), material_ids=()) -> list[str]:
    steps = {s["step_id"]: s for s in process["steps"]}
    materials = {m["material_id"]: m for m in process.get("materials", [])}
    ids: list[str] = []
    for e in [e for s in step_ids for e in steps[s]["evidence_ids"]] + \
             [e for m in material_ids for e in materials[m]["evidence_ids"]]:
        if e not in ids:
            ids.append(e)
    return ids


def steps_text(process: dict) -> list[str]:
    return [f"{s.get('actor', '')}{s['action']}" for s in
            sorted(process["steps"], key=lambda s: s["order"])]


def current_processes(repository: ResearchRepository) -> list[dict]:
    """Processes a current-rule question can be built on (legacy versions excluded)."""
    # Legacy versions, plus the disciplinary withdrawal, which the school initiates
    # and a student does not apply for.
    legacy = {"PROC_UG_WITHDRAWAL_V001", "PROC_UG_WITHDRAWAL_V002", "PROC_UG_WITHDRAWAL_V003",
              "PROC_UG_SUSPEND_LEGACY_V001", "PROC_UG_RESUME_LEGACY_V001",
              "PROC_UG_STATUS_CHANGE_V001"}
    return [p for p in repository.processes.values() if p["process_id"] not in legacy]


def make_plans(repository: ResearchRepository) -> list[dict]:
    processes = current_processes(repository)
    rng = stable_rng("plan-v1")
    plans: list[dict] = []

    multi = [p for p in processes if len(p["steps"]) >= 3
             and all(len(s["next_step_ids"]) <= 1 for s in p["steps"])]
    for index in range(PLAN["procedure"]):
        p = multi[index % len(multi)]
        step_ids = [s["step_id"] for s in sorted(p["steps"], key=lambda s: s["order"])]
        material_ids = [m["material_id"] for m in p.get("materials", [])]
        plans.append({"kind": "procedure", "process": p, "steps": step_ids,
                      "materials": material_ids, "claims": [], "variant": index // len(multi)})

    fact_types = {"time_constraint", "service_location", "fee", "entry", "material"}
    facts = [(p, c) for p in processes for c in p["allowed_claims"]
             if c.get("claim_type") in fact_types]
    rng.shuffle(facts)
    seen_items: Counter = Counter()
    for p, c in facts:
        if len([x for x in plans if x["kind"] == "fact"]) >= PLAN["fact"]:
            break
        if seen_items[p["item_id"]] >= 3:
            continue
        seen_items[p["item_id"]] += 1
        plans.append({"kind": "fact", "process": p, "claims": [c["claim_id"]], "steps": [],
                      "materials": [], "claim_text": c["text"]})

    ordered = [p for p in multi if len(p["steps"]) >= 3]
    rng.shuffle(ordered)
    for index in range(PLAN["premise"]):
        p = ordered[index % len(ordered)]
        steps = sorted(p["steps"], key=lambda s: s["order"])
        a = rng.randrange(len(steps) - 1)
        b = a + 1
        kind, template = WRONG_TEMPLATES[index % len(WRONG_TEMPLATES)]
        wrong = template.format(a=a + 1, b=b + 1, sa=steps_text(p)[a], sb=steps_text(p)[b])
        plans.append({"kind": "premise", "process": p, "steps": [steps[a]["step_id"], steps[b]["step_id"]],
                      "materials": [], "claims": [], "wrong": wrong,
                      "rule": f"先「{steps_text(p)[a]}」，再「{steps_text(p)[b]}」"})

    # Slots whose value changes the answer (checked by hand against the evidence);
    # others, such as the course-selection phase, can be answered for every value.
    # Values for slots the records leave open are taken from the evidence wording.
    branching = {
        ("PROC_UG_WITHDRAWAL_V005", "SL_CLEANUP_CATEGORY"): None,
        ("PROC_UG_RESUME_PROCESS_V001", "SL_RESUME_REASON"): None,
        ("PROC_UG_PROOF_PRINT_ENGLISH_NAME_V001", "SL_ENGLISH_NAME_STATE"): None,
        ("PROC_UG_SUSPEND_PROCESS_V001", "SL_SUSPEND_ROUND"): None,
        ("PROC_UG_PROOF_PRINT_ALUMNI_V001", "SL_GRADUATION_YEAR"):
            ["2006 年及以后入学", "2006 年以前入学"],
        ("PROC_UG_LEAVE_REQUEST_V001", "SL_LEAVE_DAYS"):
            ["一天以内", "一天以上一周以内", "一周以上两周以内", "两周以上"],
    }
    slotted = []
    for p in repository.processes.values():
        for s in p["slots"]:
            key = (p["process_id"], s["slot_id"])
            if key in branching:
                values = branching[key] or s["allowed_values"]
                slotted.append((p, {**s, "allowed_values": values}))
    rng.shuffle(slotted)
    for index in range(PLAN["missing"]):
        p, s = slotted[index % len(slotted)]
        plans.append({"kind": "missing", "process": p, "slot": s, "steps": [], "materials": [],
                      "claims": []})
    for index in range(PLAN["dialogue"]):
        p, s = slotted[index % len(slotted)]
        value = s["allowed_values"][index % len(s["allowed_values"])]
        plans.append({"kind": "dialogue", "process": p, "slot": s, "value": value,
                      "steps": [st["step_id"] for st in sorted(p["steps"], key=lambda x: x["order"])],
                      "materials": [], "claims": []})

    for index in range(PLAN["version"]):
        old_id, old_claim, new_id, new_claim, point = VERSION_PAIRS[index % len(VERSION_PAIRS)]
        old_process = repository.processes[old_id or "PROC_UG_WITHDRAWAL_V003"]
        plans.append({"kind": "version", "process": repository.processes[new_id],
                      "old_process": old_process, "point": point,
                      "old_claim_id": old_claim, "new_claim_id": new_claim,
                      "steps": [], "materials": [], "claims": []})

    for index in range(PLAN["outside"]):
        plans.append({"kind": "outside", "topic": OUTSIDE_TOPICS[index % len(OUTSIDE_TOPICS)],
                      "process": None, "steps": [], "materials": [], "claims": []})
    return plans


def version_texts(plan: dict) -> tuple[str, str]:
    claims_new = {c["claim_id"]: c for c in plan["process"]["allowed_claims"]}
    plan["new_claim"] = claims_new[plan["new_claim_id"]]
    if plan["old_claim_id"] is None:
        # A requirement absent from the older form.
        plan["old_claim"] = {"claim_id": None, "text": "旧版表格没有这项要求"}
    else:
        claims_old = {c["claim_id"]: c for c in plan["old_process"]["allowed_claims"]}
        plan["old_claim"] = claims_old[plan["old_claim_id"]]
    return plan["old_claim"]["text"], plan["new_claim"]["text"]


def plain_title(title: str) -> str:
    """Drop the version wording a student would not know, e.g. "2025 年 1 月表格："."""
    import re
    title = re.sub(r"^[0-9]{4} 年[^：]*：", "", title)
    return re.sub(r"[（(][^）)]*(版本|表格)[^）)]*[）)]", "", title).strip()


def write_question(client, plan: dict, index: int) -> list[str]:
    p = plan["process"]
    persona = f"\n提问者是一位{PERSONAS[index % len(PERSONAS)]}，措辞符合这个身份。"
    title = p["title"] if p else ""
    audience = "、".join(p.get("audience") or []) if p else ""
    if plan["kind"] == "procedure":
        user = PROMPT["procedure"].format(plain=plain_title(title), audience=audience)
    elif plan["kind"] == "fact":
        user = PROMPT["fact"].format(title=title, claim=plan["claim_text"])
    elif plan["kind"] == "premise":
        user = PROMPT["premise"].format(title=title, claim=plan["rule"], wrong=plan["wrong"])
    elif plan["kind"] == "missing":
        s = plan["slot"]
        user = PROMPT["missing"].format(title=title, slot=s["name"], values="、".join(s["allowed_values"]))
    elif plan["kind"] == "version":
        old, new = version_texts(plan)
        user = PROMPT["version"].format(title=title, point=plan["point"], old=old, new=new,
                                        old_label=plan["old_process"]["title"], new_label=p["title"])
    elif plan["kind"] == "outside":
        user = PROMPT["outside"].format(topic=plan["topic"])
    else:
        s = plan["slot"]
        user = PROMPT["dialogue"].format(title=title, slot=s["name"], value=plan["value"])
        data = client.chat_json([{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": user + persona}], max_tokens=600)
        turns = [str(t).strip() for t in data.get("turns") or [] if str(t).strip()]
        if len(turns) != 3:
            raise ValueError("dialogue did not have three turns")
        return turns
    text = client.chat([{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": user + persona}],
                       max_tokens=300).strip().strip('"“”')
    if not text:
        raise ValueError("empty question")
    return [text]


def to_sample(plan: dict, turns: list[str], index: int) -> dict:
    p = plan["process"]
    kind = plan["kind"]
    mode = MODE[kind]
    item = p["item_id"] if p else None
    code = ITEM_CODE.get(item, "XX") if item else "OS"
    claims, steps, materials = list(plan["claims"]), list(plan["steps"]), list(plan["materials"])
    missing, follow_up = [], None
    if kind == "missing":
        missing = [plan["slot"]["slot_id"]]
        follow_up = f"请问您的{plan['slot']['name']}是？"
    if kind == "version":
        claims = [plan["new_claim"]["claim_id"]]
    evidence = []
    if p:
        if kind == "missing":
            evidence = list(plan["slot"].get("evidence_ids") or [])
        else:
            evidence = claim_evidence(p, claims) + [e for e in element_evidence(p, steps, materials)
                                                    if e not in claim_evidence(p, claims)]
    roles = ["user"] if len(turns) == 1 else ["user", "assistant", "user"]
    boundary = {
        "procedure": "按顺序说明办理步骤及所需材料，不补充证据之外的环节。",
        "fact": "直接给出所问事实，不展开无关流程。",
        "premise": "先指出提问中与规定不符之处，再给出正确做法。",
        "missing": "先追问缺少的条件，不要直接给出某一种情形的答案。",
        "version": "说明依据的是哪个版本的来源，并指出与旧版说法的差异。",
        "outside": "说明现有官方材料未涉及，不凭常识作答。",
        "dialogue": "结合学生补充的条件，说明对应的办理步骤。",
    }[kind]
    if kind == "premise":
        boundary = f"指出：{plan['rule']}，而不是学生以为的做法；再给出正确步骤。"
    if kind == "version":
        boundary = (f"现行依据为《{p['title']}》：{plan['new_claim']['text']}；"
                    f"旧版《{plan['old_process']['title']}》为：{plan['old_claim']['text']}。")
    scenario = {"procedure": "direct", "fact": "direct", "premise": "step_error",
                "missing": "condition_missing", "version": "version_conflict",
                "outside": "out_of_scope", "dialogue": "multi_turn"}[kind]
    return {
        "schema_version": "1.0",
        "dataset_id": DATASET_ID,
        "sample_id": f"CFM-{code}-{index:03d}",
        "allocation_item_id": item,
        "item_id": item,
        "process_id": p["process_id"] if p else None,
        "split": "confirm",
        "scenario_type": scenario,
        "difficulty": "medium",
        "version_risk": "cross_version_conflict" if kind == "version" else "stable",
        "turn_structure": "single_turn" if len(turns) == 1 else "multi_turn",
        "conversation": [{"turn_id": f"T{i + 1:02d}", "role": r, "text": t}
                         for i, (r, t) in enumerate(zip(roles, turns))],
        "input_context": {"provided_slots": [], "requested_as_of": None,
                          "source_version_ids": sorted({e for e in evidence})[:0]},
        "gold": {
            "response_mode": mode, "target_item_id": item,
            "required_slot_ids": missing, "missing_slot_ids": missing,
            "follow_up_question": follow_up,
            "ordered_step_ids": steps, "material_ids": materials, "allowed_claim_ids": claims,
            "supporting_evidence_ids": evidence,
            "prohibited_claims": ["证据未支持的规则", "其他对象或版本的条件"],
            "answer_boundary": boundary,
        },
        "leakage_control": {
            "template_family_id": f"TPL_CFM_{kind.upper()}",
            "source_version_group_ids": ["SVG_CFM"],
            "semantic_cluster_id": f"SEM_CFM_{index:03d}",
            "construction_origin": "official_source_derived",
            "prohibited_overlap_sample_ids": [],
            "check_status": "pending", "checked_at": None, "checker": None,
            "notes": kind + (f"；{plan.get('topic')}" if kind == "outside" else ""),
        },
        "review_status": "draft",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    repository = ResearchRepository(ROOT)
    client = judge_client(ROOT / "data/cache")
    plans = make_plans(repository)
    if args.limit:
        plans = plans[: args.limit]
    print(f"计划 {len(plans)} 条：{dict(Counter(p['kind'] for p in plans))}", flush=True)

    def work(pair):
        index, plan = pair
        for attempt in range(3):
            try:
                return index, plan, write_question(client, plan, index + attempt), None
            except Exception as error:  # noqa: BLE001 - retried, then recorded
                last = f"{type(error).__name__}: {error}"[:200]
        return index, plan, None, last

    samples, failures = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, plan, turns, error in pool.map(work, enumerate(plans, 1)):
            if error:
                failures.append({"index": index, "kind": plan["kind"], "error": error})
            else:
                samples.append(to_sample(plan, turns, index))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"写出 {len(samples)} 条 -> {OUTPUT.relative_to(ROOT)}；失败 {len(failures)}")
    for failure in failures[:5]:
        print("  ", failure)
    print(f"cost: {client.cost_summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
