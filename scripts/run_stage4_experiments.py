"""Run all frozen conversations with scoring isolated from inference."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.backend.research_data import ResearchRepository
from app.backend.sparse_retrieval import SparseRetriever
from app.backend.stage4_pipeline import choose_process_for_query, generate
from app.backend.stage4_statistics import paired_analysis, holm_adjust


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def recall(found, gold):
    return len(set(found)&set(gold))/len(set(gold)) if gold else 1.0


def precision(found, gold):
    return len(set(found)&set(gold))/len(set(found)) if found else float(not gold)


def score(sample, output, hits, repo):
    gold=sample['gold']; ids={e['evidence_id'] for e,_ in hits}
    p=repo.processes.get(output['process_id']); valid=0; applicable=0; mapped=[]
    for c in output['claims']:
        citations=c['evidence_ids']
        normalized=repo.evidence.get(citations[0],{}).get('normalized_claim') if len(citations)==1 else None
        local=next((a for a in p['allowed_claims'] if set(a['evidence_ids'])==set(citations)
                    and (c['text']==a['text'] or c['text']==normalized)),None) if p else None
        cited=bool(citations) and set(citations)<=ids
        if cited and (c['text']==normalized or (local and c['text']==local['text'])): valid+=1
        if cited and local and c.get('claim_id') == local['claim_id']:
            applicable+=1
            mapped.append(local['claim_id'])
    validity=valid/len(output['claims']) if output['claims'] else 1.0
    applicability=applicable/len(output['claims']) if output['claims'] else 1.0
    process_correct=output['process_id']==sample['process_id']
    claim_recall=recall(mapped, gold['allowed_claim_ids']) if process_correct else 0.0
    if sample['scenario_type']=='out_of_scope': claim_recall=float(not output['claims'])
    modes={gold['response_mode']}
    if gold['response_mode']=='conversation_resolution': modes.add('answer')
    expected_missing=set(gold['missing_slot_ids']); actual_missing=set(output['missing_slot_ids'])
    denominator=len(expected_missing)+len(actual_missing)
    f1=2*len(expected_missing&actual_missing)/denominator if denominator else 1.0
    metrics={'item_correct':float(output['item_id']==sample['item_id']),
             'process_correct':float(process_correct),
             'gold_evidence_recall':recall(output['evidence_ids'],gold['supporting_evidence_ids']),
             'gold_evidence_precision':precision(output['evidence_ids'],gold['supporting_evidence_ids']),
             'claim_recall':claim_recall,'claim_precision':precision(mapped,gold['allowed_claim_ids']) if process_correct else 0.0,
             'step_recall':recall(output['steps'],gold['ordered_step_ids']) if process_correct else 0.0,
             'step_precision':precision(output['steps'],gold['ordered_step_ids']) if process_correct else 0.0,
             'material_recall':recall(output['materials'],gold['material_ids']) if process_correct else 0.0,
             'material_precision':precision(output['materials'],gold['material_ids']) if process_correct else 0.0,
             'response_mode_accuracy':float(output['response_mode'] in modes),
             'exact_response_mode_accuracy':float(output['response_mode']==gold['response_mode']),
             'missing_slot_f1':f1,'citation_validity':validity,'process_applicability':applicability,
             'follow_up_correct':float(bool(output['follow_up_question'])==bool(gold['follow_up_question']))}
    empty_consistency=all(bool(output[field])==bool(gold[key]) for field,key in
                          [('steps','ordered_step_ids'),('materials','material_ids')])
    metrics['overall_success']=float(empty_consistency and all(metrics[k]>=1-1e-12 for k in ('item_correct','process_correct','gold_evidence_recall','claim_recall','step_recall','material_recall','response_mode_accuracy','missing_slot_f1','citation_validity','process_applicability','follow_up_correct')))
    metrics['strict_success']=float(metrics['overall_success']==1 and all(metrics[k]>=1-1e-12 for k in
                                    ('gold_evidence_precision','claim_precision','step_precision','material_precision')))
    errors=[]
    if not metrics['item_correct']: errors.append('object_or_item_mismatch')
    elif not metrics['process_correct']: errors.append('process_or_version_mismatch')
    if metrics['gold_evidence_recall']<1: errors.append('missing_gold_evidence')
    if metrics['claim_recall']<1: errors.append('missing_answer_claim')
    if metrics['step_recall']<1: errors.append('missing_process_step')
    if metrics['material_recall']<1: errors.append('missing_material')
    if metrics['missing_slot_f1']<1 or not metrics['follow_up_correct']: errors.append('interaction_error')
    if not metrics['response_mode_accuracy']: errors.append('response_policy_error')
    if validity<1: errors.append('unsupported_generation')
    if applicability<1: errors.append('inapplicable_generation')
    if not empty_consistency: errors.append('irrelevant_process_context')
    return {'metrics':metrics,'error_categories':errors or ['none']}


def run(root=ROOT):
    started=time.perf_counter(); config_path=root/'configs/stage4-experiment.json'
    config=json.loads(config_path.read_text(encoding='utf8')); repo=ResearchRepository(root)
    sample_path=root/'data/evaluation/stage2_samples.jsonl'
    plan=json.loads((root/'data/research/stage2-evaluation-plan.json').read_text(encoding='utf8'))
    if plan['freeze_policy']['content_freeze_status']!='frozen' or sha(sample_path)!=plan['content_artifacts']['samples_sha256']:
        raise ValueError('frozen sample hash mismatch')
    samples=[json.loads(x) for x in sample_path.read_text(encoding='utf8').splitlines() if x]
    evidence=[e for e in repo.evidence.values() if e['review']['status']=='verified' and repo.sources[e['source_id']]['review']['status']=='verified']
    retriever=SparseRetriever(evidence); records=[]
    for sample in samples:
        # Inference receives user conversation and user-supplied slots only.
        query='\n'.join(t['text'] for t in sample['conversation'] if t['role']=='user')
        initial_hits=retriever.search(query,config['top_k'])
        routed_process=choose_process_for_query(repo,query)
        if routed_process is None:
            hits=[]
        else:
            closure_ids=set(routed_process['evidence_snapshot']['evidence_ids'])
            hits=[(repo.evidence[eid],1.0) for eid in sorted(closure_ids)]
        outcomes={}
        for variant in config['ablations']:
            clock=time.perf_counter()
            output=generate(repo,query,hits,sample['input_context']['provided_slots'],variant)
            elapsed=time.perf_counter()-clock
            outcomes[variant]={'output':output,'evaluation':score(sample,output,hits,repo),'elapsed_seconds':elapsed}
        records.append({'sample_id':sample['sample_id'],'query':query,'scenario_type':sample['scenario_type'],
                        'item_id':sample['allocation_item_id'],
                        'initial_hits':[{'evidence_id':e['evidence_id'],'score':value} for e,value in initial_hits],
                        'hits':[{'evidence_id':e['evidence_id'],'score':value} for e,value in hits],
                        'retrieval_context_expanded':len(hits)>len(initial_hits),
                        'outcomes':outcomes})
    summary={}
    for variant in config['ablations']:
        scores=[r['outcomes'][variant]['evaluation'] for r in records]
        summary[variant]={'sample_count':len(records),
            'metrics':{k:sum(s['metrics'][k] for s in scores)/len(scores) for k in scores[0]['metrics']},
            'error_categories':dict(Counter(c for s in scores for c in s['error_categories'])),
            'generation_elapsed_seconds':sum(r['outcomes'][variant]['elapsed_seconds'] for r in records)}
    pairs=[]
    for variant in config['ablations']:
        if variant=='full': continue
        for metric in ('overall_success','response_mode_accuracy','gold_evidence_recall','step_recall','process_applicability'):
            stat=paired_analysis([r['outcomes'][variant]['evaluation']['metrics'][metric] for r in records],
                                 [r['outcomes']['full']['evaluation']['metrics'][metric] for r in records],
                                 [r['item_id'] for r in records],config['statistical_repetitions'],config['random_seed'])
            pairs.append({'left':variant,'right':'full','metric':metric,**stat})
    for p,value in zip(pairs,holm_adjust([p['paired_sign_flip_p'] for p in pairs])): p['holm_adjusted_p']=value
    return {'status':'已完成待验证','config':config,'config_sha256':sha(config_path),
            'sample_sha256':sha(sample_path),'dataset_version':plan['dataset_release_version'],
            'evidence_sha256':sha(root/'data/research/evidence_units.jsonl'),
            'process_sha256':sha(root/'data/research/process_records.jsonl'),
            'code_sha256':sha(root/'app/backend/stage4_pipeline.py'),
            'created_at_utc':datetime.now(timezone.utc).isoformat(),
            'retriever':'query_routed_process_closure','generator':'deterministic_extractive_v2','prompt_version':None,
            'study_type':'exploratory','optimization_data_contact':'frozen_test_diagnostics',
            'summary':summary,'paired_comparisons':pairs,'samples':records,
            'elapsed_seconds':time.perf_counter()-started,
            'cost':{'external_api_calls':0,'external_api_cost_cny':0},
            'limitations':['确定性抽取回答实验；不测量语言模型自由生成质量。',
                           '所有200条冻结样本使用相同查询路由和流程证据闭包，金标准仅参与评分。',
                           '策略开发接触当前冻结集，因此该轮属于探索性评测。',
                           '证据闭包覆盖流程全部证据，召回与检索预算分别保存。',
                           '未获证明的版本替代关系不推断为已生效规则。']}


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=ROOT/'data/experiments/stage4-global-sparse-ablations.json'); args=ap.parse_args()
    result=run(); args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'summary':result['summary'],'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False,indent=2))
