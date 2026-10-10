import json,csv,hashlib
from pathlib import Path
R=Path.cwd()
def read(p):return [json.loads(l) for l in p.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
def write(p,rows):p.write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in rows),encoding='utf8',newline='\n')
s=R/'data/research/source_records.jsonl';ss=read(s)
for x in ss:
 if x['source_id']=='SRC_UG_MAJOR_CHANGE_INTERNAL_20250716':x['publication'].update(date=None,date_kind='unknown')
 if x['source_id']=='SRC_UG_MAJOR_CHANGE_EXTERNAL_20250716':x['relations']=[{'relation_type':'landing_page_for','target_source_id':'SRC_UG_MAJOR_CHANGE_EXTERNAL_PDF_20250716'}]
 if x['source_id'].startswith(('SRC_UG_CREDENTIAL','SRC_UG_STUDENT_CARD','SRC_UG_COURSE_SELECTION','SRC_UG_LEAVE','SRC_UG_MAJOR_CHANGE')):
  x['review'].update(status='in_review',reviewer=None,reviewed_at=None,notes='保存文件可用于核验；来源元数据与声明适用性正在独立复核。原记录时间为生成脚本常量，无法据此确认真实抓取时刻。')
write(s,ss)
e=R/'data/research/evidence_units.jsonl';es=read(e)
for x in es:
 if x['evidence_id']=='UGM007':x['verbatim_text']=x['source_locator']['anchor_text']='申请一旦受理，，不得撤销'
 if x['item_id'] in {'UG_CREDENTIAL_REISSUE','UG_STUDENT_CARD_REISSUE','UG_COURSE_SELECTION','UG_LEAVE_REQUEST','UG_MAJOR_CHANGE'}:x['review'].update(status='in_review',reviewed_at=None,reviewer=None,notes='正在逐项审查原文蕴含、原子性、对象和条件；尚未完成独立复核。')
write(e,es)
p=R/'data/research/process_records.jsonl';ps=read(p)
for x in ps:
 x['evidence_snapshot']['dataset_sha256']=hashlib.sha256(e.read_bytes()).hexdigest()
 if x['item_id']!='UG_WITHDRAWAL':x['review'].update(status='in_review',reviewed_at=None,reviewer=None,notes='进行中；条件分支、证据绑定和流程节点须逐项独立复核。')
write(p,ps)
for name in ['credentials','student-card','course-selection','leave','major-change']:
 p=R/f'data/audit/stage2b-{name}-second-review.csv'
 with p.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
 for x in rows:
  for k in ['locator_recheck','verbatim_recheck','claim_recheck','applicability_recheck']:x[k]='待复核'
  x.update(result='进行中',reviewed_at='',reviewer='',notes='等待实际独立复核；自动生成的覆盖行仅作为复核任务清单。')
 with p.open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
p=R/'data/research/stage2-source-migration-plan.csv'
with p.open(encoding='utf-8-sig',newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
for x in rows:
 if x['plan_id'] in ['S2SRC002','S2SRC003','S2SRC004','S2SRC005','S2SRC006']:x['status']='进行中'
with p.open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
