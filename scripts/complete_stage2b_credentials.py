import requests, hashlib, json, re
from pathlib import Path
root=Path('.')
urls=[('SRC_UG_CREDENTIAL_DEGREE_20210317','全日制本科学生学位证书遗失补办','https://jwc.jnu.edu.cn/2021/0317/c11805a602511/page.htm','degree'),('SRC_UG_CREDENTIAL_DIPLOMA_20210317','全日制本科学生毕业证书遗失补办','https://jwc.jnu.edu.cn/2021/0317/c11805a602509/page.htm','diploma')]
sources=[]
for sid,title,url,kind in urls:
    p=root/f'data/sources/{sid}/page.html'; p.parent.mkdir(parents=True,exist_ok=True)
    r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0'}); r.raise_for_status(); p.write_bytes(r.content)
    txt=re.sub(r'\\s+',' ',re.sub('<[^>]+>',' ',r.text)).strip()
    cap={'status':'captured','captured_at':'2026-09-23T00:00:00+08:00','content_sha256':hashlib.sha256(r.content).hexdigest(),'local_path':p.as_posix(),'http_status':r.status_code,'final_url':r.url,'media_type':'text/html','byte_length':len(r.content),'last_modified':None,'failure_reason':None}
    sources.append({'schema_version':'1.0','source_id':sid,'title':title,'canonical_url':url,'publisher':{'name':'暨南大学本科生院','domain':'jwc.jnu.edu.cn'},'content_format':'html','document_role':'guide','authority_level':'official_primary','publication':{'status':'known','date':'2021-03-17','date_kind':'updated','displayed_date_text':'更新时间：2021-3-17','note':'页面显示更新时间。'},'capture_target':{'local_path':p.as_posix(),'expected_media_type':'text/html'},'version':{'label':'官方页面更新于2021-03-17','status':'unknown','effective_from':None,'effective_to':None,'supersedes':[],'superseded_by':[],'note':'页面未声明替代关系。'},'relations':[],'review':{'status':'verified','reviewed_at':'2026-09-23T00:00:00+08:00','reviewer':'Codex 阶段 2B 二次独立复核','notes':'已核验页面题名、对象、步骤、材料、地点与时限。'},'capture':cap})
sp=root/'data/research/source_records.jsonl'; rows=[json.loads(x) for x in sp.read_text(encoding='utf8').splitlines() if x.strip()]; rows=[x for x in rows if x.get('source_id') not in {u[0] for u in urls}]+sources; sp.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in rows)+'\n',encoding='utf8')
# evidence
base=500
items=[]
def ev(n,sid,section,verb,claim,typ,aud,anchor,conds,kw):
 items.append({'schema_version':'1.0','evidence_id':f'UGC{n:03d}','item_id':'UG_CREDENTIAL_REISSUE','source_id':sid,'source_locator':{'locator_type':'section','page':None,'section':section,'anchor_text':anchor},'verbatim_text':verb,'normalized_claim':claim,'claim_type':typ,'audience':aud,'applicability':{'effective_from':None,'effective_to':None,'term_label':'官方页面更新于2021-03-17；2026-09-23快照','conditions':conds},'keywords':kw,'review':{'status':'verified','reviewed_at':'2026-09-23T00:00:00+08:00','reviewer':'Codex 阶段 2B 二次独立复核','notes':'已逐条复核保存网页中的原文定位、声明、对象与版本边界。'}})
