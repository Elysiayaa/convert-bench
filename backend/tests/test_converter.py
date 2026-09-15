import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services.badcase_service import BadCaseService

from app.services.converter import (
    BaseConverter,
    BmpToPngConverter,
    CSVToJSONConverter,
    ConverterRegistry,
    ExcelToJSONConverter,
    GifToPngConverter,
    ImageDecodeError,
    ImageEncodeError,
    ImageLossyWarning,
    InvalidInputError,
    JpgToPngConverter,
    JpgToWebpConverter,
    JSONToYAMLConverter,
    MarkdownToPDFConverter,
    MarkdownToWordConverter,
    PngToJpgConverter,
    PngToWebpConverter,
    SRTToVTTConverter,
    UnsupportedConversionError,
    WordToMarkdownConverter,
    WebpToPngConverter,
    YAMLToJSONConverter,
    append_failure_dataset,
    classify_error_type,
    convert_file,
    converter_registry,
    get_conversion_warning,
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
            ("png", "jpg"),
            ("jpg", "png"),
            ("png", "webp"),
            ("webp", "png"),
            ("jpg", "webp"),
            ("bmp", "png"),
            ("gif", "png"),
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
    def test_every_image_converter_creates_expected_format(self) -> None:
        converter_cases = (
            (PngToJpgConverter(), "png", "jpg", "JPEG"),
            (JpgToPngConverter(), "jpg", "png", "PNG"),
            (PngToWebpConverter(), "png", "webp", "WEBP"),
            (WebpToPngConverter(), "webp", "png", "PNG"),
            (JpgToWebpConverter(), "jpg", "webp", "WEBP"),
            (BmpToPngConverter(), "bmp", "png", "PNG"),
            (GifToPngConverter(), "gif", "png", "PNG"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (converter, source_suffix, target_suffix, expected_format) in enumerate(converter_cases):
                with self.subTest(converter=type(converter).__name__):
                    source = root / f"source-{index}.{source_suffix}"
                    output = root / f"output-{index}.{target_suffix}"
                    mode = "RGBA" if source_suffix == "png" else "RGB"
                    color = (20, 40, 60, 255) if mode == "RGBA" else (20, 40, 60)
                    Image.new(mode, (4, 3), color).save(source)

                    converter.convert(source, output)

                    with Image.open(output) as converted:
                        self.assertEqual(converted.format, expected_format)
                        self.assertEqual(converted.size, (4, 3))

    def test_gif_to_png_uses_only_first_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "animated.gif"
            output = root / "first-frame.png"
            first = Image.new("RGB", (2, 2), "red")
            second = Image.new("RGB", (2, 2), "blue")
            first.save(source, save_all=True, append_images=[second], duration=100, loop=0)

            GifToPngConverter().convert(source, output)

            with Image.open(output) as converted:
                self.assertEqual(getattr(converted, "n_frames", 1), 1)
                self.assertEqual(converted.convert("RGB").getpixel((0, 0)), (255, 0, 0))
            warning = get_conversion_warning("gif", "png")
            self.assertIsInstance(warning, ImageLossyWarning)
            self.assertIn("只保留第一帧", str(warning))

    def test_transparent_png_to_jpg_is_filled_with_white(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "transparent.png"
            output = root / "result.jpg"
            image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            for x in range(8, 16):
                for y in range(16):
                    image.putpixel((x, y), (255, 0, 0, 255))
            image.save(source)

            PngToJpgConverter().convert(source, output)

            with Image.open(output) as converted:
                red, green, blue = converted.convert("RGB").getpixel((2, 8))
                self.assertGreater(red, 240)
                self.assertGreater(green, 240)
                self.assertGreater(blue, 240)

    def test_corrupted_png_is_reported_as_image_decode_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\ncorrupted")

            with self.assertRaises(ImageDecodeError) as captured:
                convert_file(source, root / "outputs", "jpg")
            self.assertEqual(classify_error_type(captured.exception), "image_decode_error")

    def test_oversized_image_is_rejected_before_pixel_decode(self) -> None:
        class HeaderOnlyImage:
            size = (13_619, 10_000)

            def __enter__(self) -> "HeaderOnlyImage":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def load(self) -> None:
                raise AssertionError("超大图片不应进入像素解码")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "oversized.png"
            source.write_bytes(b"header")
            output = root / "result.jpg"

            with patch("PIL.Image.open", return_value=HeaderOnlyImage()):
                with self.assertRaises(InvalidInputError) as captured:
                    PngToJpgConverter().convert(source, output)

            error = captured.exception
            self.assertEqual(classify_error_type(error), "invalid_input")
            self.assertEqual(
                str(error),
                "图片尺寸过大（136190000 像素），超过限制（50000000 像素），已拒绝转换",
            )
            self.assertEqual(error.image_dimensions["width"], 13_619)  # type: ignore[attr-defined]

            case = SimpleNamespace(
                id="oversized-case",
                original_filename="oversized.png",
                source_format="png",
                target_format="jpg",
                file_size=6,
                error_message=str(error),
            )
            append_failure_dataset(case, root / "dataset", error=error)
            item = BadCaseService(root / "dataset" / "conversion_failures.jsonl").read_all()[0]
            self.assertEqual(item.severity, "error")
            self.assertEqual(item.image_dimensions.total_pixels, 136_190_000)

    def test_decompression_bomb_error_becomes_invalid_input(self) -> None:
        pillow_error = Image.DecompressionBombError(
            "Image size (136190920 pixels) exceeds limit of 100000000 pixels"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bomb.png"
            source.write_bytes(b"header")

            with patch("PIL.Image.open", side_effect=pillow_error):
                with self.assertRaises(InvalidInputError) as captured:
                    PngToJpgConverter().convert(source, root / "result.jpg")

            self.assertEqual(classify_error_type(captured.exception), "invalid_input")
            self.assertEqual(
                str(captured.exception),
                "图片尺寸过大（136190920 像素），超过限制（50000000 像素），已拒绝转换",
            )

    def test_image_larger_than_50_mb_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "huge.png"
            with source.open("wb") as image_file:
                image_file.seek(50 * 1024 * 1024)
                image_file.write(b"x")

            with self.assertRaises(InvalidInputError) as captured:
                convert_file(source, root / "outputs", "jpg")
            self.assertEqual(classify_error_type(captured.exception), "invalid_input")

    def test_jpeg_extension_uses_jpg_converter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "photo.jpeg"
            Image.new("RGB", (2, 2), "green").save(source)

            output = convert_file(source, root / "outputs", "png")

            with Image.open(output) as converted:
                self.assertEqual(converted.format, "PNG")

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
            ("文件扩展名是 .xlsx，但真实内容是 markdown，请确认文件类型", "extension_mismatch"),
            ("Unsupported conversion: xyz -> md", "unsupported_format"),
            ("Pandoc is unavailable", "missing_dependency"),
            ("File is not a zip file", "invalid_input"),
            ("Failed to read input: permission denied", "file_read_error"),
            ("Failed to write output: read-only file system", "file_write_error"),
            (ImageDecodeError("图片无法解码"), "image_decode_error"),
            (ImageEncodeError("图片编码失败"), "image_encode_error"),
            (ImageLossyWarning("有损转换"), "image_lossy_warning"),
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
        self.assertEqual(record["severity"], "error")
        self.assertIsNone(record["image_dimensions"])
        self.assertEqual(record["case_id"], case.id)
        self.assertEqual(record["original_filename"], case.original_filename)
        self.assertEqual(record["source_format"], case.source_format)
        self.assertEqual(record["target_format"], case.target_format)
        self.assertEqual(record["file_size"], case.file_size)
        self.assertEqual(record["error_message"], case.error_message)
        self.assertIn("captured_at", record)

    def test_image_warning_is_visible_in_badcase_stats(self) -> None:
        case = SimpleNamespace(
            id="gif-warning",
            original_filename="animated.gif",
            source_format="gif",
            target_format="png",
            file_size=128,
            error_message=None,
        )
        warning = get_conversion_warning("gif", "png")
        self.assertIsNotNone(warning)
        with tempfile.TemporaryDirectory() as directory:
            dataset_dir = Path(directory)
            append_failure_dataset(case, dataset_dir, error=warning, message=str(warning))
            service = BadCaseService(dataset_dir / "conversion_failures.jsonl")

            self.assertEqual(service.get_stats().by_error_type, {"image_lossy_warning": 1})
            self.assertEqual(service.get_stats().by_severity, {"warning": 1})
            self.assertIn("只保留第一帧", service.read_all()[0].error_message)


if __name__ == "__main__":
    unittest.main()
