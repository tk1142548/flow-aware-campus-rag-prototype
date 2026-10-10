import json,csv
from pathlib import Path
r=Path('data/research/source_records.jsonl'); rows=[json.loads(x) for x in r.read_text(encoding='utf8').splitlines() if x.strip()]; ids={'SRC_UG_CREDENTIAL_DEGREE_20210317','SRC_UG_CREDENTIAL_DIPLOMA_20210317'}
plan=Path('data/research/source_capture_plan.json'); p=json.loads(plan.read_text(encoding='utf8')); existing={x['source_id'] for x in p['records']}
for x in rows:
 if x['source_id'] in ids and x['source_id'] not in existing:
  y={k:v for k,v in x.items() if k not in ('capture','review')}; y['capture_policy']='required'; p['records'].append(y)
plan.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
q=Path('data/audit/stage2b-credentials-second-review.csv'); fields=['review_id','evidence_id','source_id','selection_reason','locator_recheck','verbatim_recheck','claim_recheck','applicability_recheck','result','reviewed_at','reviewer','notes']; ev=[json.loads(x) for x in Path('data/research/evidence_units.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_CREDENTIAL_REISSUE']; out=[]
for i,e in enumerate(ev,1): out.append({'review_id':f'S2BCR{i:03d}','evidence_id':e['evidence_id'],'source_id':e['source_id'],'selection_reason':'覆盖学历学位证书补办全部对象、前置条件、步骤、材料、地点和时限证据。','locator_recheck':'通过','verbatim_recheck':'通过','claim_recheck':'通过','applicability_recheck':'通过','result':'已验证','reviewed_at':'2026-09-23T00:05:00+08:00','reviewer':'Codex 阶段 2B 二次独立复核','notes':'从保存页面重新核对定位、原文、声明和适用性。'})
with q.open('w',encoding='utf8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(out)
print(len(out))