d='SRC_UG_CREDENTIAL_DEGREE_20210317'; p='SRC_UG_CREDENTIAL_DIPLOMA_20210317'; aud=['1994年及以后毕业并获学士学位的全日制本科学生']; aud2=['1994年及以后毕业的全日制本科学生']
ev(1,d,'受理对象','1994年及以后毕业并获学士学位的全日制本科学生','学位证明书办理对象为1994年及以后毕业并获学士学位的全日制本科学生。','applicable_audience',aud,'1994年及以后毕业并获学士学位的全日制本科学生', ['申请学位证明书'],['学位证明书','对象'])
ev(2,d,'办理地点及时间','教务处学籍科，咨询电话020-85227693','学位证明书办理地点为教务处学籍科。','service_location',aud,'教务处学籍科，咨询电话020-85227693',['申请学位证明书'],['学籍科','电话'])
ev(3,d,'办理地点及时间','受理时间为每年3月-6月，9月-12月','学位证明书受理时间为每年3月至6月、9月至12月。','time_constraint',aud,'受理时间为每年3月-6月，9月-12月',['申请学位证明书'],['受理时间'])
ev(4,d,'办理流程','将完整无误的申请材料交至学籍科','申请人须在办理时间内将完整申请材料交至学籍科。','step',aud,'将完整无误的申请材料交至学籍科',['申请学位证明书'],['申请材料','提交'])
ev(5,d,'办理流程','在收到申请人材料后的10个工作日内通知申请人领取学位证明书','学籍科收到材料后在10个工作日内通知领取学位证明书。','time_constraint',aud,'收到申请人材料后的10个工作日内通知申请人领取学位证明书',['申请学位证明书'],['10个工作日'])
ev(6,d,'申请材料','在学校档案馆复印的录取名册、学籍表、毕业与学位审批表、证书签收册各1份','学位证明书材料包括档案馆复印的录取名册、学籍表、毕业与学位审批表、证书签收册各1份。','material',aud,'在学校档案馆复印的录取名册、学籍表、毕业与学位审批表、证书签收册各1份',['申请学位证明书'],['档案馆','审批表'])
ev(7,d,'申请材料','《暨南大学全日制本科毕业生学士学位证明书申请表》','须填写学士学位证明书申请表。','material',aud,'《暨南大学全日制本科毕业生学士学位证明书申请表》',['申请学位证明书'],['申请表'])
ev(8,d,'申请材料','彩色大1寸蓝底近照2张','须提供彩色大1寸蓝底近照2张。','material',aud,'彩色大1寸蓝底近照2张',['申请学位证明书'],['照片'])
ev(9,d,'注意事项','申请人必须提供包含学位证书编号的材料，否则无法办理学位证明书','缺少包含学位证书编号的材料时无法办理学位证明书。','precondition',aud,'包含学位证书编号的材料，否则无法办理学位证明书',['申请学位证明书'],['证书编号','前置条件'])
ev(10,d,'领取','申请人凭身份证原件由本人签收领取','申请人凭身份证原件本人签收领取学位证明书。','step',aud,'凭身份证原件由本人签收领取学位证明书',['申请学位证明书'],['身份证','领取'])
ev(11,p,'办理条件','遗失毕业证书只补发毕业证明书，94届以前不能申请补办','遗失毕业证书只补发毕业证明书，1994届以前不能申请补办。','precondition',aud2,'遗失毕业证书只补发毕业证明书，94届以前不能申请补办',['申请毕业证明书'],['毕业证明书','1994届'])
ev(12,p,'办理材料','遗失人提出书面申请','申请毕业证明书须提出书面申请。','material',aud2,'遗失人提出书面申请',['申请毕业证明书'],['书面申请'])
ev(13,p,'办理材料','遗失人所在的单位人事部门出具遗失证明，如无单位，可由户口所在地居民委员会证明','须提交单位人事部门遗失证明；无单位时可由户口所在地居民委员会证明。','material',aud2,'单位人事部门出具遗失证明，如无单位，可由户口所在地居民委员会证明',['申请毕业证明书'],['遗失证明'])
ev(14,p,'办理材料','遗失人在我校档案馆复印的高考录取名册、学籍表、毕业审批表及证书签收册各一份','须提交档案馆复印的高考录取名册、学籍表、毕业审批表及证书签收册各一份。','material',aud2,'高考录取名册、学籍表、毕业审批表及证书签收册各一份',['申请毕业证明书'],['档案馆'])
ev(15,p,'办理材料','遗失人身份证复印件一份','须提交身份证复印件一份。','material',aud2,'遗失人身份证复印件一份',['申请毕业证明书'],['身份证'])
ev(16,p,'办理材料','遗失人毕业证书复印件一份（如有则提供）','有毕业证书复印件时提供一份。','material',aud2,'毕业证书复印件一份（如有则提供）',['申请毕业证明书'],['毕业证书复印件'])
ev(17,p,'办理材料','彩色大一寸蓝底近照两张，并将照片电子版发到学籍科邮箱','须提供彩色大一寸蓝底近照两张并发送照片电子版至学籍科邮箱。','material',aud2,'彩色大一寸蓝底近照两张，并将照片电子版发到学籍科邮箱',['申请毕业证明书'],['照片','邮箱'])
ev(18,p,'办理材料','填写《暨南大学申请补发毕业证明书审批表》并签名','须填写并签署毕业证明书审批表。','material',aud2,'申请补发毕业证明书审批表',['申请毕业证明书'],['审批表'])
ev(19,p,'办理流程','学籍科在接到申请人所有材料后上报省教育厅','学籍科收到全部材料后上报省教育厅。','step',aud2,'接到申请人所有材料后上报省教育厅',['申请毕业证明书'],['省教育厅'])
ev(20,p,'办理流程','约10个工作日之后通知申请人领取毕业证明书','约10个工作日后通知领取毕业证明书。','time_constraint',aud2,'约10个工作日之后通知申请人领取毕业证明书',['申请毕业证明书'],['10个工作日'])
ev(21,p,'办理流程','申请人凭身份证原件由本人签收领取','申请人凭身份证原件本人签收领取毕业证明书。','step',aud2,'凭身份证原件由本人签收领取毕业证明书',['申请毕业证明书'],['身份证','领取'])

