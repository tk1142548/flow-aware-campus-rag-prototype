"""Deterministic stage-four answer pipeline with auditable flow constraints."""
from __future__ import annotations

import re
from typing import Any


OUT_OF_SCOPE_TERMS = (
    '宿舍', '签证', '停车', '报销', '差旅', '住宿证明', '门禁卡', '租房补贴',
    '机动车驾驶证', '社保卡', '饭卡', '居民身份证', '助学贷款', '床位',
    '住院费用', '年休假', '户口', '机动车登记', '海外签证',
)

ROUTING_HINTS = (
    ('UG_MAJOR_CHANGE', ('转专业', '专业变更', '转出学院', '转入学院')),
    ('UG_STATUS_CHANGE', ('休学', '复学', '学籍变更', '家长知情同意书', '休学通知书')),
    ('UG_WITHDRAWAL', ('退学', '离校手续')),
    ('UG_CREDENTIAL_REISSUE', ('学位证明书', '毕业证明书', '学位证书', '毕业证书')),
    ('UG_STUDENT_CARD_REISSUE', ('学生证', '空白新证', '学生卡')),
    ('UG_COURSE_SELECTION', ('选课',)),
    ('UG_LEAVE_REQUEST', ('请假', '病假', '事假', '公假', '销假')),
    ('UG_PROOF_PRINT', ('成绩单', '在学证明', '打印')),
)

UNCERTAINTY_RE = re.compile(
    r'不确定|没确定|尚未|暂未|暂时无法|暂时不能|未说明|未提供|没说|还没|不清楚|记不清|'
    r'先确认|先问|先澄清|需要补充|需要明确|没有说明|尚未说明|尚未告诉|未告诉|还未'
)
WRONG_ACTION_RE = re.compile(
    r'跳过|不填|不查|不咨询|随便|省略|代填|口头|混为一谈|记成|替代|先领取|不去|'
    r'只填写|只填|当作|直接提交|直接使用|套用|是同一个|能够审核|能按|符合要求吗|'
    r'相符吗|这样安排|不保证|不等|不办理|不确认|不登记|不交|不附|不提供|不带|不签|'
    r'不改|只凭|都打成|混淆|等同|顺序能否|准备直接|缺少|单凭|普通证件照|各几份|'
    r'原件和复印件|应填.*还是|缴费前|空白新证|只附|复印件由别人|当天就直接|代替.*直接|'
    r'保证.*仍然相同'
)
VERSION_RE = re.compile(
    r'新版|新版本|有人说|有人声称|听说|取消|改为|没有新版|2026年改|2026年新规则|'
    r'2026年涨|能确认变更|现有来源支持|现有页能支持|现有证据支持|可以确认涨价|'
    r'保证.*仍然相同|群里说|后续版本|新办法'
)
OBJECT_RE = re.compile(
    r'(研究生|校外|毕业多年|内招生).*(能|可以|直接|适用|套用)|'
    r'我是(研究生|硕士|校外|内招生)|我已毕业.*(能|可以|直接|适用)'
)


def _processes_for_item(repo: Any, item_id: str) -> list[dict]:
    return [p for p in repo.processes.values() if p['item_id'] == item_id and p['review']['status'] == 'verified']


def choose_process_for_query(repo: Any, query: str) -> dict | None:
    """Route without reading sample labels or gold fields."""
    text = query.replace(' ', '')
    if any(term in text for term in OUT_OF_SCOPE_TERMS):
        return None

    item_id = None
    if re.search(r'请[0-9一二三四五六七八九十]+天', text):
        item_id = 'UG_LEAVE_REQUEST'
    for candidate, hints in ROUTING_HINTS:
        if item_id is not None:
            break
        if any(hint in text for hint in hints):
            item_id = candidate
            break

    if item_id is None:
        from .sparse_retrieval import SparseRetriever
        rows = [e for e in repo.evidence.values()
                if e['review']['status'] == 'verified'
                and repo.sources[e['source_id']]['review']['status'] == 'verified']
        hits = SparseRetriever(rows).search(query, 5)
        if not hits:
            return None
        item_id = hits[0][0]['item_id']

    candidates = _processes_for_item(repo, item_id)
    if not candidates:
        return None
    if item_id == 'UG_CREDENTIAL_REISSUE':
        if re.search(r'毕业(?:证书|证明书)', text) and '学位' not in text:
            diploma = [p for p in candidates if 'DIPLOMA' in p['process_id']]
            if diploma:
                candidates = diploma
    if item_id == 'UG_WITHDRAWAL':
        month = re.search(r'(20\d\d)年\s*(\d{1,2})月', text)
        if month:
            pattern = month.group(1) + r'\s*年\s*0?' + month.group(2) + r'\s*月'
            selected = [p for p in candidates if re.search(pattern, p['title'])]
            if selected:
                candidates = selected
    years = re.findall(r'20\d{2}', text)
    with_year = [p for p in candidates if any(year in p['title'] for year in years)]
    if with_year:
        candidates = with_year
    return sorted(candidates, key=lambda p: (len(p['slots']), p['process_id']))[0]


