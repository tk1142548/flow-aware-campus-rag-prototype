import json,hashlib
from pathlib import Path
p=Path('data/research/evidence_units.jsonl'); rows=[json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
for x in rows:
 if x.get('evidence_id')=='UGT006': x['source_locator']['anchor_text']='石牌校区行政办公楼 827'
p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
sha=hashlib.sha256(p.read_bytes()).hexdigest(); q=Path('data/research/process_records.jsonl'); ps=[json.loads(x) for x in q.read_text(encoding='utf8').splitlines() if x.strip()]
for x in ps: x['evidence_snapshot']['dataset_sha256']=sha
q.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in ps)+'\n',encoding='utf8')
