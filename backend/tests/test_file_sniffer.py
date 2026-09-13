import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import Workbook

from app.services.badcase_service import BadCaseService
from app.services.converter import (
    ExtensionMismatchError,
    UnknownFileTypeError,
    append_failure_dataset,
    classify_error_type,
    convert_file,
)
from app.services.file_sniffer import sniff_file_type


class FileSnifferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.magic_patch = patch(
            "app.services.file_sniffer._sniff_with_python_magic",
            return_value=None,
        )
        self.magic_patch.start()

    def tearDown(self) -> None:
        self.magic_patch.stop()

    def test_magic_numbers_and_office_zip_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xlsx_path = root / "book.bin"
            docx_path = root / "document.bin"
            zip_path = root / "archive.bin"
            pdf_path = root / "document.bin.pdf"

            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr("xl/workbook.xml", "<workbook />")
            with zipfile.ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", "<document />")
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("readme.txt", "hello")
            pdf_path.write_bytes(b"%PDF-1.7\n")

            self.assertEqual(sniff_file_type(xlsx_path), "xlsx")
            self.assertEqual(sniff_file_type(docx_path), "docx")
            self.assertEqual(sniff_file_type(zip_path), "zip")
            self.assertEqual(sniff_file_type(pdf_path), "pdf")

    def test_structured_text_types_are_detected(self) -> None:
        samples = {
            "data.json": ('{"name": "ConvertBench"}', "json"),
            "config.yaml": ("name: ConvertBench\nfeatures:\n- sniffing\n- export\n", "yaml"),
            "table.csv": ("name,value\nalpha,1\nbeta,2\n", "csv"),
            "readme.md": ("# ConvertBench\n\n**Failure becomes data.**\n", "markdown"),
            "caption.srt": ("1\n00:00:00,000 --> 00:00:01,000\n你好\n", "srt"),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, (content, expected) in samples.items():
                with self.subTest(expected=expected):
                    path = root / filename
                    path.write_text(content, encoding="utf-8")
                    self.assertEqual(sniff_file_type(path), expected)

    def test_real_xlsx_and_csv_convert_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xlsx_path = root / "real.xlsx"
            workbook = Workbook()
            workbook.active.append(["name", "value"])
            workbook.active.append(["alpha", 1])
            workbook.save(xlsx_path)

            csv_path = root / "real.csv"
            csv_path.write_text("name,value\nalpha,1\n", encoding="utf-8")

            xlsx_output = convert_file(xlsx_path, root / "xlsx-output", "json")
            csv_output = convert_file(csv_path, root / "csv-output", "json")

            self.assertEqual(json.loads(xlsx_output.read_text(encoding="utf-8"))["sheets"][0]["rows"][1], ["alpha", 1])
            self.assertEqual(json.loads(csv_output.read_text(encoding="utf-8"))[0]["name"], "alpha")

    def test_markdown_renamed_to_xlsx_is_extension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "report.xlsx"
            source.write_text("# Report\n\nThis is Markdown.\n", encoding="utf-8")

            with self.assertRaises(ExtensionMismatchError) as captured:
                convert_file(source, root / "output", "json")

            message = str(captured.exception)
            self.assertIn("文件扩展名是 .xlsx", message)
            self.assertIn("真实内容是 markdown", message)
            self.assertEqual(classify_error_type(captured.exception), "extension_mismatch")

    def test_empty_file_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "empty.txt"
            source.touch()

            self.assertEqual(sniff_file_type(source), "unknown")
            with self.assertRaises(UnknownFileTypeError) as captured:
                convert_file(source, root / "output", "md")
            self.assertEqual(classify_error_type(captured.exception), "unknown")

    def test_mismatch_is_available_in_stats_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            error = ExtensionMismatchError(
                "文件扩展名是 .xlsx，但真实内容是 markdown，请确认文件类型"
            )
            case = SimpleNamespace(
                id="mismatch-case",
                original_filename="report.xlsx",
                source_format="xlsx",
                target_format="json",
                file_size=28,
                error_message=str(error),
            )
            append_failure_dataset(case, root, error=error)

            service = BadCaseService(root / "conversion_failures.jsonl")
            self.assertEqual(service.get_stats().by_error_type, {"extension_mismatch": 1})
            exported = json.loads(
                service.export_dataset("json", error_type="extension_mismatch").decode("utf-8")
            )
            self.assertEqual(exported[0]["error_type"], "extension_mismatch")

if __name__ == "__main__":
    unittest.main()
