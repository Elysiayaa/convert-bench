import json
import re
import shutil
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.conversion_case import ConversionCase


class ConversionError(RuntimeError):
    """转换执行失败。"""


class UnsupportedConversionError(ConversionError):
    """找不到匹配的转换器。"""


class BaseConverter(ABC):
    """所有格式转换器的统一基类。"""

    source_format: str
    target_format: str

    @abstractmethod
    def convert(self, input_path: Path, output_path: Path) -> None:
        """将输入文件转换后写入指定输出路径。"""

    def _prepare(self, input_path: Path, output_path: Path) -> None:
        if not input_path.is_file():
            raise ConversionError(f"Input file does not exist / 输入文件不存在: {input_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def _run_safely(self, input_path: Path, output_path: Path, action: Callable[[], None]) -> None:
        """统一清理失败时可能产生的不完整输出。"""

        self._prepare(input_path, output_path)
        try:
            action()
            if not output_path.is_file():
                raise ConversionError("Converter produced no output / 转换器未生成输出文件")
        except ConversionError:
            output_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise ConversionError(
                f"{self.source_format} -> {self.target_format} failed / 转换失败: {exc}"
            ) from exc


class PandocConverter(BaseConverter):
    """基于 Pandoc 的转换器公共实现。"""

    pandoc_source_format: str
    pandoc_target_format: str
    extra_args: list[str] = []

    def _convert_with_pandoc(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                import pypandoc
            except ImportError as exc:
                raise ConversionError("pypandoc is not installed / 未安装 pypandoc") from exc

            try:
                pypandoc.convert_file(
                    str(input_path),
                    to=self.pandoc_target_format,
                    format=self.pandoc_source_format,
                    outputfile=str(output_path),
                    extra_args=self.extra_args,
                )
            except OSError as exc:
                raise ConversionError(
                    "Pandoc is unavailable; use the backend Docker image or install Pandoc locally / "
                    "Pandoc 不可用，请使用后端 Docker 镜像或在本地安装 Pandoc"
                ) from exc

        self._run_safely(input_path, output_path, action)


class MarkdownToWordConverter(PandocConverter):
    source_format = "md"
    target_format = "docx"
    pandoc_source_format = "markdown"
    pandoc_target_format = "docx"

    def convert(self, input_path: Path, output_path: Path) -> None:
        self._convert_with_pandoc(input_path, output_path)


class WordToMarkdownConverter(PandocConverter):
    source_format = "docx"
    target_format = "md"
    pandoc_source_format = "docx"
    pandoc_target_format = "markdown"
    extra_args = ["--wrap=none"]

    def convert(self, input_path: Path, output_path: Path) -> None:
        self._convert_with_pandoc(input_path, output_path)


class MarkdownToPDFConverter(PandocConverter):
    source_format = "md"
    target_format = "pdf"
    pandoc_source_format = "markdown"
    pandoc_target_format = "pdf"
    # XeLaTeX 与 Noto CJK 字体由后端 Docker 镜像提供，支持中英文混排。
    extra_args = [
        "--pdf-engine=xelatex",
        "-V",
        "mainfont=Noto Serif CJK SC",
        "-V",
        "CJKmainfont=Noto Serif CJK SC",
    ]

    def convert(self, input_path: Path, output_path: Path) -> None:
        self._convert_with_pandoc(input_path, output_path)


class ExcelToJSONConverter(BaseConverter):
    source_format = "xlsx"
    target_format = "json"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                import openpyxl
            except ImportError as exc:
                raise ConversionError("openpyxl is not installed / 未安装 openpyxl") from exc

            workbook = openpyxl.load_workbook(input_path, read_only=True, data_only=True)
            try:
                payload = {
                    "sheets": [
                        {
                            "name": worksheet.title,
                            "rows": [list(row) for row in worksheet.iter_rows(values_only=True)],
                        }
                        for worksheet in workbook.worksheets
                    ]
                }
                output_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
                    encoding="utf-8",
                )
            finally:
                workbook.close()

        self._run_safely(input_path, output_path, action)


class CSVToJSONConverter(BaseConverter):
    source_format = "csv"
    target_format = "json"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                import pandas as pd
            except ImportError as exc:
                raise ConversionError("pandas is not installed / 未安装 pandas") from exc

            # utf-8-sig 同时兼容普通 UTF-8 与带 BOM 的 CSV。
            dataframe = pd.read_csv(input_path, encoding="utf-8-sig")
            output_path.write_text(
                dataframe.to_json(orient="records", force_ascii=False, indent=2),
                encoding="utf-8",
            )

        self._run_safely(input_path, output_path, action)


class JSONToYAMLConverter(BaseConverter):
    source_format = "json"
    target_format = "yaml"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                import yaml
            except ImportError as exc:
                raise ConversionError("PyYAML is not installed / 未安装 PyYAML") from exc

            data = json.loads(input_path.read_text(encoding="utf-8-sig"))
            output_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        self._run_safely(input_path, output_path, action)


class YAMLToJSONConverter(BaseConverter):
    source_format = "yaml"
    target_format = "json"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                import yaml
            except ImportError as exc:
                raise ConversionError("PyYAML is not installed / 未安装 PyYAML") from exc

            data = yaml.safe_load(input_path.read_text(encoding="utf-8-sig"))
            output_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),
                encoding="utf-8",
            )

        self._run_safely(input_path, output_path, action)


