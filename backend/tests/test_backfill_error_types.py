import json
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_error_types import backfill_error_types, infer_error_type


class ErrorTypeInferenceTests(unittest.TestCase):
    def test_each_supported_error_type_is_inferred(self) -> None:
        cases = (
            ("Unsupported conversion: xyz -> md", "unsupported_format"),
            ("Pandoc is unavailable; install it first", "missing_dependency"),
            ("xlsx -> json failed: File is not a zip file", "invalid_input"),
            (
                "文件扩展名是 .xlsx，但真实内容是 markdown，请确认文件类型",
                "extension_mismatch",
            ),
        )
        for message, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(infer_error_type(message), expected)

    def test_priority_and_existing_value_are_preserved(self) -> None:
        combined = (
            "Unsupported conversion; Pandoc is unavailable; not a zip file; "
            "文件扩展名是 .xlsx，但真实内容是 markdown"
        )
        self.assertEqual(infer_error_type(combined), "unsupported_format")
        self.assertEqual(infer_error_type("other failure", "converter_error"), "converter_error")

    def test_unknown_message_is_not_misclassified(self) -> None:
        self.assertEqual(infer_error_type("an unrelated historical error"), "unknown")
        self.assertEqual(infer_error_type("", "unknown"), "unknown")


class BackfillFileTests(unittest.TestCase):
    def test_dry_run_does_not_modify_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "failures.jsonl"
            original = json.dumps(
                {
                    "case_id": "case-1",
                    "error_message": "Unsupported conversion: xyz -> md",
                }
            ) + "\n"
            file_path.write_text(original, encoding="utf-8")

            stats = backfill_error_types(file_path, dry_run=True)

            self.assertEqual(file_path.read_text(encoding="utf-8"), original)
            self.assertEqual(stats.backfilled, 1)
            self.assertEqual(stats.before_by_error_type, {"unknown": 1})
            self.assertEqual(stats.after_by_error_type, {"unsupported_format": 1})

    def test_update_preserves_valid_type_and_field_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "failures.jsonl"
            records = [
                {
                    "case_id": "case-1",
                    "error_type": "unknown",
                    "error_message": "Pandoc is unavailable",
                    "captured_at": "2026-09-12T00:00:00+00:00",
                },
                {
                    "case_id": "case-2",
                    "error_message": "Unsupported conversion: xyz -> md",
                    "error_type": "converter_error",
                    "captured_at": "2026-09-12T00:01:00+00:00",
                },
            ]
            file_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            stats = backfill_error_types(file_path)
            updated_records = [
                json.loads(line) for line in file_path.read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(updated_records[0]["error_type"], "missing_dependency")
            self.assertEqual(updated_records[1]["error_type"], "converter_error")
            self.assertEqual(list(updated_records[0]), list(records[0]))
            self.assertEqual(list(updated_records[1]), list(records[1]))
            self.assertEqual(stats.backfilled, 1)

    def test_unknown_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "failures.jsonl"
            original = {
                "case_id": "case-unknown",
                "error_message": "an unrelated historical error",
                "error_type": "unknown",
            }
            file_path.write_text(json.dumps(original) + "\n", encoding="utf-8")

            stats = backfill_error_types(file_path)
            updated = json.loads(file_path.read_text(encoding="utf-8"))

            self.assertEqual(updated, original)
            self.assertEqual(stats.backfilled, 0)
            self.assertEqual(stats.unknown, 1)


if __name__ == "__main__":
    unittest.main()
