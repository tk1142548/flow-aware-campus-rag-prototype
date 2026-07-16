from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.capture_official_sources import (
    safe_output_path,
    safe_record_path,
    validate_content,
    write_jsonl,
)


class OfficialSourceCaptureTests(unittest.TestCase):
    def test_capture_paths_stay_inside_declared_repository_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            source_path = safe_output_path(
                root, "data/sources/SRC_EXAMPLE/document.pdf"
            )
            record_path = safe_record_path(
                root, "data/research/source_records.jsonl"
            )

            self.assertEqual(
                root / "data/sources/SRC_EXAMPLE/document.pdf", source_path
            )
            self.assertEqual(
                root / "data/research/source_records.jsonl", record_path
            )

    def test_capture_paths_reject_parent_traversal_and_directory_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            invalid_source_paths = [
                "data/sources",
                "data/sources/../../outside.pdf",
            ]
            invalid_record_paths = [
                "data/research",
                "data/research/../../outside.jsonl",
            ]

            for path in invalid_source_paths:
                with self.subTest(path=path):
                    with self.assertRaises(ValueError):
                        safe_output_path(root, path)

            for path in invalid_record_paths:
                with self.subTest(path=path):
                    with self.assertRaises(ValueError):
                        safe_record_path(root, path)

    def test_content_validation_checks_media_type_and_file_signature(self) -> None:
        validate_content(
            "SRC_HTML",
            "html",
            "text/html",
            "text/html",
            b"<!doctype html><html><body>official</body></html>",
        )
        validate_content(
            "SRC_PDF",
            "pdf",
            "application/pdf",
            "application/pdf",
            b"%PDF-1.7\n",
        )

        invalid_cases = [
            ("html", "text/html", "application/pdf", b"<html></html>"),
            ("html", "text/html", "text/html", b"not html"),
            ("pdf", "application/pdf", "application/pdf", b"not pdf"),
        ]
        for content_format, expected_type, actual_type, content in invalid_cases:
            with self.subTest(
                content_format=content_format,
                expected_type=expected_type,
                actual_type=actual_type,
            ):
                with self.assertRaises(ValueError):
                    validate_content(
                        "SRC_INVALID",
                        content_format,
                        expected_type,
                        actual_type,
                        content,
                    )

    def test_source_record_output_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "source_records.jsonl"
            rows = [{"source_id": "SRC_EXAMPLE"}]

            write_jsonl(output_path, rows)

            with self.assertRaises(FileExistsError):
                write_jsonl(output_path, rows)


if __name__ == "__main__":
    unittest.main()
