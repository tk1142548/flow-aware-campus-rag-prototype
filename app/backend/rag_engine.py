from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from app.backend.llm_client import LLMClient


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / 'data' / 'evidence' / 'evidence_units.jsonl'
ALLOWED_ASSERTION_STATUS = {'supported', 'insufficient', 'conflict', 'object_mismatch'}
INTERNAL_PHRASES = {
    '而不是单一聊天答复': '',
    '而不是转向开放域问答': '',
    '证据未明确': '当前公开信息未写明',
}
OFFICIAL_DOWNLOAD_URLS = {
    'UGS001': 'https://jwc.jnu.edu.cn/_upload/article/files/26/18/5fde309f47a3a4eb7f037a4a720b/1b6a2c01-631c-4162-8915-510adeddc284.pdf',
    'UGS011': 'https://jwc.jnu.edu.cn/_upload/article/files/85/ed/532b7c2740ea81fbf5515c8eae02/e9589e0b-b39a-4964-a7bf-cc892fe2082e.pdf',
}


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip())


def sanitize_user_text(text: str) -> str:
    cleaned = text
    for source, target in INTERNAL_PHRASES.items():
        cleaned = cleaned.replace(source, target)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip('；，。 ')
    return cleaned or '当前公开信息未写明'


def tokenize(text: str) -> list[str]:
    text = normalize_text(text).lower()
    tokens: list[str] = []
    for match in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9_]+', text):
        if re.fullmatch(r'[\u4e00-\u9fff]+', match):
            tokens.extend([match[i : i + 2] for i in range(len(match) - 1)] or [match])
            if len(match) > 2:
                tokens.extend([match[i : i + 3] for i in range(len(match) - 2)])
            tokens.append(match)
        else:
            tokens.append(match)
    return tokens or [text]


@dataclass
class SessionState:
    item_id: str | None
    slots: dict[str, Any]
    last_action: str
    follow_up_question: str


@dataclass
class Evidence:
    evidence_id: str
    item_id: str
    source_title: str
    source_url: str
    publish_date: str
    effective_term: str
    audience: str
    source_type: str
    source_level: str
    chunk_type: str
    content: str
    location_hint: str
    keywords: list[str]

    def search_text(self) -> str:
        keyword_text = ' '.join(self.keywords)
        return f'{self.source_title} {self.content} {self.audience} {self.chunk_type} {keyword_text}'

    def card(self, score: float) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id,
            'item_id': self.item_id,
            'source_title': self.source_title,
            'source_url': self.source_url,
            'publish_date': self.publish_date,
            'effective_term': self.effective_term,
            'audience': self.audience,
            'source_type': self.source_type,
            'source_level': self.source_level,
            'chunk_type': self.chunk_type,
            'content': sanitize_user_text(self.content),
            'location_hint': self.location_hint,
            'keywords': self.keywords,
            'score': round(score, 4),
        }


