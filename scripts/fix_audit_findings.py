import json, re
from pathlib import Path
p=Path('data/research/evidence_units.jsonl'); rows=[json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
updates={
'UGT001':'在校全日制本科学生遗失学生证，须向所在院系书面写明原因、提交补发申请。',
'UGL005':'一天以内请班主任审批，并告知辅导员，请手写签名并签署意见。',
'UGL010':'本人签名确认已阅读申请须知，并承诺遵守所有规定，同时确认表中所填内容及附件真实、准确。',
'UGM003':'转专业学生需提供成绩单原件，未按要求提供材料及材料不合格者，不予受理。',
'UGM009':'外招生跨校区转专业必须附：①成绩绩点排名证明和②证明材料。',
'UGQ004':'第一阶段选课（期末17-18周），学生必须上网选好必修课程和专业课程。',
}
for x in rows:
 if x.get('evidence_id') in updates:
  x['verbatim_text']=updates[x['evidence_id']]; x['source_locator']['anchor_text']=updates[x['evidence_id']]
 if x.get('evidence_id')=='UGC011': x['normalized_claim']='遗失毕业证书只补发毕业证明书，94届以前不能申请补办。'
 # all new process evidence remains explicitly in review pending actual independent review
p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
# process corrections
q=Path('data/research/process_records.jsonl'); ps=[json.loads(x) for x in q.read_text(encoding='utf8').splitlines() if x.strip()]
for x in ps:
 if x.get('process_id')=='PROC_UG_LEAVE_REQUEST_V001':
  vals=['一天以内','一天以上一周以内','一周以上两周以内','两周以上']
  for i,t in enumerate(x['time_constraints']):
   t['conditions']=[{'slot_id':'SL_LEAVE_DAYS','operator':'equals','value':vals[i]}]
  x['steps'][1]['evidence_ids']=['UGL004','UGL005','UGL006','UGL007','UGL008']
  x['consequences'][0]['trigger']=[{'slot_id':'SL_LEAVE_DAYS','operator':'equals','value':'累计超过学期总学时三分之一'}]
  x['consequences'][1]['trigger']=[{'slot_id':'SL_LEAVE_DAYS','operator':'known','value':'存在虚假信息或隐瞒事实'}]
 if x.get('process_id')=='PROC_UG_CREDENTIAL_DEGREE_V001':
  x['steps'][0]['evidence_ids']=['UGC001','UGC002','UGC003','UGC004','UGC006','UGC007','UGC008','UGC009']
  x['steps'][1]['evidence_ids']=['UGC005']
  x['steps'][2]['evidence_ids']=['UGC010']
 if x.get('process_id')=='PROC_UG_CREDENTIAL_DIPLOMA_V001':
  x['steps'][0]['evidence_ids']=['UGC011','UGC012','UGC013','UGC014','UGC015','UGC016','UGC017','UGC018']
  x['steps'][1]['evidence_ids']=['UGC019','UGC020']
  x['steps'][2]['evidence_ids']=['UGC021']
 if x.get('process_id')=='PROC_UG_STUDENT_CARD_V001':
  x['steps'][3]['actor']='学生与办理部门'; x['steps'][3]['action']='学生持新证到石牌校区行政办公楼827扫码缴纳3元工本费，办理部门随后盖章。'
 if x.get('process_id')=='PROC_UG_MAJOR_CHANGE_EXTERNAL_V001':
  x['slots'].append({'slot_id':'SL_CROSS_CAMPUS','name':'是否跨校区转专业','value_type':'boolean','required_for_resolution':False,'allowed_values':[],'unknown_policy':'allow_unknown','evidence_ids':['UGM009']})
  x['exceptions'][0]['trigger']=[{'slot_id':'SL_APPLICANT_TYPE','operator':'equals','value':'外招生'},{'slot_id':'SL_CROSS_CAMPUS','operator':'equals','value':'true'}]
  x['steps'][2]['action']='转入学院教科办在教务管理系统中审核申请，然后转至教务处学籍科。'
q.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in ps)+'\n',encoding='utf8')
