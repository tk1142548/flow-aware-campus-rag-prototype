import json,hashlib
from pathlib import Path
e=Path('data/research/evidence_units.jsonl');s=hashlib.sha256(e.read_bytes()).hexdigest();p=Path('data/research/process_records.jsonl');a=[json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()];
for x in a:x['evidence_snapshot']['dataset_sha256']=s
p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in a)+'\n',encoding='utf8')
