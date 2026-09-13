import json
import csv
from io import StringIO
import tempfile
import unittest
from pathlib import Path

from app.services.badcase_service import BadCaseService


RECORDS = [
    {
        "case_id": "case-1",
        "original_filename": "hello.xyz",
        "source_format": "xyz",
        "target_format": "md",
        "file_size": 47,
        "error_message": "Unsupported conversion: xyz -> md",
        "captured_at": "2026-09-10T18:59:46+00:00",
    },
    {
        "case_id": "case-2",
        "original_filename": "sheet.xlsx",
        "source_format": "xlsx",
        "target_format": "json",
        "file_size": 1024,
        "error_message": "File is not a zip file",
        "error_type": "converter_error",
        "captured_at": "2026-09-11T03:42:28+00:00",
    },
    {
        "case_id": "case-3",
        "original_filename": "second.xyz",
        "source_format": "xyz",
        "target_format": "json",
        "file_size": 12,
        "error_message": "Unsupported format",
        "error_type": "unsupported_format",
        "captured_at": "2026-09-11T04:00:00+00:00",
    },
]


class BadCaseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.dataset_path = Path(self.temp_directory.name) / "conversion_failures.jsonl"
        lines = [json.dumps(record) for record in RECORDS]
        lines.insert(1, "{this line is broken")
        self.dataset_path.write_text("\n".join(lines), encoding="utf-8")
        self.service = BadCaseService(self.dataset_path)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_missing_file_returns_empty_results(self) -> None:
        service = BadCaseService(Path(self.temp_directory.name) / "missing.jsonl")
        self.assertEqual(service.list_badcases().items, [])
        self.assertEqual(service.get_stats().total, 0)

    def test_invalid_line_is_skipped_and_error_type_defaults_to_unknown(self) -> None:
        items = self.service.read_all()
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].error_type, "unknown")

    def test_filters_and_keyword_are_combined(self) -> None:
        result = self.service.list_badcases(source_format="xyz", keyword="hello")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].case_id, "case-1")

    def test_sort_and_pagination(self) -> None:
        result = self.service.list_badcases(
            sort_by="file_size",
            order="desc",
            page=2,
            page_size=1,
        )
        self.assertEqual(result.total, 3)
        self.assertEqual(result.items[0].file_size, 47)

    def test_get_detail_and_missing_case(self) -> None:
        self.assertEqual(self.service.get_badcase("case-2").original_filename, "sheet.xlsx")
        self.assertIsNone(self.service.get_badcase("missing"))

    def test_stats_include_all_dimensions(self) -> None:
        stats = self.service.get_stats()
        self.assertEqual(stats.total, 3)
        self.assertEqual(stats.by_source_format, {"xyz": 2, "xlsx": 1})
        self.assertEqual(stats.by_target_format, {"json": 2, "md": 1})
        self.assertEqual(stats.by_error_type["unknown"], 1)
        self.assertEqual(stats.by_date, {"2026-09-11": 2, "2026-09-10": 1})

    def test_dataset_stats_include_latest_ten(self) -> None:
        stats = self.service.get_dataset_stats()
        self.assertEqual(stats.total, 3)
        self.assertEqual(len(stats.latest_badcases), 3)
        self.assertEqual(stats.latest_badcases[0].case_id, "case-3")
        self.assertEqual(stats.latest_badcases[-1].case_id, "case-1")

    def test_json_and_jsonl_exports_preserve_records(self) -> None:
        json_records = json.loads(self.service.export_dataset("json").decode("utf-8"))
        jsonl_records = [
            json.loads(line)
            for line in self.service.export_dataset("jsonl").decode("utf-8").splitlines()
        ]
        self.assertEqual(len(json_records), 3)
        self.assertEqual(json_records, jsonl_records)
        self.assertIn("error_type", json_records[0])

    def test_csv_export_has_all_fields_and_utf8_content(self) -> None:
        text = self.service.export_dataset("csv").decode("utf-8-sig")
        records = list(csv.DictReader(StringIO(text)))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["case_id"], "case-3")
        self.assertEqual(
            set(records[0]),
            {
                "case_id",
                "original_filename",
                "source_format",
                "target_format",
                "file_size",
                "error_message",
                "error_type",
                "captured_at",
            },
        )

    def test_export_filters_are_combined(self) -> None:
        content = self.service.export_dataset(
            "json",
            source_format="xyz",
            target_format="md",
            error_type="unknown",
        )
        records = json.loads(content.decode("utf-8"))
        self.assertEqual([record["case_id"] for record in records], ["case-1"])


if __name__ == "__main__":
    unittest.main()
