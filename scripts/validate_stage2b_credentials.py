import csv,json,hashlib
from pathlib import Path
r=Path('.'); ev=[json.loads(x) for x in (r/'data/research/evidence_units.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_CREDENTIAL_REISSUE']; assert len(ev)==21 and {x['evidence_id'] for x in ev}=={f'UGC{i:03d}' for i in range(1,22)}
for x in ev: assert x['review']['status']=='verified' and x['source_id'] in {'SRC_UG_CREDENTIAL_DEGREE_20210317','SRC_UG_CREDENTIAL_DIPLOMA_20210317'}
ps=[json.loads(x) for x in (r/'data/research/process_records.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_CREDENTIAL_REISSUE']; assert len(ps)==2 and {x['process_id'] for x in ps}=={'PROC_UG_CREDENTIAL_DEGREE_V001','PROC_UG_CREDENTIAL_DIPLOMA_V001'}
sha=hashlib.sha256((r/'data/research/evidence_units.jsonl').read_bytes()).hexdigest()
for p in ps: assert p['evidence_snapshot']['dataset_sha256']==sha and set(p['evidence_snapshot']['evidence_ids'])=={e['evidence_id'] for e in ev if e['evidence_id'] in p['evidence_snapshot']['evidence_ids']}
rev=list(csv.DictReader((r/'data/audit/stage2b-credentials-second-review.csv').open(encoding='utf8'))); assert len(rev)==21 and {x['evidence_id'] for x in rev}=={e['evidence_id'] for e in ev}
print('[OK] S2SRC002 credentials contract passed: 2 sources, 21 evidence units, 2 process records, 21 independent reviews')
