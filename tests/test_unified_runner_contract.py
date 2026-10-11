import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class UnifiedRunnerContractTests(unittest.TestCase):
    def test_runner_requires_api_key_without_calling_network(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, 'scripts/run_stage3_unified.py', '--item', 'UG_CREDENTIAL_REISSUE',
                                     '--process', 'PROC_UG_CREDENTIAL_DEGREE_V001', '--query', '照片',
                                     '--output', str(Path(directory) / 'out.json')], cwd=root,
                                    env={k: v for k, v in __import__('os').environ.items() if k != 'DASHSCOPE_API_KEY'},
                                    capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('DASHSCOPE_API_KEY', result.stderr)