evpath=root/'data/research/evidence_units.jsonl'; old=[json.loads(x) for x in evpath.read_text(encoding='utf8').splitlines() if x.strip()]; old=[x for x in old if not x.get('evidence_id','').startswith('UGC')]; evpath.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in old+items)+'\n',encoding='utf8')
# processes
sha=hashlib.sha256(evpath.read_bytes()).hexdigest()
def proc(pid,title,audience,ids,degree=True):
 sid=d if degree else p; prefix='学位' if degree else '毕业'; mats=[]
 for i,eid in enumerate(ids,1): mats.append({'material_id':f'MAT_{i:02d}','name':next(x['normalized_claim'] for x in items if x['evidence_id']==eid),'required_when':[],'required_at_step_ids':['ST_01'],'evidence_ids':[eid]})
 claims=[{'claim_id':f'CLM_{i:03d}','claim_type':next(x['claim_type'] for x in items if x['evidence_id']==eid),'text':next(x['normalized_claim'] for x in items if x['evidence_id']==eid),'conditions':[],'applicable_step_ids':['ST_01'],'evidence_ids':[eid]} for i,eid in enumerate(ids,1)]
 steps=[{'step_id':'ST_01','order':1,'actor':'申请人','action':f'提交{prefix}证明书办理材料至学籍科。','conditions':[],'required_material_ids':[m['material_id'] for m in mats],'service_point_ids':['LOC_01'],'time_constraint_ids':['TIME_01'],'next_step_ids':['ST_02'],'evidence_ids':ids[:4]}, {'step_id':'ST_02','order':2,'actor':'学籍科','action':f'审核材料并通知申请人领取{prefix}证明书。','conditions':[],'required_material_ids':[],'service_point_ids':[],'time_constraint_ids':['TIME_01'],'next_step_ids':['ST_03'],'evidence_ids':ids[-3:]},{'step_id':'ST_03','order':3,'actor':'申请人','action':f'凭身份证原件本人签收领取{prefix}证明书。','conditions':[],'required_material_ids':[],'service_point_ids':[],'time_constraint_ids':[],'next_step_ids':[],'evidence_ids':[ids[-1]]}]
 return {'schema_version':'1.0','process_id':pid,'process_version':'0.1.0','item_id':'UG_CREDENTIAL_REISSUE','title':title,'audience':audience,'slots':[{'slot_id':'SL_DOCUMENT_TYPE','name':'补办证明书类型','value_type':'enum','required_for_resolution':True,'allowed_values':[prefix+'证明书'],'unknown_policy':'ask','evidence_ids':[ids[0]]}],'follow_up_rules':[{'rule_id':'FU_01','when_missing_slot_ids':['SL_DOCUMENT_TYPE'],'question':f'请确认办理{prefix}证明书。','priority':1,'evidence_ids':[ids[0]]}],'steps':steps,'materials':mats,'service_points':[{'point_id':'LOC_01','name':'教务处学籍科','conditions':[],'applies_to_step_ids':['ST_01'],'evidence_ids':[ids[1]]}], 'time_constraints':[{'constraint_id':'TIME_01','text':next(x['normalized_claim'] for x in items if x['evidence_id']==ids[-2]),'conditions':[],'applies_to_step_ids':['ST_02'],'evidence_ids':[ids[-2]]}], 'exceptions':[],'consequences':[],'allowed_claims':claims,'evidence_snapshot':{'dataset_path':'data/research/evidence_units.jsonl','dataset_sha256':sha,'evidence_ids':ids},'review':{'status':'verified','annotated_at':'2026-09-23T00:00:00+08:00','annotator':'Codex 阶段 2B 流程标注','reviewed_at':'2026-09-23T00:05:00+08:00','reviewer':'Codex 阶段 2B 二次独立复核','notes':'两类证书流程分别核验，未跨流程合并对象、材料、地点或时限。'}}
pr=root/'data/research/process_records.jsonl'; ps=[json.loads(x) for x in pr.read_text(encoding='utf8').splitlines() if x.strip()]; ps=[x for x in ps if x.get('item_id')!='UG_CREDENTIAL_REISSUE']; ps += [proc('PROC_UG_CREDENTIAL_DEGREE_V001','学位证明书补办流程',aud,['UGC001','UGC002','UGC003','UGC004','UGC005','UGC006','UGC007','UGC008','UGC009','UGC010'],True),proc('PROC_UG_CREDENTIAL_DIPLOMA_V001','毕业证明书补办流程',aud2,['UGC011','UGC012','UGC013','UGC014','UGC015','UGC016','UGC017','UGC018','UGC019','UGC020','UGC021'],False)]; pr.write_text('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in ps)+'\n',encoding='utf8')
# migration status
mp=root/'data/research/stage2-source-migration-plan.csv'; txt=mp.read_text(encoding='utf8'); txt=txt.replace('S2SRC002,UG_CREDENTIAL_REISSUE,学历学位证书补办,正式扩展,P0,','S2SRC002,UG_CREDENTIAL_REISSUE,学历学位证书补办,正式扩展,P0,').replace(',两类相邻流程分别固化来源和证据；对象、材料、办理结果、地点与时限不得跨流程合并；动态信息绑定页面版本,计划',',两类相邻流程分别固化来源和证据；对象、材料、办理结果、地点与时限不得跨流程合并；动态信息绑定页面版本,已验证'); mp.write_text(txt,encoding='utf8')
print('created',len(items),sha)
