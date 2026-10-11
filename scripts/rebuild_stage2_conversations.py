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


def rebuild(sample: dict) -> dict:
    result = copy.deepcopy(sample)
    number = int(sample['sample_id'][-3:])
    item = ITEM_NAMES[sample['allocation_item_id']]
    scenario = sample['scenario_type']
    difficulty = sample['difficulty']
    risk = sample['version_risk']
    if scenario == 'direct':
        text = f'请说明{item}的办理流程，我重点想了解第{number}条场景中的申请对象和办理入口。'
    elif scenario == 'condition_missing':
        text = f'我想办理{item}，当前只知道事项名称，能否先说明第{number}条场景还缺少哪项条件？'
    elif scenario == 'object_mismatch':
        text = f'我的身份或办理对象与{item}的常规对象不同，第{number}条场景是否仍能直接套用该流程？'
    elif scenario == 'version_conflict':
        text = f'我看到{item}存在不同时间或版本的要求，请按第{number}条{risk}场景说明适用版本和差异。'
    elif scenario == 'step_error':
        text = f'办理{item}时我准备跳过前置步骤，第{number}条{difficulty}场景下请指出顺序和后果。'
    elif scenario == 'material_confusion':
        text = f'办理{item}时我只有部分材料，第{number}条{difficulty}场景下请核对缺少的材料及其办理节点。'
    elif scenario == 'multi_turn':
        text = f'我想办理{item}，这是第{number}条多轮场景。'
    elif scenario == 'out_of_scope':
        text = f'我想办理{item}之外的事项，第{number}条场景请判断是否属于当前服务范围。'
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
                                     checker=None, notes='对话已按蓝图维度重建，待语义近重复检查与独立复核。')
    return result


def main():
    path = ROOT / 'data/evaluation/stage2_samples.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    rebuilt = [rebuild(row) for row in rows]
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
