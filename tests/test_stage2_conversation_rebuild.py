import unittest

from scripts.rebuild_stage2_conversations import rebuild


class ConversationRebuildTests(unittest.TestCase):
    def base(self, scenario='direct', turn_structure='single_turn'):
        return {'sample_id': 'S2E-PP-007', 'allocation_item_id': 'UG_PROOF_PRINT',
                'scenario_type': scenario, 'difficulty': 'medium', 'version_risk': 'stable',
                'turn_structure': turn_structure, 'conversation': [], 'review_status': 'frozen',
                'leakage_control': {'check_status': 'passed'}}

    def test_dimensions_are_in_conversation(self):
        row = rebuild(self.base('version_conflict'))
        self.assertIn('版本', row['conversation'][0]['text'])
        self.assertEqual('draft', row['review_status'])
        self.assertEqual('pending', row['leakage_control']['check_status'])

    def test_multiturn_has_three_distinct_turns(self):
        row = rebuild(self.base('multi_turn', 'multi_turn'))
        self.assertEqual(3, len(row['conversation']))
        self.assertEqual(3, len({turn['text'] for turn in row['conversation']}))

    def test_out_of_scope_is_scoped(self):
        row = rebuild(self.base('out_of_scope'))
        self.assertIn('服务范围', row['conversation'][0]['text'])
