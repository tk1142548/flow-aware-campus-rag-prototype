import json,hashlib
from pathlib import Path
sp=Path('data/research/source_records.jsonl'); rows=[json.loads(x) for x in sp.read_text(encoding='utf8').splitlines() if x.strip()]
for x in rows:
 if x.get('source_id','').startswith('SRC_UG_CREDENTIAL_'): x.pop('capture_target',None)
sp.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
ep=Path('data/research/evidence_units.jsonl'); rows=[json.loads(x) for x in ep.read_text(encoding='utf8').splitlines() if x.strip()]
for x in rows:
 if x.get('evidence_id')=='UGC010': x['source_locator']['anchor_text']='凭身份证原件由本人签收领取'
 if x.get('evidence_id')=='UGC021': x['source_locator']['anchor_text']='凭身份证原件由本人签收领取'
ep.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
sha=hashlib.sha256(ep.read_bytes()).hexdigest(); pp=Path('data/research/process_records.jsonl'); ps=[json.loads(x) for x in pp.read_text(encoding='utf8').splitlines() if x.strip()]
for x in ps: x.get('evidence_snapshot',{})['dataset_sha256']=sha
pp.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in ps)+'\n',encoding='utf8')
mp=Path('data/research/stage2-source-migration-plan.csv'); txt=mp.read_text(encoding='utf8'); lines=txt.splitlines(); lines=[lines[0]]+[(','.join(l.split(',')[:-1])+',计划' if l.startswith('S2SRC002,') else l) for l in lines[1:]]; mp.write_text('\n'.join(lines)+'\n',encoding='utf8')
