"""Recompute and analyze the saved Stage 3 item-conditioned retrieval outputs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.backend.stage4_statistics import paired_analysis, retrieval_observation, holm_adjust


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(root=ROOT, repetitions=10000, seed=0):
    sample_path=root/'data/evaluation/stage2_samples.jsonl'
    plan=json.loads((root/'data/research/stage2-evaluation-plan.json').read_text(encoding='utf8'))
    if plan['freeze_policy']['content_freeze_status']!='frozen' or sha(sample_path)!=plan['content_artifacts']['samples_sha256']:
        raise ValueError('frozen sample hash does not match release manifest')
    samples={x['sample_id']:x for x in map(json.loads,sample_path.read_text(encoding='utf8').splitlines()) if x}
    result_path=root/'data/audit/stage3-formal-semantic-hybrid.json'
    results=json.loads(result_path.read_text(encoding='utf8'))
    if results['dataset_version']!=plan['dataset_release_version']: raise ValueError('release mismatch')
    ids=[r['sample_id'] for r in results['samples']]
    expected={k for k,s in samples.items() if s['scenario_type']!='out_of_scope'}
    if len(set(ids))!=len(ids) or set(ids)!=expected: raise ValueError('incomplete paired sample coverage')
    strategies=['sparse','semantic','hybrid']; per_sample=[]
    for r in results['samples']:
        s=samples[r['sample_id']]; relevant=set(s['gold']['supporting_evidence_ids'])
        if relevant!=set(r['relevant_evidence_ids']): raise ValueError('gold binding mismatch')
        entry={k:s[k] for k in ('sample_id','item_id','scenario_type','difficulty','version_risk','turn_structure')}; entry['strategies']={}
        for strategy in strategies:
            raw=r['strategies'][strategy]; score=retrieval_observation(raw['hits'],relevant)
            for metric in ('recall_at_k','precision_at_k'):
                if abs(score[metric]-raw[metric])>1e-10: raise ValueError('saved metrics cannot be reproduced')
            score['hits']=raw['hits']; score['structural_validation_errors']=raw['validation_errors']
            entry['strategies'][strategy]=score
        per_sample.append(entry)
    groups={}
    for dimension in ('all','item_id','scenario_type','difficulty','version_risk','turn_structure'):
        buckets=defaultdict(list)
        for s in per_sample: buckets['all' if dimension=='all' else s[dimension]].append(s)
        groups[dimension]={}
        for key,rows in sorted(buckets.items()):
            groups[dimension][key]={}
            for strategy in strategies:
                scores=[r['strategies'][strategy] for r in rows]
                groups[dimension][key][strategy]={'sample_count':len(rows),
                    'mean_recall_at_k':sum(v['recall_at_k'] for v in scores)/len(rows),
                    'mean_precision_at_k':sum(v['precision_at_k'] for v in scores)/len(rows),
                    'complete_evidence_rate':sum(v['complete_evidence'] for v in scores)/len(rows),
                    'retrieval_errors':dict(Counter(v['retrieval_error'] for v in scores))}
    pairs=[]; item_ids=[s['item_id'] for s in per_sample]
    for left,right in [('sparse','semantic'),('sparse','hybrid'),('semantic','hybrid')]:
        for metric in ('recall_at_k','precision_at_k'):
            stat=paired_analysis([s['strategies'][left][metric] for s in per_sample],
                                 [s['strategies'][right][metric] for s in per_sample],item_ids,repetitions,seed)
            pairs.append({'left':left,'right':right,'metric':metric,**stat})
    for row, p in zip(pairs,holm_adjust([r['paired_sign_flip_p'] for r in pairs])): row['holm_adjusted_p']=p
    return {'status':'已验证','dataset_version':plan['dataset_release_version'],
            'evaluation_scope':'item_and_process_conditioned_retrieval',
            'sample_count':len(per_sample),'out_of_scope_not_scored_count':len(samples)-len(per_sample),
            'sample_sha256':sha(sample_path),'input_result_sha256':sha(result_path),
            'top_k':results['top_k'],'alpha':results['alpha'],'seed':seed,
            'groups':groups,'paired_comparisons':pairs,'samples':per_sample,
            'limitations':['检索器已获知正确事项，流程校验已获知正确流程；本结果衡量条件检索。',
                           '多轮检索仅使用末轮文本；该结果未测量完整对话理解。',
                           '结构校验只检查所生成声明的引用一致性；实际错误由独立金标准覆盖率复算。',
                           '事项簇仅8个，簇级区间用于显示样本相关性带来的不确定性。'],
            'cost':{'external_api_calls':0,'external_api_cost_cny':0}}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=ROOT/'data/experiments/stage4-retrieval-analysis.json'); ap.add_argument('--repetitions',type=int,default=10000); args=ap.parse_args()
    started=time.perf_counter(); result=analyze(repetitions=args.repetitions)
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'samples':result['sample_count'],'all':result['groups']['all'],'comparisons':result['paired_comparisons'],'elapsed_seconds':time.perf_counter()-started},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
