import csv,json,hashlib
from pathlib import Path
R=Path('.')
ev=[json.loads(x) for x in (R/'data/research/evidence_units.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_STUDENT_CARD_REISSUE']
assert len(ev)==7 and {x['evidence_id'] for x in ev}=={f'UGT{i:03d}' for i in range(1,8)}
assert all(x['review']['status']=='verified' for x in ev)
ps=[json.loads(x) for x in (R/'data/research/process_records.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_STUDENT_CARD_REISSUE']; assert len(ps)==1
assert ps[0]['evidence_snapshot']['dataset_sha256']==hashlib.sha256((R/'data/research/evidence_units.jsonl').read_bytes()).hexdigest()
assert set(ps[0]['evidence_snapshot']['evidence_ids'])=={x['evidence_id'] for x in ev}
rev=list(csv.DictReader((R/'data/audit/stage2b-student-card-second-review.csv').open(encoding='utf8'))); assert len(rev)==7 and {x['evidence_id'] for x in rev}=={x['evidence_id'] for x in ev}
print('[OK] S2SRC003 student-card contract passed: 1 source, 7 evidence units, 1 process record, 7 independent reviews')