class SRTToVTTConverter(BaseConverter):
    source_format = "srt"
    target_format = "vtt"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                import pysubs2
            except ImportError as exc:
                raise ConversionError("pysubs2 is not installed / 未安装 pysubs2") from exc

            subtitles = pysubs2.load(str(input_path), encoding="utf-8")
            subtitles.save(str(output_path), format_="vtt", encoding="utf-8")

        self._run_safely(input_path, output_path, action)


class TextToMarkdownConverter(BaseConverter):
    source_format = "txt"
    target_format = "md"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            text = input_path.read_text(encoding="utf-8")
            output_path.write_text(f"# {input_path.stem}\n\n{text}\n", encoding="utf-8")

        self._run_safely(input_path, output_path, action)


class MarkdownToTextConverter(BaseConverter):
    source_format = "md"
    target_format = "txt"

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            text = input_path.read_text(encoding="utf-8")
            output_path.write_text(re.sub(r"[`*_>#-]", "", text), encoding="utf-8")

        self._run_safely(input_path, output_path, action)


class SameFormatConverter(BaseConverter):
    """同扩展名转换时保留原文件内容。"""

    source_format = "*"
    target_format = "*"

    def convert(self, input_path: Path, output_path: Path) -> None:
        self._run_safely(input_path, output_path, lambda: shutil.copy2(input_path, output_path))


class ConverterRegistry:
    """按照源格式和目标格式注册、查找转换器。"""

    def __init__(self) -> None:
        self._converters: dict[tuple[str, str], BaseConverter] = {}
        self._same_format_converter = SameFormatConverter()

    def register(self, converter: BaseConverter) -> None:
        if not isinstance(converter, BaseConverter):
            raise TypeError("converter must inherit BaseConverter / 转换器必须继承 BaseConverter")
        key = (normalize_format(converter.source_format), normalize_format(converter.target_format))
        if key in self._converters:
            raise ValueError(f"Converter already registered / 转换器已注册: {key[0]} -> {key[1]}")
        self._converters[key] = converter

    def get(self, source_format: str, target_format: str) -> BaseConverter:
        source_format = normalize_format(source_format)
        target_format = normalize_format(target_format)
        if source_format == target_format and source_format:
            return self._same_format_converter
        try:
            return self._converters[(source_format, target_format)]
        except KeyError as exc:
            raise UnsupportedConversionError(
                f"Unsupported conversion: {source_format or 'unknown'} -> {target_format or 'unknown'} / "
                "暂不支持该格式"
            ) from exc

    @property
    def supported_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._converters))


def normalize_format(value: str) -> str:
    return value.strip().lower().lstrip(".")


def _json_default(value: Any) -> str | float:
    """将表格或 YAML 中的常见特殊值转换为 JSON 可序列化值。"""

    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


converter_registry = ConverterRegistry()
for converter_type in (
    MarkdownToWordConverter,
    WordToMarkdownConverter,
    MarkdownToPDFConverter,
    ExcelToJSONConverter,
    CSVToJSONConverter,
    JSONToYAMLConverter,
    YAMLToJSONConverter,
    SRTToVTTConverter,
    TextToMarkdownConverter,
    MarkdownToTextConverter,
):
    converter_registry.register(converter_type())


def convert_file(source: Path, output_dir: Path, target_format: str) -> Path:
    """通过注册表选择转换器，并返回生成的输出文件路径。"""

    source_format = normalize_format(source.suffix)
    target_format = normalize_format(target_format)
    if not target_format or not re.fullmatch(r"[a-z0-9]{1,16}", target_format):
        raise UnsupportedConversionError("Invalid target format / 目标格式不合法")

    output_path = output_dir / f"{source.stem}.{target_format}"
    converter = converter_registry.get(source_format, target_format)
    converter.convert(source, output_path)
    return output_path


def append_failure_dataset(case: "ConversionCase", dataset_dir: Path) -> None:
    """追加一条可回放的失败样本。"""

    dataset_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "case_id": case.id,
        "original_filename": case.original_filename,
        "source_format": case.source_format,
        "target_format": case.target_format,
        "file_size": case.file_size,
        "error_message": case.error_message,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    with (dataset_dir / "conversion_failures.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
