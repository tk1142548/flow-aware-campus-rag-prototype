import json,hashlib
from pathlib import Path
p=Path('data/research/process_records.jsonl');s=p.read_text(encoding='utf8').replace(r'\n','\n');a=[json.loads(x) for x in s.splitlines() if x.strip()];e=Path('data/research/evidence_units.jsonl');sha=hashlib.sha256(e.read_bytes()).hexdigest()
for x in a:x['evidence_snapshot']['dataset_sha256']=sha
p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in a)+'\n',encoding='utf8');print(len(a))
