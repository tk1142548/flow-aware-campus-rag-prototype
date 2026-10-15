"""Rebuild stage 2 conversations from allocation dimensions and process claims."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEM_NAMES = {
    'UG_PROOF_PRINT': '成绩与证明打印', 'UG_STATUS_CHANGE': '休学复学与学籍状态',
    'UG_WITHDRAWAL': '退学办理', 'UG_CREDENTIAL_REISSUE': '学历学位证书补办',
    'UG_STUDENT_CARD_REISSUE': '学生证补办', 'UG_COURSE_SELECTION': '本科选课',
    'UG_LEAVE_REQUEST': '本科生请假', 'UG_MAJOR_CHANGE': '本科生转专业',
}


def rebuild(sample: dict, process: dict | None = None) -> dict:
    result = copy.deepcopy(sample)
    number = int(sample['sample_id'][-3:])
    item = ITEM_NAMES[sample['allocation_item_id']]
    scenario = sample['scenario_type']
    difficulty = sample['difficulty']
    risk = sample['version_risk']
    claims = sample.get('gold', {}).get('allowed_claim_ids', [])
    focus = claims[(number - 1) % len(claims)] if claims else None
    claim_text = ''
    if process and focus:
        claim_text = next((c['text'] for c in process['allowed_claims'] if c['claim_id'] == focus), '')
    if scenario == 'direct':
        focus_type = ['适用对象', '办理地点', '办理时限', '所需材料'][(number - 1) % 4]
        text = f'我准备办理{item}，这次最关心{focus_type}。请核对以下流程声明并说明它在整体流程中的位置：{claim_text}'
    elif scenario == 'condition_missing':
        slot = (sample.get('gold', {}).get('required_slot_ids') or ['办理类型'])[0]
        missing_questions = [
            f'我只知道事项名称，不确定本人是否符合{item}的适用对象条件。',
            f'我没有说明{item}的具体办理类型，系统应先追问哪一项。',
            f'我尚未提供与{item}有关的当前学期、日期或状态，是否必须先补充。',
            f'我没有说明{item}的办理渠道和地点，流程应如何处理这个缺口。',
        ]
        values = [] if not process else [v for s in process.get('slots', []) if s['slot_id'] == slot for v in s.get('allowed_values', [])]
        value_hint = '、'.join(values) if values else '具体值'
        text = f'我想办理{item}，当前没有提供{slot}。{missing_questions[(number - 1) % len(missing_questions)]}已知可能值包括{value_hint}，请说明需要补充什么条件以及为什么。'
    elif scenario == 'object_mismatch':
        alternatives = ['交换生', '研究生', '校外人员', '已毕业校友']
        text = f'我的办理对象是{alternatives[(number - 1) % len(alternatives)]}，与{item}流程中的适用对象不同，请结合这条流程声明判断能否适用，并限定回答范围：{claim_text}'
    elif scenario == 'version_conflict':
        dates = ['2019年流程页', '2025年表格', '当前办理日期']
        text = f'我看到{item}在{dates[(number - 1) % len(dates)]}存在要求，请围绕这条声明说明{risk}场景下的适用版本和差异：{claim_text}'
    elif scenario == 'step_error':
        text = f'办理{item}时我准备跳过一个前置环节，请按{difficulty}难度核对以下步骤声明的顺序和证据边界：{claim_text}'
    elif scenario == 'material_confusion':
        text = f'办理{item}时我只有部分材料，请核对以下声明对应的材料要求、办理节点和缺失材料处理方式：{claim_text}'
    elif scenario == 'multi_turn':
        text = f'我想办理{item}，先请说明下面这条声明涉及的事项：{claim_text}'
    elif scenario == 'out_of_scope':
        alternatives = ['住宿证明', '海外签证', '校外就业登记', '科研经费报销']
        text = f'我想办理{alternatives[(number - 1) % len(alternatives)]}，请判断它是否属于{item}服务范围并说明拒答边界。'
    else:
        raise ValueError(f'unsupported scenario: {scenario}')
    conversation = [{'turn_id': 'T01', 'role': 'user', 'text': text}]
    if sample['turn_structure'] == 'multi_turn':
        conversation.extend([
            {'turn_id': 'T02', 'role': 'assistant', 'text': f'请补充与{item}相关的办理对象或条件。'},
            {'turn_id': 'T03', 'role': 'user', 'text': f'我补充第{number}条场景所需信息，请继续核对{risk}要求。'},
        ])
    result['conversation'] = conversation
    result['review_status'] = 'draft'
    result['leakage_control'].update(check_status='pending', checked_at=None,
                                     checker=None, notes='对话已按蓝图维度重建，待语义近重复检查与核验。')
    return result


def main():
    path = ROOT / 'data/evaluation/stage2_samples.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    process_rows = [json.loads(line) for line in (ROOT / 'data/research/process_records.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    processes = {row['process_id']: row for row in process_rows}
    rebuilt = [rebuild(row, processes.get(row['process_id'])) for row in rows]
    keys = [tuple((turn['role'], turn['text']) for turn in row['conversation']) for row in rebuilt]
    if len(keys) != len(set(keys)):
        raise ValueError('rebuild did not produce unique conversations')
    ledger = ROOT / 'data/audit/stage2-conversation-rebuild.json'
    ledger.write_text(json.dumps({'status': '已完成待验证', 'sample_count': len(rows),
        'unique_conversations': len(set(keys)), 'duplicate_excess': 0,
        'review_reset_count': len(rows), 'basis': '蓝图事项、场景、难度和版本风险'}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp = path.with_suffix('.jsonl.tmp')
    temp.write_text(''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n' for row in rebuilt), encoding='utf-8')
    temp.replace(path)
    print(json.dumps({'sample_count': len(rows), 'unique_conversations': len(set(keys)), 'duplicate_excess': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
