import json
import tempfile
import unittest
from pathlib import Path

from scripts.repair_jsonl_boundaries import decode_records, repair


class JsonlBoundaryRepairTests(unittest.TestCase):
    def test_string_escapes_are_preserved(self):
        rows = [{"text": "a\nb", "literal": r"\n", "quote": '\"}\\n{'} , {"nested": {"x": 1}}]
        text = r"\n".join(json.dumps(row) for row in rows) + r"\n"
        self.assertEqual(decode_records(text), rows)

    def test_corrupt_input_leaves_original_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            backup = Path(directory) / "backup"
            original = b'{"id":1}\\n{"id":'
            path.write_bytes(original)
            with self.assertRaises(json.JSONDecodeError):
                repair(path, backup)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(backup.exists())

    def test_backup_and_recovered_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            backup = Path(directory) / "backup"
            original = b'{"id":1}\\n{"id":2}\\n'
            path.write_bytes(original)
            self.assertEqual(repair(path, backup), 2)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual([json.loads(line) for line in path.read_text().splitlines()], [{"id": 1}, {"id": 2}])
            with self.assertRaises(FileExistsError):
                repair(path, backup)


if __name__ == "__main__":
    unittest.main()
