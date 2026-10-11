import json
import subprocess
import sys
import unittest
from pathlib import Path


class ReviewChecklistTests(unittest.TestCase):
    def test_checklist_is_pending_and_complete(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable, 'scripts/build_stage2_review_checklist.py'], cwd=root, check=True, capture_output=True)
        rows = [json.loads(line) for line in (root / 'data/audit/stage2-independent-review-checklist.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(200, len(rows))
        self.assertTrue(all(row['review_status'] == 'pending' and row['decision'] is None for row in rows))
