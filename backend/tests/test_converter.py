import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.converter import (
    BaseConverter,
    CSVToJSONConverter,
    ConverterRegistry,
    ExcelToJSONConverter,
    JSONToYAMLConverter,
    MarkdownToPDFConverter,
    MarkdownToWordConverter,
    SRTToVTTConverter,
    UnsupportedConversionError,
    WordToMarkdownConverter,
    YAMLToJSONConverter,
    append_failure_dataset,
    classify_error_type,
    convert_file,
    converter_registry,
)


class ConverterRegistryTests(unittest.TestCase):
    def test_requested_converters_are_registered(self) -> None:
        expected = {
            ("md", "docx"),
            ("docx", "md"),
            ("md", "pdf"),
            ("xlsx", "json"),
            ("csv", "json"),
            ("json", "yaml"),
            ("yaml", "json"),
            ("srt", "vtt"),
        }
        self.assertTrue(expected.issubset(set(converter_registry.supported_pairs)))

    def test_requested_converters_inherit_base_converter(self) -> None:
        converter_types = (
            MarkdownToWordConverter,
            WordToMarkdownConverter,
            MarkdownToPDFConverter,
            ExcelToJSONConverter,
            CSVToJSONConverter,
            JSONToYAMLConverter,
            YAMLToJSONConverter,
            SRTToVTTConverter,
        )
        for converter_type in converter_types:
            self.assertTrue(issubclass(converter_type, BaseConverter))
            self.assertIn("convert", converter_type.__dict__)

    def test_duplicate_registration_is_rejected(self) -> None:
        registry = ConverterRegistry()
        registry.register(MarkdownToWordConverter())
        with self.assertRaises(ValueError):
            registry.register(MarkdownToWordConverter())

    def test_unknown_pair_is_rejected(self) -> None:
        with self.assertRaises(UnsupportedConversionError):
            converter_registry.get("pdf", "mp3")


