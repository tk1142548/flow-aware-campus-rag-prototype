import copy
import unittest

from app.backend.claim_validation import validate_claims


class ClaimValidationTests(unittest.TestCase):
    def setUp(self):
        self.claim = {'claim_id': 'C', 'text': '提交照片两张', 'evidence_ids': ['E']}
        self.process = {'allowed_claims': [self.claim], 'evidence_snapshot': {'evidence_ids': ['E']}}

    def test_exact_claim_passes(self):
        self.assertEqual([], validate_claims(self.process, {'E'}, [self.claim]))

    def test_unretrieved_evidence_fails(self):
        self.assertEqual('citation_outside_candidates', validate_claims(self.process, set(), [self.claim])[0]['code'])

    def test_modified_text_fails(self):
        claim = copy.deepcopy(self.claim)
        claim['text'] = '提交照片一张'
        self.assertEqual('claim_text_mismatch', validate_claims(self.process, {'E'}, [claim])[0]['code'])

    def test_unknown_claim_and_empty_citations_fail(self):
        self.assertEqual('unknown_claim', validate_claims(self.process, {'E'}, [{'claim_id': 'X'}])[0]['code'])
        claim = {**self.claim, 'evidence_ids': []}
        self.assertEqual('invalid_citations', validate_claims(self.process, {'E'}, [claim])[0]['code'])

    def test_snapshot_and_duplicate_constraints(self):
        self.assertTrue(validate_claims(self.process, {'E'}, [self.claim, self.claim]))
        self.process['evidence_snapshot']['evidence_ids'] = []
        self.assertTrue(validate_claims(self.process, {'E'}, [self.claim]))
