import unittest
from pathlib import Path

from app.backend.research_data import ResearchRepository
from app.backend.stage4_pipeline import extract_slots, generate, choose_process, choose_process_for_query


class Stage4PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo=ResearchRepository(Path(__file__).resolve().parents[1])

    def test_missing_duration_does_not_become_known(self):
        p=self.repo.processes['PROC_UG_LEAVE_REQUEST_V001']
        self.assertEqual({},extract_slots(p,'我要请假，天数尚未确定。',[]))

    def test_known_duration_is_extracted(self):
        p=self.repo.processes['PROC_UG_LEAVE_REQUEST_V001']
        self.assertEqual('3天',extract_slots(p,'我要请假3天。',[])['SL_LEAVE_DAYS'])

    def test_no_candidates_produce_abstention(self):
        result=generate(self.repo,'申请许可证',[],[], 'full')
        self.assertEqual('abstention',result['response_mode'])
        self.assertEqual([],result['evidence_ids'])

    def test_flow_steps_only_use_retrieved_evidence(self):
        p=self.repo.processes['PROC_UG_WITHDRAWAL_V001']
        ev=self.repo.evidence['UGW003']
        result=generate(self.repo,'我要主动申请退学',[(ev,1)],[], 'full')
        for step in result['steps']:
            required=next(s for s in p['steps'] if s['step_id']==step)['evidence_ids']
            self.assertLessEqual(set(required),{'UGW003'})

    def test_process_choice_uses_evidence_instead_of_gold(self):
        ev=self.repo.evidence['UGT006']
        p=choose_process(self.repo,[(ev,1)])
        self.assertEqual('PROC_UG_STUDENT_CARD_V001',p['process_id'])

    def test_out_of_scope_query_abstains_before_retrieval(self):
        self.assertIsNone(choose_process_for_query(self.repo,'我想申请宿舍床位'))

    def test_leave_duration_routes_to_leave_process(self):
        p=choose_process_for_query(self.repo,'我要请假3天')
        self.assertEqual('PROC_UG_LEAVE_REQUEST_V001',p['process_id'])

    def test_leave_question_does_not_emit_unasked_flow_steps(self):
        p=self.repo.processes['PROC_UG_LEAVE_REQUEST_V001']
        hits=[(self.repo.evidence[eid],1) for eid in p['evidence_snapshot']['evidence_ids']]
        result=generate(self.repo,'我要请假3天',hits,[], 'full')
        self.assertEqual([],result['steps'])
