import json,hashlib
from pathlib import Path
p=Path('data/research/process_records.jsonl');s=p.read_text(encoding='utf8');d=json.JSONDecoder();i=0;rows=[]
while i<len(s):
 while i<len(s) and s[i].isspace():i+=1
 if i>=len(s):break
 x,j=d.raw_decode(s,i);rows.append(x);i=j
print('rows',len(rows));e=Path('data/research/evidence_units.jsonl');sha=hashlib.sha256(e.read_bytes()).hexdigest()
for x in rows:x['evidence_snapshot']['dataset_sha256']=sha
p.write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in rows),encoding='utf8')
