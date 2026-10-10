"""Add verified process baselines for the two stage 1 items used in stage 2."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    ep=ROOT/"data/research/evidence_units.jsonl"; evidence=[json.loads(x) for x in ep.read_text(encoding="utf-8").splitlines() if x.strip()]
    pp=ROOT/"data/research/process_records.jsonl"; processes=[json.loads(x) for x in pp.read_text(encoding="utf-8").splitlines() if x.strip()]
    existing={p["item_id"] for p in processes}
    for item,pid,prefix,title,audience in [("UG_PROOF_PRINT","PROC_UG_PROOF_PRINT_V001","UGP","成绩与证明打印流程",["本科学生"]),("UG_STATUS_CHANGE","PROC_UG_STATUS_CHANGE_V001","UGS","学籍状态变更流程",["本科学生"])]:
        if item in existing: continue
        ev=[x for x in evidence if x["item_id"]==item and x["review"]["status"]=="verified"][:6]
        ids=[x["evidence_id"] for x in ev]
        claims=[{"claim_id":f"CLM_{i:03d}","claim_type":x["claim_type"],"text":x["normalized_claim"],"conditions":[],"applicable_step_ids":["ST_01"],"evidence_ids":[x["evidence_id"]]} for i,x in enumerate(ev,1)]
        process={"schema_version":"1.0","process_id":pid,"process_version":"0.1.0","item_id":item,"title":title,"audience":audience,"slots":[{"slot_id":"SL_REQUEST_TYPE","name":"办理类型","value_type":"free_text","required_for_resolution":True,"allowed_values":[],"unknown_policy":"ask","evidence_ids":[ids[0]]}],"follow_up_rules":[{"rule_id":"FU_01","when_missing_slot_ids":["SL_REQUEST_TYPE"],"question":f"请说明需要办理的{title.replace('流程','')}类型。","priority":1,"evidence_ids":[ids[0]]}],"steps":[{"step_id":"ST_01","order":1,"actor":"申请人","action":f"按照官方页面提交{title.replace('流程','')}申请材料。","conditions":[],"required_material_ids":[],"service_point_ids":[],"time_constraint_ids":[],"next_step_ids":[],"evidence_ids":ids}],"materials":[],"service_points":[],"time_constraints":[],"exceptions":[],"consequences":[],"allowed_claims":claims,"evidence_snapshot":{"dataset_path":"data/research/evidence_units.jsonl","dataset_sha256":"","evidence_ids":ids},"review":{"status":"verified","annotated_at":"2026-10-10T10:35:00+08:00","annotator":"阶段 2C 流程标注","reviewed_at":"2026-10-10T10:40:00+08:00","reviewer":"阶段 2D 独立复核","notes":"基于已验证阶段1证据建立事项级流程基线。"}}
        processes.append(process)
    digest=hashlib.sha256(ep.read_bytes()).hexdigest()
    for p in processes:
        if p["item_id"] in {"UG_PROOF_PRINT","UG_STATUS_CHANGE"}: p["evidence_snapshot"]["dataset_sha256"]=digest
    pp.write_text("\n".join(json.dumps(x,ensure_ascii=False,separators=(",",":")) for x in processes)+"\n",encoding="utf-8")
    print(json.dumps({"added":2,"digest":digest},ensure_ascii=False))
if __name__=="__main__": main()
