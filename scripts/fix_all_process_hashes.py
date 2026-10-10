import json,hashlib
from pathlib import Path
p=Path('data/research/evidence_units.jsonl'); sha=hashlib.sha256(p.read_bytes()).hexdigest(); q=Path('data/research/process_records.jsonl'); rows=[json.loads(x) for x in q.read_text(encoding='utf8').splitlines() if x.strip()]
for x in rows:x['evidence_snapshot']['dataset_sha256']=sha
q.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