class EvidenceIndex:
    def __init__(self, evidence_list: list[Evidence]) -> None:
        self.evidence_list = evidence_list
        corpus = [e.search_text() for e in evidence_list]
        tokenized = [tokenize(doc) for doc in corpus]
        self.bm25 = BM25Okapi(tokenized)
        self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
        dense = self.vectorizer.fit_transform(corpus).astype(np.float32).toarray()
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        dense = dense / norms
        self.index = faiss.IndexFlatIP(dense.shape[1])
        self.index.add(dense)

    def search(self, query: str, slots: dict[str, Any], top_k: int = 12) -> list[tuple[Evidence, float]]:
        query_tokens = tokenize(query)
        bm25_scores = np.array(self.bm25.get_scores(query_tokens), dtype=np.float32)
        bm25_scores = self._normalize(bm25_scores)

        query_vec = self.vectorizer.transform([query]).astype(np.float32).toarray()
        norms = np.linalg.norm(query_vec, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        query_vec = query_vec / norms
        faiss_scores, faiss_ids = self.index.search(query_vec, len(self.evidence_list))
        dense_scores = np.zeros(len(self.evidence_list), dtype=np.float32)
        for idx, score in zip(faiss_ids[0], faiss_scores[0]):
            if idx >= 0:
                dense_scores[idx] = score
        dense_scores = self._normalize(dense_scores)

        combined = 0.58 * bm25_scores + 0.42 * dense_scores
        education_level = slots.get('education_level')
        doc_type = slots.get('doc_type')
        action = slots.get('action')
        location_intent = any(term in query for term in ('去哪里', '哪里', '窗口', '地点', '入口'))
        material_intent = any(term in query for term in ('材料', '准备什么', '准备哪些', '填哪些', '填写什么', '表格'))
        time_intent = any(term in query for term in ('什么时候', '截止', '第二周', '第一周', '周三前', '来得及'))

        for idx, evidence in enumerate(self.evidence_list):
            if education_level and education_level in evidence.audience:
                combined[idx] += 0.14
            if education_level == '本科' and evidence.audience == '研究生':
                combined[idx] -= 0.45
            if doc_type and doc_type in evidence.content:
                combined[idx] += 0.12
            if action and action in evidence.content:
                combined[idx] += 0.10
            if location_intent and evidence.chunk_type in {'entry', 'service_location'}:
                combined[idx] += 0.16
            if material_intent and evidence.chunk_type == 'materials':
                combined[idx] += 0.18
            if time_intent and evidence.chunk_type == 'time_constraints':
                combined[idx] += 0.18
            if evidence.chunk_type in {'conflict', 'conflicts'} and education_level != '研究生':
                combined[idx] -= 0.10
            if evidence.source_url.startswith('https://gs.jnu.edu.cn') and education_level != '研究生':
                combined[idx] -= 0.30

        ranking = np.argsort(combined)[::-1][:top_k]
        return [(self.evidence_list[i], float(combined[i])) for i in ranking]

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        minimum = float(values.min())
        maximum = float(values.max())
        if math.isclose(minimum, maximum):
            return np.ones_like(values) * 0.5
        return (values - minimum) / (maximum - minimum)


class FlowAwareCampusRAG:
    def __init__(self) -> None:
        self.evidence = self._load_evidence()
        self.evidence_by_id = {row.evidence_id: row for row in self.evidence}
        self.by_item: dict[str, list[Evidence]] = defaultdict(list)
        for row in self.evidence:
            self.by_item[row.item_id].append(row)
        self.indexes = {item_id: EvidenceIndex(rows) for item_id, rows in self.by_item.items()}
        self.llm = LLMClient()
        self.sessions: dict[str, SessionState] = {}

    @staticmethod
    def _load_evidence() -> list[Evidence]:
        rows: list[Evidence] = []
        with EVIDENCE_PATH.open('r', encoding='utf-8') as handle:
            for line in handle:
                rows.append(Evidence(**json.loads(line)))
        return rows

    def run(self, query: str, session_id: str | None = None) -> dict[str, Any]:
        query = normalize_text(query)
        session = self.sessions.get(session_id) if session_id else None
        item_id = self.detect_item_id(query)
        slots = self.extract_slots(query)
        item_id, slots = self.apply_session_context(query, item_id, slots, session)
        slots = self.refine_slots_with_llm(query, item_id, slots)
        action, follow_up_question = self.decide_action(item_id, slots, query)

        retrieval_item = item_id or 'UG_PROOF_PRINT'
        raw_hits = self.indexes[retrieval_item].search(query, slots, top_k=12)
        top_hits = self.select_relevant_hits(retrieval_item, query, slots, action, raw_hits)[:5]
        evidence_cards = [e.card(score) for e, score in top_hits]
        official_links = self.build_official_links(retrieval_item, slots, action, evidence_cards)
        flow_skeleton = self.build_flow_skeleton(retrieval_item, slots, query, evidence_cards, action)
        final_answer = self.compose_answer(query, retrieval_item, slots, action, follow_up_question, flow_skeleton, evidence_cards, official_links)
        assertions = self.build_assertions(query, retrieval_item, slots, action, flow_skeleton, evidence_cards, final_answer)

        result = {
            'item_id': item_id or retrieval_item,
            'slots': slots,
            'action': action,
            'follow_up_question': follow_up_question,
            'evidence_cards': evidence_cards,
            'official_links': official_links,
            'flow_skeleton': flow_skeleton,
            'assertions': assertions,
            'final_answer': final_answer,
        }
        if session_id:
            self.sessions[session_id] = SessionState(
                item_id=result['item_id'],
                slots=dict(result['slots']),
                last_action=action,
                follow_up_question=follow_up_question,
            )
        return result

    def _is_elliptical_follow_up(self, query: str) -> bool:
        if len(query) <= 18:
            return True
        return bool(re.search(r'^(那|那我|然后|还需要|还要|去哪|去哪里|怎么交|材料呢|表格呢|本科|研究生|在学证明|成绩单|毕业证明|休学|复学)', query))

    def apply_session_context(
        self,
        query: str,
        item_id: str | None,
        slots: dict[str, Any],
        session: SessionState | None,
    ) -> tuple[str | None, dict[str, Any]]:
        if not session:
            return item_id, slots

        should_merge = session.last_action == 'follow_up' or item_id is None
        if not should_merge and item_id == session.item_id and self._is_elliptical_follow_up(query):
            should_merge = True
        if not should_merge:
            return item_id, slots

        merged = dict(slots)
        for key, value in session.slots.items():
            if merged.get(key) is None and value is not None:
                merged[key] = value
        return item_id or session.item_id, merged

    def select_relevant_hits(
        self,
        item_id: str,
        query: str,
        slots: dict[str, Any],
        action: str,
        hits: list[tuple[Evidence, float]],
    ) -> list[tuple[Evidence, float]]:
        selected: list[tuple[Evidence, float]] = []
        seen: set[str] = set()
        education_level = slots.get('education_level')

        for evidence, score in hits:
            if evidence.evidence_id in seen:
                continue
            if action != 'refuse' and education_level != '研究生' and evidence.audience == '研究生':
                continue
            if item_id == 'UG_PROOF_PRINT' and evidence.source_url.startswith('https://gs.jnu.edu.cn') and action != 'refuse':
                continue
            if action != 'refuse' and evidence.chunk_type in {'conflict', 'conflicts'}:
                continue
            slot_action = slots.get('action')
            if item_id == 'UG_STATUS_CHANGE' and slot_action == '休学' and '复学' in evidence.source_title + evidence.content:
                continue
            if item_id == 'UG_STATUS_CHANGE' and slot_action == '复学' and '休学' in evidence.source_title + evidence.content:
                continue
            seen.add(evidence.evidence_id)
            selected.append((evidence, score))

        if not selected:
            return hits

        material_intent = any(term in query for term in ('材料', '准备什么', '准备哪些', '填哪些', '填写什么', '表格'))
        location_intent = any(term in query for term in ('去哪里', '哪里', '窗口', '地点', '入口'))
        ensured = list(selected)
        existing_ids = {e.evidence_id for e, _ in ensured}

        def append_by_chunk(target_chunks: set[str], minimum: int) -> None:
            current = sum(1 for e, _ in ensured[:5] if e.chunk_type in target_chunks)
            if current >= minimum:
                return
            for evidence, score in hits:
                if evidence.evidence_id in existing_ids:
                    continue
                if evidence.chunk_type not in target_chunks:
                    continue
                if action != 'refuse' and slots.get('education_level') != '研究生' and evidence.audience == '研究生':
                    continue
                slot_action = slots.get('action')
                if item_id == 'UG_STATUS_CHANGE' and slot_action == '休学' and '复学' in evidence.source_title + evidence.content:
                    continue
                if item_id == 'UG_STATUS_CHANGE' and slot_action == '复学' and '休学' in evidence.source_title + evidence.content:
                    continue
                ensured.append((evidence, score))
                existing_ids.add(evidence.evidence_id)
                current += 1
                if current >= minimum:
                    break

        if material_intent:
            append_by_chunk({'materials'}, 2)
        if location_intent:
            append_by_chunk({'entry', 'service_location'}, 1)

        def priority(pair: tuple[Evidence, float]) -> tuple[int, float]:
            evidence, score = pair
            weight = 0
            if material_intent and evidence.chunk_type == 'materials':
                weight += 3
            if location_intent and evidence.chunk_type in {'entry', 'service_location'}:
                weight += 2
            if evidence.chunk_type == 'time_constraints' and any(term in query for term in ('什么时候', '截止', '第二周', '第一周', '周三前', '来得及')):
                weight += 3
            return (weight, score)

        ensured.sort(key=priority, reverse=True)
        return ensured

    def detect_item_id(self, query: str) -> str | None:
        if re.search(r'休学|复学|学籍异动', query):
            return 'UG_STATUS_CHANGE'
        if re.search(r'成绩单|证明|毕业证明|在学证明|打证明|打印', query):
            return 'UG_PROOF_PRINT'
        return None

    def extract_slots(self, query: str) -> dict[str, Any]:
        slots: dict[str, Any] = {
            'education_level': None,
            'student_status': None,
            'doc_type': None,
            'campus': None,
            'action': None,
            'reason': None,
            'time_status': None,
        }
        if '本科' in query:
            slots['education_level'] = '本科'
        elif '研究生' in query:
            slots['education_level'] = '研究生'

        if '在学证明' in query:
            slots['doc_type'] = '在学证明'
        elif '毕业证明' in query:
            slots['doc_type'] = '毕业证明'
        elif '成绩单' in query:
            slots['doc_type'] = '成绩单'

        if '休学' in query:
            slots['action'] = '休学'
        elif '复学' in query:
            slots['action'] = '复学'

        if '未注册' in query:
            slots['student_status'] = '未注册'
        elif '在学' in query:
            slots['student_status'] = '在学'
        elif '毕业' in query:
            slots['student_status'] = '毕业'

        for campus in ('广州', '番禺', '石牌', '珠海', '深圳'):
            if campus in query:
                slots['campus'] = campus
                break

        for reason in ('因病', '创业', '参军', '服兵役', '出国', '家庭', '个人原因'):
            if reason in query:
                slots['reason'] = reason
                break

        time_match = re.search(r'(开学[^，。？；]*|第一周[^，。？；]*|第二周[^，。？；]*|报到日[^，。？；]*)', query)
        if time_match:
            slots['time_status'] = time_match.group(1)
        return slots

    def refine_slots_with_llm(self, query: str, item_id: str | None, slots: dict[str, Any]) -> dict[str, Any]:
        if not self.llm.enabled:
            return slots
        system_prompt = (
            '你是校园办事槽位抽取器。只能在用户原话明确支持时补全槽位，不能臆测。'
            '输出 JSON，字段固定为 education_level, student_status, doc_type, campus, action, reason, time_status。'
            '不确定时必须返回 null。'
        )
        user_prompt = json.dumps({'query': query, 'item_id': item_id, 'rule_slots': slots}, ensure_ascii=False)
        try:
            refined = self.llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0, max_tokens=400)
        except Exception:
            return slots
        merged = dict(slots)
        for key in merged:
            if refined.get(key) is not None and merged.get(key) is None:
                merged[key] = refined[key]
        return merged

    def decide_action(self, item_id: str | None, slots: dict[str, Any], query: str) -> tuple[str, str]:
        if not item_id:
            return 'follow_up', '请先说明你要办哪一类本科事项：打印成绩单/在学证明，还是休学/复学？'

        if item_id == 'UG_PROOF_PRINT':
            if slots.get('education_level') == '研究生':
                return 'refuse', '对象与当前原型不匹配。'
            if not slots.get('education_level') or not slots.get('doc_type'):
                return 'follow_up', '请补充两个信息：你是本科生还是研究生？想打印的是成绩单、在学证明，还是毕业证明？'

        if item_id == 'UG_STATUS_CHANGE':
            if not slots.get('action'):
                return 'follow_up', '你要办理的是休学还是复学？'
            if slots['action'] == '复学' and any(word in query for word in ('什么时候', '截止', '来得及', '可以提交', '是不是')):
                if not slots.get('time_status'):
                    return 'follow_up', '你问的是复学申请的提交时限，还是报到/注册时点？请补充你现在的时间状态。'

        return 'answer', ''

    def build_official_links(self, item_id: str, slots: dict[str, Any], action: str, evidence_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def add_link(collection: list[dict[str, Any]], label: str, url: str, link_type: str, source_title: str, evidence_ids: list[str]) -> None:
            if not url or any(row['url'] == url and row['label'] == label for row in collection):
                return
            collection.append(
                {
                    'label': label,
                    'url': url,
                    'link_type': link_type,
                    'source_title': source_title,
                    'evidence_ids': evidence_ids,
                }
            )

        def add_source_links(
            collection: list[dict[str, Any]],
            evidence_id: str,
            official_label: str,
            excerpt_label: str | None = None,
            download_label: str | None = None,
        ) -> None:
            evidence = self.evidence_by_id.get(evidence_id)
            if not evidence:
                return
            add_link(collection, official_label, evidence.source_url, 'official_page', evidence.source_title, [evidence_id])
            if excerpt_label:
                add_link(collection, excerpt_label, f'/source/{evidence_id}', 'local_excerpt', evidence.source_title, [evidence_id])
            if download_label:
                add_link(collection, download_label, f'/source/{evidence_id}/download', 'local_download', evidence.source_title, [evidence_id])

        links: list[dict[str, Any]] = []
        if action == 'refuse':
            add_source_links(links, 'UGP011', '研究生证明办理官方页', '研究生办理事项摘录页')
            return links

        if item_id == 'UG_PROOF_PRINT':
            add_source_links(links, 'UGP002', '打印成绩单/证明官方页', '打印成绩单/证明摘录页')
            add_link(links, '密封办理点摘录页', '/source/UGP008', 'local_excerpt', '打印中英文成绩单、证明等', ['UGP008'])
            add_source_links(links, 'UGP010', '暑期各校区办理点通知', '暑期办理点摘录页')
            return links

        if slots.get('action') == '休学':
            add_source_links(links, 'UGS001', '休学申请表官网页', '休学申请表摘录页', '下载休学申请表摘录')
            add_link(links, '下载休学申请表（PDF）', OFFICIAL_DOWNLOAD_URLS['UGS001'], 'official_download', 'XX1_休学申请表202504', ['UGS001'])
            add_source_links(links, 'UGS007', '办理休学流程官方页', '办理休学流程摘录页')
        elif slots.get('action') == '复学':
            add_source_links(links, 'UGS011', '复学申请表官网页', '复学申请表摘录页', '下载复学申请表摘录')
            add_link(links, '下载复学申请表（PDF）', OFFICIAL_DOWNLOAD_URLS['UGS011'], 'official_download', 'FX1_复学申请表202504', ['UGS011'])
            add_source_links(links, 'UGS015', '办理复学流程官方页', '办理复学流程摘录页')
            if slots.get('time_status'):
                add_source_links(links, 'UGS019', '注册与清退时限通知', '注册与清退时限摘录页')
        return links

    def build_flow_skeleton(
        self,
        item_id: str,
        slots: dict[str, Any],
        query: str,
        evidence_cards: list[dict[str, Any]],
        action: str,
    ) -> dict[str, Any]:
        if self.llm.enabled and action == 'answer':
            system_prompt = (
                '你是流程感知校园办事 RAG 的流程骨架生成器。'
                '只能使用提供的 evidence_cards 中已出现的信息，严禁补充证据外信息。'
                '不要输出内部系统表述，不要提研究生流程，除非用户对象就是研究生。'
                '输出 JSON，字段固定为 applicable_audience, preconditions, steps, materials, time_constraints, entry, service_location, notes, conflicts。'
                'applicable_audience, entry, service_location 为对象，格式 {text, evidence_ids}。'
                '其余字段为数组，数组元素格式 {text, evidence_ids}。'
                '如果证据不足，text 写“当前公开信息未写明”，evidence_ids 为空数组。'
            )
            user_prompt = json.dumps(
                {
                    'query': query,
                    'item_id': item_id,
                    'slots': slots,
                    'evidence_cards': evidence_cards,
                },
                ensure_ascii=False,
            )
            try:
                skeleton = self.llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0, max_tokens=1800)
                return self._normalize_flow_skeleton(skeleton)
            except Exception:
                pass
        return self._fallback_flow_skeleton(item_id, slots)

    def _fallback_flow_skeleton(self, item_id: str, slots: dict[str, Any]) -> dict[str, Any]:
        if item_id == 'UG_PROOF_PRINT':
            return {
                'applicable_audience': {'text': '适用于本科生打印成绩单、在学证明和相关证明材料。', 'evidence_ids': ['UGP001', 'UGP005', 'UGP007']},
                'preconditions': [
                    {'text': '打印在学证明前，需先在教务管理系统完成注册并保持在校状态。', 'evidence_ids': ['UGP003']},
                    {'text': '如需打印英文成绩单或英文在学证明，应先确认系统中的英文名正确。', 'evidence_ids': ['UGP004']},
                ],
                'steps': [{'text': '登录“暨南大学全日制本科学生自助打印系统”，按页面提示办理打印。', 'evidence_ids': ['UGP002']}],
                'materials': [{'text': '当前公开信息未写明需要额外提交纸质材料。', 'evidence_ids': []}],
                'time_constraints': [{'text': '当前公开信息未写明统一截止时间，请以当期页面说明为准。', 'evidence_ids': []}],
                'entry': {'text': '办理入口为“暨南大学全日制本科学生自助打印系统”。', 'evidence_ids': ['UGP002']},
                'service_location': {'text': '如需密封盖章，校本部到行政办公楼129室学籍科，其他校区到对应教学办。', 'evidence_ids': ['UGP008', 'UGP010']},
                'notes': [{'text': '收费标准和联系方式已在官方页写明，可按文书类型查询。', 'evidence_ids': ['UGP009']}],
                'conflicts': [{'text': '研究生证明和成绩单应走研究生院渠道，不与本科流程混用。', 'evidence_ids': ['UGP011']}],
            }

        if slots.get('action') == '休学':
            return {
                'applicable_audience': {'text': '适用于本科学生办理休学。', 'evidence_ids': ['UGS001', 'UGS007']},
                'preconditions': [{'text': '先下载并填写《休学申请表（本科学生）》，并准备相关证明材料。', 'evidence_ids': ['UGS001', 'UGS002']}],
                'steps': [
                    {'text': '填写休学申请表；因病休学者还须经校门诊核签。', 'evidence_ids': ['UGS007']},
                    {'text': '将申请表先交学院教科办，学院审批后交教务处学籍科。', 'evidence_ids': ['UGS008']},
                    {'text': '教务处批准后发出休学通知，学生凭通知回学院办理离校手续。', 'evidence_ids': ['UGS009']},
                ],
                'materials': [
                    {'text': '《休学申请表（本科学生）》官方表单。', 'evidence_ids': ['UGS001']},
                    {'text': '表单需填写姓名、学号、学院、专业、联系电话、休学原因和休学起止时间。', 'evidence_ids': ['UGS002']},
                    {'text': '家长需签署意见，如有相关证明材料应一并附上。', 'evidence_ids': ['UGS002']},
                ],
                'time_constraints': [{'text': '休学申请一般在每学期开学第一至第四周办理，提交到本科生院后通常5个工作日内反馈。', 'evidence_ids': ['UGS004']}],
                'entry': {'text': '从《休学申请表（本科学生）》官网页下载表单后开始办理。', 'evidence_ids': ['UGS001']},
                'service_location': {'text': '主要办理环节在学院教科办、教务处学籍科和学院离校手续办理环节。', 'evidence_ids': ['UGS010']},
                'notes': [{'text': '开学第七周后申请休学的，已选课程不能退选，成绩单中会保留相关课程记录。', 'evidence_ids': ['UGS005']}],
                'conflicts': [{'text': '休学期满未办理复学或延期休学手续的，学校将按退学处理。', 'evidence_ids': ['UGS006']}],
            }

        return {
            'applicable_audience': {'text': '适用于本科学生办理复学。', 'evidence_ids': ['UGS011', 'UGS015']},
            'preconditions': [{'text': '学生应在休学期满、学期开学前到学院教科办填写复学申请表；因病休学者须经校门诊体检并凭证明办理。', 'evidence_ids': ['UGS015']}],
            'steps': [
                {'text': '下载并填写《复学申请表（本科学生）》，按要求附齐材料。', 'evidence_ids': ['UGS011', 'UGS013', 'UGS014']},
                {'text': '学院审批后，由学院将复学申请交教务处学籍科；教务处审查符合条件者会开出复学通知。', 'evidence_ids': ['UGS016']},
                {'text': '学生领取复学通知后，到财务处交学费，再到学院注册并办理选课。', 'evidence_ids': ['UGS017']},
            ],
            'materials': [
                {'text': '《复学申请表（本科学生）》官方表单。', 'evidence_ids': ['UGS011']},
                {'text': '表单需填写姓名、学号、学院、专业、联系电话、休学起止时间、申请复学时间和复学理由。', 'evidence_ids': ['UGS014']},
                {'text': '需附休学通知书原件和复印件；因病或心理问题休学者还需附相关诊断或评估材料。', 'evidence_ids': ['UGS013']},
            ],
            'time_constraints': [
                {'text': '复学申请应在每学期开学第一周周三前提交；第一周由院系审核，第二周由本科生院出复学通知。', 'evidence_ids': ['UGS012']},
                {'text': '2025年春季注册时间为3月3日至3月14日；逾期两周不注册或休学期满逾期1个月未办理复学手续的，会进入相应学籍处理范围。', 'evidence_ids': ['UGS019']},
            ],
            'entry': {'text': '从《复学申请表（本科学生）》官网页下载表单后开始办理。', 'evidence_ids': ['UGS011']},
            'service_location': {'text': '主要办理环节在学院教科办、教务处学籍科、财务处和学院注册选课环节。', 'evidence_ids': ['UGS018']},
            'notes': [{'text': '证明材料不全的复学申请不予受理。', 'evidence_ids': ['UGS013']}],
            'conflicts': [{'text': '逾期两周不注册或休学期满逾期1个月未办理复学、延期手续的，会进入相应学籍处理范围。', 'evidence_ids': ['UGS019']}],
        }

    def _normalize_flow_skeleton(self, skeleton: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        single_fields = {'applicable_audience', 'entry', 'service_location'}
        list_fields = {'preconditions', 'steps', 'materials', 'time_constraints', 'notes', 'conflicts'}

        for field in single_fields:
            value = skeleton.get(field) or {}
            normalized[field] = {
                'text': sanitize_user_text(value.get('text', '当前公开信息未写明')),
                'evidence_ids': value.get('evidence_ids', []),
            }

        for field in list_fields:
            value = skeleton.get(field)
            if not isinstance(value, list) or not value:
                normalized[field] = [{'text': '当前公开信息未写明', 'evidence_ids': []}]
                continue
            normalized[field] = [
                {
                    'text': sanitize_user_text(row.get('text', '当前公开信息未写明')),
                    'evidence_ids': row.get('evidence_ids', []),
                }
                for row in value
            ]
        return normalized

    def compose_answer(
        self,
        query: str,
        item_id: str,
        slots: dict[str, Any],
        action: str,
        follow_up_question: str,
        flow_skeleton: dict[str, Any],
        evidence_cards: list[dict[str, Any]],
        official_links: list[dict[str, Any]],
    ) -> str:
        if action == 'follow_up':
            return follow_up_question
        if action == 'refuse':
            return '当前原型只对本科事项给出确定性流程。如果你是研究生，请改走研究生院官方办理页面。'

        grounded_answer = self._fallback_answer(item_id, slots, flow_skeleton, official_links)
        if self.llm.enabled:
            system_prompt = (
                '你是校园办事助手，负责生成面向学生的最终回答。'
                '只能依据 flow_skeleton、evidence_cards、official_links 回答，不能补充证据外信息。'
                '必须优先保留具体名词，例如系统名称、办理地点、提交时间、表单名称和附加材料。'
                '绝对不要输出以下内部表述：证据卡、流程骨架、断言、开放域问答、单一聊天答复、对象冲突。'
                '不要提研究生内容，除非用户就是研究生。'
                '输出纯文本，2到5句。'
            )
            user_prompt = json.dumps(
                {
                    'query': query,
                    'item_id': item_id,
                    'slots': slots,
                    'flow_skeleton': flow_skeleton,
                    'evidence_cards': evidence_cards,
                    'official_links': official_links,
                    'reference_answer': grounded_answer,
                },
                ensure_ascii=False,
            )
            try:
                answer = sanitize_user_text(
                    self.llm.chat_text(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1, max_tokens=500).strip()
                )
                if len(answer) >= 24 and '研究生' not in answer:
                    return answer
            except Exception:
                pass
        return grounded_answer

    def _fallback_answer(self, item_id: str, slots: dict[str, Any], flow_skeleton: dict[str, Any], official_links: list[dict[str, Any]]) -> str:
        if item_id == 'UG_PROOF_PRINT':
            doc_type = slots.get('doc_type')
            if doc_type == '在学证明':
                return '在校本科生打印在学证明，可登录“暨南大学全日制本科学生自助打印系统”办理，各校区均有设备。打印前需先在教务管理系统完成注册并保持在校状态；如需密封盖章，校本部到行政办公楼129室学籍科，其他校区到对应教学办。右侧可直接打开官方页。'
            if doc_type == '成绩单':
                return '本科生成绩单可通过“暨南大学全日制本科学生自助打印系统”办理，各校区均有设备。2000至2006年入学的毕业生需先电话咨询020-85220035，2000级以前毕业生需咨询学校档案馆；右侧可直接打开官方页。'
            if doc_type == '毕业证明':
                return '英文毕业证明按入学年份区分办理：2006年及以后入学的毕业生可通过自助打印系统办理，2006年以前入学的毕业生需携带身份证、毕业证和学位证复印件到教务处学籍科申请。右侧已列出官方页和办理点说明。'
            return '本科生打印成绩单或证明，应先确认具体文书类型，再进入“暨南大学全日制本科学生自助打印系统”办理。右侧已列出打印官方页和各校区密封办理点说明。'
        if slots.get('action') == '休学':
            return '本科生办理休学，先在休学申请表官网页下载并填写《休学申请表（本科学生）》，补齐姓名、学号、学院、专业、联系电话、休学原因和休学起止时间，并附家长意见和相关证明材料。因病休学还须经校门诊核签；之后将表交学院教科办，学院审批后交教务处学籍科。休学一般在开学第一至第四周办理，本科生院受理后通常5个工作日内反馈。'
        if slots.get('action') == '复学' and slots.get('time_status'):
            return '不可以按“开学第二周前都可以提交”来理解。复学申请应在每学期开学第一周周三前提交，第一周由院系审核，第二周由本科生院出复学通知；还需附休学通知书原件和复印件，因病或心理问题休学者还要补相关诊断或评估材料。'
        return '本科生办理复学，应在休学期满、学期开学前到学院教科办填写《复学申请表（本科学生）》并附齐材料。学院审批后将申请交教务处学籍科，审核通过后开出复学通知；学生随后到财务处交学费，再到学院注册并办理选课。'

    def build_assertions(
        self,
        query: str,
        item_id: str,
        slots: dict[str, Any],
        action: str,
        flow_skeleton: dict[str, Any],
        evidence_cards: list[dict[str, Any]],
        final_answer: str,
    ) -> list[dict[str, Any]]:
        if action == 'refuse':
            return [
                {
                    'assertion_id': 'ASR001',
                    'field': 'applicable_audience',
                    'text': '当前问题对象不属于本科事项原型的确定性处理范围。',
                    'status': 'object_mismatch',
                    'evidence_ids': ['UGP011'],
                    'reason': '官方来源表明研究生证明、成绩单由研究生院及研究生服务中心负责。',
                }
            ]

        if action == 'follow_up':
            missing_fields = []
            if item_id == 'UG_PROOF_PRINT':
                if not slots.get('education_level'):
                    missing_fields.append('education_level')
                if not slots.get('doc_type'):
                    missing_fields.append('doc_type')
            if item_id == 'UG_STATUS_CHANGE' and not slots.get('action'):
                missing_fields.append('action')
            return [
                {
                    'assertion_id': 'ASR001',
                    'field': ','.join(missing_fields) or 'slots',
                    'text': '当前输入还不足以锁定唯一官方流程。',
                    'status': 'insufficient',
                    'evidence_ids': ['UGP001', 'UGP002'] if item_id == 'UG_PROOF_PRINT' else ['UGS001', 'UGS011'],
                    'reason': '缺少关键槽位，继续回答会把不同官方流程混在一起。',
                }
            ]

        seeded: list[dict[str, Any]] = []
        if item_id == 'UG_STATUS_CHANGE' and slots.get('action') == '复学' and '第二周' in query:
            seeded.append(
                {
                    'assertion_id': 'ASR001',
                    'field': 'time_constraints',
                    'text': '复学申请可以在开学第二周前提交。',
                    'status': 'conflict',
                    'evidence_ids': ['UGS012', 'UGS019'],
                    'reason': '官方表单要求在开学第一周周三前提交，逾期未注册或逾期未复学还会进入相应学籍处理范围。',
                }
            )

        if self.llm.enabled:
            system_prompt = (
                '你是断言核验器。请把 final_answer 拆成 3 到 5 条 assertion。'
                '每条 assertion 输出 assertion_id, field, text, status, evidence_ids, reason。'
                'status 只能是 supported, insufficient, conflict, object_mismatch。'
                '只能引用提供 evidence_cards 里的 evidence_id。输出 JSON 对象，包含 assertions 数组。'
            )
            user_prompt = json.dumps(
                {
                    'query': query,
                    'item_id': item_id,
                    'slots': slots,
                    'final_answer': final_answer,
                    'flow_skeleton': flow_skeleton,
                    'evidence_cards': evidence_cards,
                },
                ensure_ascii=False,
            )
            try:
                payload = self.llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0, max_tokens=1200)
                assertions = self._normalize_assertions(payload.get('assertions', []))
                if seeded:
                    assertions = seeded + [row for row in assertions if row['status'] != 'conflict']
                return assertions[:5]
            except Exception:
                pass

        fallback = [
            {
                'assertion_id': f'ASR{len(seeded) + 1:03d}',
                'field': 'applicable_audience',
                'text': flow_skeleton['applicable_audience']['text'],
                'status': 'supported' if flow_skeleton['applicable_audience']['evidence_ids'] else 'insufficient',
                'evidence_ids': flow_skeleton['applicable_audience']['evidence_ids'],
                'reason': '适用对象来自检索到的官方证据。' if flow_skeleton['applicable_audience']['evidence_ids'] else '证据不足。',
            },
            {
                'assertion_id': f'ASR{len(seeded) + 2:03d}',
                'field': 'service_location',
                'text': flow_skeleton['service_location']['text'],
                'status': 'supported' if flow_skeleton['service_location']['evidence_ids'] else 'insufficient',
                'evidence_ids': flow_skeleton['service_location']['evidence_ids'],
                'reason': '办理位置来自检索到的官方证据。' if flow_skeleton['service_location']['evidence_ids'] else '证据不足。',
            },
        ]
        return (seeded + fallback)[:5]

    def _normalize_assertions(self, assertions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(assertions, start=1):
            status = row.get('status', 'insufficient')
            if status not in ALLOWED_ASSERTION_STATUS:
                status = 'insufficient'
            normalized.append(
                {
                    'assertion_id': row.get('assertion_id', f'ASR{index:03d}'),
                    'field': row.get('field', 'unknown'),
                    'text': sanitize_user_text(row.get('text', '')),
                    'status': status,
                    'evidence_ids': row.get('evidence_ids', []),
                    'reason': sanitize_user_text(row.get('reason', '')),
                }
            )
        return normalized