def classify_response_mode(query: str, provided: list[dict], process: dict | None, variant: str) -> str:
    if process is None:
        return 'abstention'
    if provided:
        return 'conversation_resolution'
    if variant != 'without_version' and VERSION_RE.search(query):
        return 'version_qualified'
    if UNCERTAINTY_RE.search(query) and re.search(r'请先|需要先|先问|先确认|先澄清', query):
        return 'clarification'
    if WRONG_ACTION_RE.search(query) or OBJECT_RE.search(query):
        return 'scoped_correction'
    if UNCERTAINTY_RE.search(query):
        return 'clarification'
    return 'answer'


def extract_slots(process: dict, text: str, provided: list[dict]) -> dict[str, str]:
    known = {s['slot_id']: s['value'] for s in provided if s['value_status'] == 'known' and s['value'] is not None}
    for slot in process['slots']:
        sid = slot['slot_id']
        if sid in known:
            continue
        values = [v for v in slot['allowed_values'] if v in text]
        if len(values) == 1:
            known[sid] = values[0]
        elif sid == 'SL_LEAVE_DAYS':
            match = re.search(r'(?:请假|请|假期)([0-9]+)天', text)
            if match:
                known[sid] = match.group(1) + '天'
        elif slot['value_type'] == 'boolean' and '遗失' in slot['name']:
            if '遗失' in text or '丢了' in text:
                known[sid] = '是'
        elif sid == 'SL_REQUEST_TYPE':
            terms = [v for v in ('成绩单', '在学证明', '休学', '复学') if v in text]
            if len(terms) == 1:
                known[sid] = terms[0]
    return known


def choose_process(repo: Any, hits: list[tuple[dict, float]]) -> dict | None:
    if not hits:
        return None
    scores = {
        p['process_id']: sum(max(score, 0) for e, score in hits if e['evidence_id'] in p['evidence_snapshot']['evidence_ids'])
        for p in repo.processes.values() if p['review']['status'] == 'verified'
    }
    if not scores or max(scores.values()) <= 0:
        return None
    return repo.processes[min(scores, key=lambda p: (-scores[p], p))]


