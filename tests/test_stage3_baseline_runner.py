import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BaselineRunnerTests(unittest.TestCase):
    def test_development_runner_is_deterministic(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            outputs = []
            for index in range(2):
                output = Path(directory) / f'{index}.json'
                subprocess.run([sys.executable, 'scripts/run_stage3_baseline.py',
                                '--item', 'UG_CREDENTIAL_REISSUE',
                                '--source', 'SRC_UG_CREDENTIAL_DEGREE_20210317',
                                '--query', '学位证明书照片材料', '--output', str(output)],
                               cwd=root, check=True, capture_output=True, text=True)
                outputs.append(json.loads(output.read_text(encoding='utf-8')))
            self.assertEqual(outputs[0], outputs[1])
            self.assertFalse(outputs[0]['formal_evaluation_enabled'])
