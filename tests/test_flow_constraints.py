import unittest

from app.backend.flow_constraints import supported_process_context


class FlowConstraintTests(unittest.TestCase):
    def process(self):
        return {'process_id': 'P', 'evidence_snapshot': {'evidence_ids': ['E1', 'E2']},
                'allowed_claims': [{'claim_id': 'C1', 'evidence_ids': ['E1']}],
                'steps': [{'step_id': 'S1', 'evidence_ids': ['E1']},
                          {'step_id': 'S2', 'evidence_ids': ['E2']}],
                'materials': [{'material_id': 'M1', 'evidence_ids': ['E1']}]}

    def test_only_fully_supported_nodes_are_returned(self):
        result = supported_process_context(self.process(), {'E1', 'E2'})
        self.assertEqual(['S1'], result['step_ids'])
        self.assertEqual(['M1'], result['material_ids'])

    def test_unretrieved_evidence_returns_empty_context(self):
        result = supported_process_context(self.process(), set())
        self.assertEqual([], result['claim_ids'])
        self.assertEqual([], result['step_ids'])

    def test_process_snapshot_limits_context(self):
        result = supported_process_context(self.process(), {'E1', 'FOREIGN'})
        self.assertEqual(['E1'], result['evidence_ids'])