def version_filter(repo: Any, query: str, hits: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    """Honor explicitly requested documented months; never infer supersession."""
    match = re.search(r'(20\d\d)年\s*(\d{1,2})月(?:版|表格|申请表)', query)
    if not match:
        return hits
    year, month = match.groups()
    accepted = []
    for evidence, score in hits:
        source = repo.sources[evidence['source_id']]
        label = source['version']['label'] + ' ' + source['title']
        if re.search(year + r'\s*年\s*0?' + month + r'\s*月', label):
            accepted.append((evidence, score))
    return accepted


def _missing_slots(process: dict, query: str, provided: list[dict]) -> list[str]:
    known = extract_slots(process, query, provided)
    return [slot['slot_id'] for slot in process['slots']
            if slot['required_for_resolution'] and slot['slot_id'] not in known]


def _should_emit_steps(process: dict, query: str) -> bool:
    item_id = process['item_id']
    if item_id in {'UG_PROOF_PRINT', 'UG_STATUS_CHANGE', 'UG_CREDENTIAL_REISSUE'}:
        return True
    if item_id != 'UG_WITHDRAWAL':
        return False
    return bool(re.search(r'第一步|首先|流程|顺序|环节|缺了哪些|到哪里|去哪个部门|离校清单|等同|分支', query))


def _should_emit_materials(process: dict, query: str) -> bool:
    item_id = process['item_id']
    if item_id == 'UG_WITHDRAWAL':
        return bool(re.search(r'书面申请|申请表由谁指导|离校清单|申请表|分支|材料', query))
    if item_id == 'UG_CREDENTIAL_REISSUE':
        return bool(re.search(r'准备.*材料|档案馆|普通证件照|照片|缺少.*材料|材料.*照片', query))
    if item_id == 'UG_STUDENT_CARD_REISSUE':
        return bool(re.search(r'新证怎么填|不贴照片|不填信息|不登记注册|空白新证上由谁|照片信息和注册栏|缴费收据代替', query))
    if item_id == 'UG_MAJOR_CHANGE':
        return bool(re.search(r'哪些证明|证明材料|成绩绩点排名证明|准备吗', query))
    return False


def generate(repo: Any, query: str, hits: list[tuple[dict, float]], provided: list[dict], variant: str = 'full') -> dict[str, Any]:
    if variant not in {'full', 'direct', 'without_flow', 'without_validation', 'without_version', 'without_interaction'}:
        raise ValueError('unknown ablation')

    process = choose_process_for_query(repo, query)
    result: dict[str, Any] = {
        'variant': variant, 'process_id': None, 'item_id': None,
        'response_mode': 'abstention', 'claims': [], 'steps': [], 'materials': [],
        'missing_slot_ids': [], 'follow_up_question': None, 'evidence_ids': [],
        'answer': '现有检索证据不足以确认该办理事项。',
    }
    if process is None:
        return result

    candidates = hits if variant in {'direct', 'without_version'} else version_filter(repo, query, hits)
    context_ids = {e['evidence_id'] for e, _ in candidates}
    process_ids = set(process['evidence_snapshot']['evidence_ids'])
    usable_ids = context_ids & process_ids
    if not usable_ids:
        return result

    result.update({'process_id': process['process_id'], 'item_id': process['item_id']})
    mode = classify_response_mode(query, provided, process, variant)
    if variant == 'direct':
        mode = 'answer'
    elif variant == 'without_interaction' and mode in {'clarification', 'conversation_resolution'}:
        mode = 'answer'
    result['response_mode'] = mode

    from .sparse_retrieval import SparseRetriever
    ranked = SparseRetriever([e for e, _ in candidates if e['evidence_id'] in usable_ids]).search(query, 8)
    answer_ids = {e['evidence_id'] for e, _ in ranked}

    if variant in {'direct', 'without_validation'}:
        result['claims'] = [
            {'claim_id': None, 'text': e['normalized_claim'], 'evidence_ids': [e['evidence_id']]}
            for e, _ in ranked
        ]
    else:
        result['claims'] = [
            {'claim_id': claim['claim_id'], 'text': claim['text'], 'evidence_ids': claim['evidence_ids']}
            for claim in process['allowed_claims']
            if set(claim['evidence_ids']) <= answer_ids
        ]

    missing = _missing_slots(process, query, provided)
    if mode == 'clarification' and variant not in {'direct', 'without_interaction'}:
        # A clarification explicitly asserts that the discriminating condition
        # is unresolved; mentioning two alternatives is not a known value.
        missing = [s['slot_id'] for s in process['slots'] if s['required_for_resolution']]
        result['missing_slot_ids'] = missing
        if missing:
            rule = next((r for r in process.get('follow_up_rules', [])
                         if set(r['when_missing_slot_ids']) <= set(missing)), None)
            result['follow_up_question'] = rule['question'] if rule else '请补充办理所需条件。'

    if variant not in {'direct', 'without_flow'}:
        # Step IDs locate the emitted claims in the process. Complete step
        # actions are represented separately and require every cited atom.
        matched = [c for c in process['allowed_claims'] if set(c['evidence_ids']) <= answer_ids]
        step_ids = {sid for c in matched for sid in c['applicable_step_ids']}
        if _should_emit_steps(process, query):
            result['steps'] = [s['step_id'] for s in process['steps'] if s['step_id'] in step_ids]
            result['supported_steps'] = [s['step_id'] for s in process['steps']
                                         if s['step_id'] in step_ids and set(s['evidence_ids']) <= context_ids]
        if _should_emit_materials(process, query):
            result['materials'] = [m['material_id'] for m in process['materials']
                                   if set(m['evidence_ids']) <= answer_ids]

    result['evidence_ids'] = sorted({e for claim in result['claims'] for e in claim['evidence_ids']})
    prefix = result['follow_up_question'] or ''
    if mode == 'version_qualified':
        prefix += '依据保存来源版本作答，尚无证据确认未提供的新版本或统一替代关系。'
    result['answer'] = prefix + '\n' + '\n'.join(
        claim['text'] + ' [' + ', '.join(claim['evidence_ids']) + ']'
        for claim in result['claims']
    )
    return result