class ConverterExecutionTests(unittest.TestCase):
    def test_existing_text_conversion_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "hello.txt"
            source.write_text("你好 ConvertBench", encoding="utf-8")

            output = convert_file(source, root / "outputs", "md")

            self.assertEqual(output.suffix, ".md")
            self.assertIn("你好 ConvertBench", output.read_text(encoding="utf-8"))

    def test_pandoc_converters_pass_expected_formats(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_convert_file(input_file: str, **kwargs: object) -> str:
            calls.append({"input_file": input_file, **kwargs})
            Path(str(kwargs["outputfile"])).write_bytes(b"converted")
            return ""

        fake_pypandoc = SimpleNamespace(convert_file=fake_convert_file)
        cases = (
            (MarkdownToWordConverter(), "input.md", "output.docx", "markdown", "docx"),
            (WordToMarkdownConverter(), "input.docx", "output.md", "docx", "markdown"),
            (MarkdownToPDFConverter(), "input.md", "output.pdf", "markdown", "pdf"),
        )

        with patch.dict(sys.modules, {"pypandoc": fake_pypandoc}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for converter, input_name, output_name, source_format, target_format in cases:
                    input_path = root / input_name
                    output_path = root / output_name
                    input_path.write_text("# 测试", encoding="utf-8")
                    converter.convert(input_path, output_path)
                    self.assertTrue(output_path.is_file())
                    self.assertEqual(calls[-1]["format"], source_format)
                    self.assertEqual(calls[-1]["to"], target_format)

    def test_excel_to_json_preserves_sheet_rows(self) -> None:
        worksheet = SimpleNamespace(
            title="数据",
            iter_rows=lambda values_only: [("name", "value"), ("alpha", 1)],
        )
        workbook = SimpleNamespace(worksheets=[worksheet], close=lambda: None)
        fake_openpyxl = SimpleNamespace(load_workbook=lambda *args, **kwargs: workbook)

        with patch.dict(sys.modules, {"openpyxl": fake_openpyxl}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "input.xlsx"
                output = root / "output.json"
                source.write_bytes(b"fake workbook")
                ExcelToJSONConverter().convert(source, output)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(data["sheets"][0]["name"], "数据")
                self.assertEqual(data["sheets"][0]["rows"][1], ["alpha", 1])

    def test_csv_to_json_uses_record_orientation(self) -> None:
        dataframe = SimpleNamespace(
            to_json=lambda **kwargs: '[\n  {"name":"测试","value":1}\n]'
        )
        fake_pandas = SimpleNamespace(read_csv=lambda *args, **kwargs: dataframe)

        with patch.dict(sys.modules, {"pandas": fake_pandas}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "input.csv"
                output = root / "output.json"
                source.write_text("name,value\n测试,1", encoding="utf-8")
                CSVToJSONConverter().convert(source, output)
                self.assertEqual(json.loads(output.read_text(encoding="utf-8"))[0]["name"], "测试")

    def test_json_and_yaml_converters_use_safe_yaml_apis(self) -> None:
        fake_yaml = SimpleNamespace(
            safe_dump=lambda data, **kwargs: "name: 测试\n",
            safe_load=lambda text: {"name": "测试"},
        )

        with patch.dict(sys.modules, {"yaml": fake_yaml}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                json_input = root / "input.json"
                yaml_output = root / "output.yaml"
                json_input.write_text('{"name":"测试"}', encoding="utf-8")
                JSONToYAMLConverter().convert(json_input, yaml_output)
                self.assertEqual(yaml_output.read_text(encoding="utf-8"), "name: 测试\n")

                yaml_input = root / "input.yaml"
                json_output = root / "output.json"
                yaml_input.write_text("name: 测试\n", encoding="utf-8")
                YAMLToJSONConverter().convert(yaml_input, json_output)
                self.assertEqual(json.loads(json_output.read_text(encoding="utf-8"))["name"], "测试")

    def test_srt_to_vtt_requests_vtt_output(self) -> None:
        observed: dict[str, object] = {}

        def save(path: str, **kwargs: object) -> None:
            observed.update(kwargs)
            Path(path).write_text("WEBVTT\n", encoding="utf-8")

        fake_pysubs2 = SimpleNamespace(load=lambda *args, **kwargs: SimpleNamespace(save=save))
        with patch.dict(sys.modules, {"pysubs2": fake_pysubs2}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "input.srt"
                output = root / "output.vtt"
                source.write_text("1\n00:00:00,000 --> 00:00:01,000\n测试\n", encoding="utf-8")
                SRTToVTTConverter().convert(source, output)
                self.assertEqual(observed["format_"], "vtt")
                self.assertTrue(output.read_text(encoding="utf-8").startswith("WEBVTT"))


class ErrorClassificationTests(unittest.TestCase):
    def test_every_error_type_is_recognized(self) -> None:
        cases = (
            ("Unsupported conversion: xyz -> md", "unsupported_format"),
            ("Pandoc is unavailable", "missing_dependency"),
            ("File is not a zip file", "invalid_input"),
            ("Failed to read input: permission denied", "file_read_error"),
            ("Failed to write output: read-only file system", "file_write_error"),
            (RuntimeError("unexpected converter failure"), "converter_error"),
            (None, "unknown"),
        )
        for error, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_error_type(error), expected)

    def test_specific_rules_take_priority(self) -> None:
        message = "Unsupported conversion: md -> docx; Pandoc is unavailable"
        self.assertEqual(classify_error_type(message), "unsupported_format")

    def test_failure_record_contains_error_type_and_keeps_original_fields(self) -> None:
        case = SimpleNamespace(
            id="case-id",
            original_filename="hello.xyz",
            source_format="xyz",
            target_format="md",
            file_size=47,
            error_message="Unsupported conversion: xyz -> md / 暂不支持该格式",
        )
        with tempfile.TemporaryDirectory() as directory:
            dataset_dir = Path(directory)
            append_failure_dataset(case, dataset_dir, error=UnsupportedConversionError(case.error_message))
            record = json.loads(
                (dataset_dir / "conversion_failures.jsonl").read_text(encoding="utf-8")
            )

        self.assertEqual(record["error_type"], "unsupported_format")
        self.assertEqual(record["case_id"], case.id)
        self.assertEqual(record["original_filename"], case.original_filename)
        self.assertEqual(record["source_format"], case.source_format)
        self.assertEqual(record["target_format"], case.target_format)
        self.assertEqual(record["file_size"], case.file_size)
        self.assertEqual(record["error_message"], case.error_message)
        self.assertIn("captured_at", record)


if __name__ == "__main__":
    unittest.main()
