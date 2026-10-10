import csv,json,hashlib
from pathlib import Path
R=Path('.')
ev=[json.loads(x) for x in (R/'data/research/evidence_units.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_LEAVE_REQUEST']; assert len(ev)==12 and {x['evidence_id'] for x in ev}=={f'UGL{i:03d}' for i in range(1,13)}
ps=[json.loads(x) for x in (R/'data/research/process_records.jsonl').read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x).get('item_id')=='UG_LEAVE_REQUEST']; assert len(ps)==1 and ps[0]['evidence_snapshot']['dataset_sha256']==hashlib.sha256((R/'data/research/evidence_units.jsonl').read_bytes()).hexdigest()
assert set(ps[0]['evidence_snapshot']['evidence_ids'])=={x['evidence_id'] for x in ev}; rev=list(csv.DictReader((R/'data/audit/stage2b-leave-second-review.csv').open(encoding='utf8'))); assert len(rev)==12 and {x['evidence_id'] for x in rev}=={x['evidence_id'] for x in ev}; print('[OK] S2SRC005 leave contract passed: 2 sources, 12 evidence units, 1 process record, 12 independent reviews')
