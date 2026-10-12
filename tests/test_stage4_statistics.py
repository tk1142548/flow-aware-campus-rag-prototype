import unittest

from app.backend.stage4_statistics import paired_analysis, retrieval_observation


class Stage4StatisticsTests(unittest.TestCase):
    def test_nonempty_wrong_hits_are_a_retrieval_miss(self):
        result = retrieval_observation(['OTHER'], {'RIGHT'})
        self.assertEqual(0, result['recall_at_k'])
        self.assertEqual('retrieval_miss', result['retrieval_error'])

    def test_partial_retrieval_is_not_complete(self):
        result = retrieval_observation(['A', 'X'], {'A', 'B'})
        self.assertEqual(0.5, result['recall_at_k'])
        self.assertFalse(result['complete_evidence'])
        self.assertEqual('partial_retrieval', result['retrieval_error'])

    def test_identical_pair_is_zero_with_no_significance(self):
        result = paired_analysis([0, 1, 0.5], [0, 1, 0.5], ['a', 'b', 'b'], 500, 42)
        self.assertEqual(0, result['mean_difference'])
        self.assertEqual([0, 0], result['sample_bootstrap_ci95'])
        self.assertEqual(1, result['paired_sign_flip_p'])

    def test_direction_and_repeatability(self):
        first = paired_analysis([0, 0, 0, 0], [1, 1, 1, 1], ['a', 'a', 'b', 'b'], 500, 42)
        second = paired_analysis([0, 0, 0, 0], [1, 1, 1, 1], ['a', 'a', 'b', 'b'], 500, 42)
        self.assertEqual(first, second)
        self.assertEqual(1, first['mean_difference'])
        self.assertEqual([1, 1], first['item_cluster_bootstrap_ci95'])

    def test_invalid_pairs_are_rejected(self):
        for left, right, items in [([], [], []), ([1], [1, 0], ['a']), ([float('nan')], [1], ['a'])]:
            with self.assertRaises(ValueError):
                paired_analysis(left, right, items, 100, 0)


if __name__ == '__main__': unittest.main()
