import json,hashlib
from pathlib import Path
p=Path('data/research/evidence_units.jsonl'); rows=[json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
for x in rows:
 if x.get('evidence_id')=='UGL009': x['source_locator']['anchor_text']='请假时间：自_______年_______月_______日 至_______年_______月_______日，共_______天'; x['verbatim_text']=x['source_locator']['anchor_text']
 if x.get('evidence_id')=='UGL011': x['source_locator']['anchor_text']='申请会被驳回并会按《暨南大学学生违纪处分办法》的相关规定处理'; x['verbatim_text']=x['source_locator']['anchor_text']
p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
sp=Path('data/research/source_records.jsonl'); ss=[json.loads(x) for x in sp.read_text(encoding='utf8').splitlines() if x.strip()]
for x in ss:
 if x.get('source_id')=='SRC_UG_LEAVE_PAGE_202504': x['relations']=[{'relation_type':'landing_page_for','target_source_id':'SRC_UG_LEAVE_FORM_PDF_202504'}]
sp.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in ss)+'\n',encoding='utf8')
sha=hashlib.sha256(p.read_bytes()).hexdigest();q=Path('data/research/process_records.jsonl');ps=[json.loads(x) for x in q.read_text(encoding='utf8').splitlines() if x.strip()]
for x in ps:x['evidence_snapshot']['dataset_sha256']=sha
q.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in ps)+'\n',encoding='utf8')
