import unittest

from scripts.repair_stage2_bindings import repair_sample


class BindingRepairTests(unittest.TestCase):
    def sample(self):
        return {'process_id': 'P', 'item_id': 'I', 'review_status': 'frozen',
                'gold': {'allowed_claim_ids': ['C'], 'supporting_evidence_ids': ['WRONG']},
                'leakage_control': {'check_status': 'passed'}}

    def processes(self):
        return {'P': {'item_id': 'I', 'allowed_claims': [{'claim_id': 'C', 'evidence_ids': ['E']}],
                      'evidence_snapshot': {'evidence_ids': ['E']}}}

    def test_repair_invalidates_review_and_keeps_input(self):
        sample = self.sample()
        result = repair_sample(sample, self.processes())
        self.assertEqual(['E'], result['gold']['supporting_evidence_ids'])
        self.assertEqual('draft', result['review_status'])
        self.assertEqual('pending', result['leakage_control']['check_status'])
        self.assertEqual(['WRONG'], sample['gold']['supporting_evidence_ids'])

    def test_unknown_claim_fails(self):
        sample = self.sample()
        sample['gold']['allowed_claim_ids'] = ['UNKNOWN']
        with self.assertRaises(KeyError):
            repair_sample(sample, self.processes())

    def test_snapshot_violation_fails(self):
        processes = self.processes()
        processes['P']['evidence_snapshot']['evidence_ids'] = []
        with self.assertRaises(ValueError):
            repair_sample(self.sample(), processes)
