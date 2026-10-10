import csv,json,hashlib
from pathlib import Path
R=Path('.')
ev=[json.loads(x) for x in (R/'data/research/evidence_units.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_COURSE_SELECTION']; assert len(ev)==9 and {x['evidence_id'] for x in ev}=={f'UGQ{i:03d}' for i in range(1,10)}; assert all(x['review']['status']=='verified' for x in ev)
ps=[json.loads(x) for x in (R/'data/research/process_records.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_COURSE_SELECTION']; assert len(ps)==1 and ps[0]['evidence_snapshot']['dataset_sha256']==hashlib.sha256((R/'data/research/evidence_units.jsonl').read_bytes()).hexdigest() and set(ps[0]['evidence_snapshot']['evidence_ids'])=={x['evidence_id'] for x in ev}
rev=list(csv.DictReader((R/'data/audit/stage2b-course-selection-second-review.csv').open(encoding='utf8'))); assert len(rev)==9 and {x['evidence_id'] for x in rev}=={x['evidence_id'] for x in ev}; print('[OK] S2SRC004 course-selection contract passed: 1 source, 9 evidence units, 1 process record, 9 independent reviews')
