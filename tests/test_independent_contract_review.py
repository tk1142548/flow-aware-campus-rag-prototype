import unittest

from scripts.run_stage2_independent_contract_review import review


class IndependentContractReviewTests(unittest.TestCase):
    def process(self):
        return {'item_id': 'I', 'review': {'status': 'verified'},
                'evidence_snapshot': {'evidence_ids': ['E']},
                'allowed_claims': [{'claim_id': 'C', 'evidence_ids': ['E']}]}

    def sample(self):
        return {'sample_id': 'S', 'scenario_type': 'direct', 'item_id': 'I', 'process_id': 'P',
                'gold': {'allowed_claim_ids': ['C'], 'supporting_evidence_ids': ['E']},
                'leakage_control': {'check_status': 'passed'}}

    def test_pass_is_still_human_review_required(self):
        result = review(self.sample(), {'P': self.process()}, {'E': {}})
        self.assertEqual('pass', result['status'])
        self.assertTrue(result['human_review_required'])

    def test_mismatch_fails(self):
        sample = self.sample()
        sample['gold']['supporting_evidence_ids'] = []
        self.assertEqual('fail', review(sample, {'P': self.process()}, {'E': {}})['status'])
