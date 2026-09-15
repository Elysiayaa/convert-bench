import json
import re
import shutil
import warnings
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from app.services.file_sniffer import formats_match, sniff_file_type
from app.services.error_severity import severity_for_error_type

if TYPE_CHECKING:
    from app.models.conversion_case import ConversionCase


class ConversionError(RuntimeError):
    """转换执行失败。"""


class UnsupportedConversionError(ConversionError):
    """找不到匹配的转换器。"""


class MissingDependencyError(ConversionError):
    """转换所需的外部依赖不可用。"""


class InvalidInputError(ConversionError):
    """输入文件损坏或内容与格式不匹配。"""


class ExtensionMismatchError(InvalidInputError):
    """文件扩展名与真实内容类型不一致。"""


class UnknownFileTypeError(ConversionError):
    """空文件或无法识别真实内容类型。"""


class FileReadError(ConversionError):
    """输入文件读取失败。"""


class FileWriteError(ConversionError):
    """输出文件写入失败。"""


class ImageDecodeError(InvalidInputError):
    """图片损坏或无法由 Pillow 解码。"""


class ImageEncodeError(ConversionError):
    """图片无法编码为目标格式。"""


class ImageLossyWarning(RuntimeWarning):
    """图片转换成功，但发生了有损处理。"""


MAX_IMAGE_PIXELS = 50_000_000
HARD_MAX_IMAGE_PIXELS = 100_000_000


ErrorType = Literal[
    "unsupported_format",
    "missing_dependency",
    "invalid_input",
    "extension_mismatch",
    "converter_error",
    "file_read_error",
    "file_write_error",
    "image_decode_error",
    "image_encode_error",
    "image_lossy_warning",
    "unknown",
]


def classify_error_type(error: BaseException | str | None) -> ErrorType:
    """按照从具体到通用的顺序识别转换错误类型。"""

    if error is None:
        return "unknown"
    if isinstance(error, UnsupportedConversionError):
        return "unsupported_format"
    if isinstance(error, MissingDependencyError):
        return "missing_dependency"
    if isinstance(error, ExtensionMismatchError):
        return "extension_mismatch"
    if isinstance(error, ImageDecodeError):
        return "image_decode_error"
    if isinstance(error, ImageEncodeError):
        return "image_encode_error"
    if isinstance(error, ImageLossyWarning):
        return "image_lossy_warning"
    if isinstance(error, InvalidInputError):
        return "invalid_input"
    if isinstance(error, UnknownFileTypeError):
        return "unknown"
    if isinstance(error, FileReadError):
        return "file_read_error"
    if isinstance(error, FileWriteError):
        return "file_write_error"

    message = str(error).strip()
    if not message:
        return "unknown"

    normalized = message.casefold()
    if "image decode error" in normalized or "图片无法解码" in normalized:
        return "image_decode_error"
    if "image encode error" in normalized or "图片编码失败" in normalized:
        return "image_encode_error"
    if "image lossy warning" in normalized or "有损转换" in normalized or "只保留第一帧" in normalized:
        return "image_lossy_warning"
    if "extension mismatch" in normalized or (
        "文件扩展名是" in normalized and "真实内容是" in normalized
    ):
        return "extension_mismatch"
    if "unsupported conversion" in normalized:
        return "unsupported_format"
    if any(
        marker in normalized
        for marker in (
            "pandoc is unavailable",
            "pypandoc is not installed",
            "no pandoc was found",
            "xelatex not found",
            "xelatex is unavailable",
            "ffmpeg not found",
            "ffmpeg is unavailable",
            "missing dependency",
        )
    ):
        return "missing_dependency"
    if any(
        marker in normalized
        for marker in (
            "not a zip file",
            "invalid input",
            "invalid data found",
            "file is corrupted",
            "corrupt file",
            "does not match extension",
            "expecting value",
        )
    ):
        return "invalid_input"
    if any(
        marker in normalized
        for marker in (
            "input file does not exist",
            "failed to read input",
            "cannot read input",
            "unable to read input",
            "file read error",
        )
    ):
        return "file_read_error"
    if any(
        marker in normalized
        for marker in (
            "failed to write output",
            "cannot write output",
            "unable to write output",
            "read-only file system",
            "file write error",
        )
    ):
        return "file_write_error"
    if "empty file" in normalized or "无法识别文件真实类型" in normalized:
        return "unknown"
    return "converter_error"


class BaseConverter(ABC):
    """所有格式转换器的统一基类。"""

    source_format: str
    target_format: str

    @abstractmethod
    def convert(self, input_path: Path, output_path: Path) -> None:
        """将输入文件转换后写入指定输出路径。"""

    def _prepare(self, input_path: Path, output_path: Path) -> None:
        try:
            if not input_path.is_file():
                raise FileReadError(f"Input file does not exist / 输入文件不存在: {input_path}")
        except OSError as exc:
            raise FileReadError(f"Failed to read input / 输入文件读取失败: {exc}") from exc
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FileWriteError(f"Failed to write output / 输出目录创建失败: {exc}") from exc

    def _run_safely(self, input_path: Path, output_path: Path, action: Callable[[], None]) -> None:
        """统一清理失败时可能产生的不完整输出。"""

        self._prepare(input_path, output_path)
        try:
            action()
            if not output_path.is_file():
                raise ConversionError("Converter produced no output / 转换器未生成输出文件")
        except ConversionError:
            self._remove_partial_output(output_path)
            raise
        except Exception as exc:
            self._remove_partial_output(output_path)
            error_filename = Path(exc.filename) if isinstance(exc, OSError) and exc.filename else None
            if error_filename == input_path:
                raise FileReadError(f"Failed to read input / 输入文件读取失败: {exc}") from exc
            if error_filename in (output_path, output_path.parent):
                raise FileWriteError(f"Failed to write output / 输出文件写入失败: {exc}") from exc
            raise ConversionError(
                f"{self.source_format} -> {self.target_format} failed / 转换失败: {exc}"
            ) from exc

    @staticmethod
    def _remove_partial_output(output_path: Path) -> None:
        """尽力清理不完整输出，但不能覆盖原始转换异常。"""

        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass


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
                raise MissingDependencyError("pypandoc is not installed / 未安装 pypandoc") from exc

            try:
                pypandoc.convert_file(
                    str(input_path),
                    to=self.pandoc_target_format,
                    format=self.pandoc_source_format,
                    outputfile=str(output_path),
                    extra_args=self.extra_args,
                )
            except OSError as exc:
                raise MissingDependencyError(
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


class PillowImageConverter(BaseConverter):
    """基于 Pillow 的图片转换公共实现。"""

    pillow_target_format: str

    def _prepare_image(self, image: Any) -> Any:
        """按目标格式调整色彩模式，子类可覆盖。"""

        return image.copy()

    def convert(self, input_path: Path, output_path: Path) -> None:
        def action() -> None:
            try:
                from PIL import Image, UnidentifiedImageError
            except ImportError as exc:
                raise MissingDependencyError("Pillow is not installed / 未安装 Pillow") from exc

            dimensions: dict[str, int] | None = None
            try:
                # 这里只解析文件头；忽略 Pillow 警告后由项目自己的更严格阈值统一判断。
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                    opened_image = Image.open(input_path)
                with opened_image:
                    width, height = opened_image.size
                    total_pixels = width * height
                    dimensions = {
                        "width": width,
                        "height": height,
                        "total_pixels": total_pixels,
                    }
                    if total_pixels > HARD_MAX_IMAGE_PIXELS:
                        # 硬限制图片绝不进入像素解码阶段。
                        raise _image_size_error(width, height)
                    if total_pixels > MAX_IMAGE_PIXELS:
                        raise _image_size_error(width, height)

                    # load 会立即校验像素数据，避免损坏图片延迟到保存阶段才报错。
                    opened_image.seek(0)
                    opened_image.load()
                    image = self._prepare_image(opened_image)
            except Image.DecompressionBombError as exc:
                pixels = _pixels_from_decompression_bomb(exc)
                message = (
                    f"图片尺寸过大（{pixels} 像素），超过限制（{MAX_IMAGE_PIXELS} 像素），已拒绝转换"
                    if pixels is not None
                    else f"图片尺寸过大，超过限制（{MAX_IMAGE_PIXELS} 像素），已拒绝转换"
                )
                error = InvalidInputError(message)
                _attach_image_dimensions(error, dimensions)
                raise error from exc
            except InvalidInputError:
                raise
            except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
                error = ImageDecodeError(
                    f"Image decode error / 图片无法解码，文件可能已损坏: {exc}"
                )
                _attach_image_dimensions(error, dimensions)
                raise error from exc

            try:
                with image:
                    image.save(output_path, format=self.pillow_target_format)
            except (OSError, KeyError, TypeError, ValueError) as exc:
                error = ImageEncodeError(
                    f"Image encode error / 图片编码失败，目标格式可能不支持当前图片特性: {exc}"
                )
                _attach_image_dimensions(error, dimensions)
                raise error from exc

        self._run_safely(input_path, output_path, action)


def _image_size_error(width: int, height: int) -> InvalidInputError:
    """构造包含尺寸元数据的友好输入错误。"""

    total_pixels = width * height
    error = InvalidInputError(
        f"图片尺寸过大（{total_pixels} 像素），超过限制（{MAX_IMAGE_PIXELS} 像素），已拒绝转换"
    )
    _attach_image_dimensions(
        error,
        {"width": width, "height": height, "total_pixels": total_pixels},
    )
    return error


def _attach_image_dimensions(
    error: BaseException,
    dimensions: dict[str, int] | None,
) -> None:
    """把已知图片尺寸附加到异常，供 badcase 写入逻辑读取。"""

    if dimensions is not None:
        error.image_dimensions = dimensions  # type: ignore[attr-defined]


def _pixels_from_decompression_bomb(error: BaseException) -> int | None:
    """从 Pillow 异常文本中提取像素数，无法提取时返回空值。"""

    match = re.search(r"Image size \((\d+) pixels\)", str(error), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


class PngToJpgConverter(PillowImageConverter):
    source_format = "png"
    target_format = "jpg"
    pillow_target_format = "JPEG"

    def _prepare_image(self, image: Any) -> Any:
        # JPEG 不支持透明通道，统一叠加到白色背景上。
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            from PIL import Image

            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            background.alpha_composite(rgba)
            return background.convert("RGB")
        return image.convert("RGB")


class JpgToPngConverter(PillowImageConverter):
    source_format = "jpg"
    target_format = "png"
    pillow_target_format = "PNG"


class PngToWebpConverter(PillowImageConverter):
    source_format = "png"
    target_format = "webp"
    pillow_target_format = "WEBP"


class WebpToPngConverter(PillowImageConverter):
    source_format = "webp"
    target_format = "png"
    pillow_target_format = "PNG"


class JpgToWebpConverter(PillowImageConverter):
    source_format = "jpg"
    target_format = "webp"
    pillow_target_format = "WEBP"


class BmpToPngConverter(PillowImageConverter):
    source_format = "bmp"
    target_format = "png"
    pillow_target_format = "PNG"


class GifToPngConverter(PillowImageConverter):
    source_format = "gif"
    target_format = "png"
    pillow_target_format = "PNG"


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
    normalized = value.strip().lower().lstrip(".")
    return {"jpeg": "jpg", "jpe": "jpg"}.get(normalized, normalized)


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
    PngToJpgConverter,
    JpgToPngConverter,
    PngToWebpConverter,
    WebpToPngConverter,
    JpgToWebpConverter,
    BmpToPngConverter,
    GifToPngConverter,
):
    converter_registry.register(converter_type())


def convert_file(source: Path, output_dir: Path, target_format: str) -> Path:
    """先确认转换组合受支持，再嗅探并校验输入文件。"""

    source_format = normalize_format(source.suffix)
    target_format = normalize_format(target_format)
    if not target_format or not re.fullmatch(r"[a-z0-9]{1,16}", target_format):
        raise UnsupportedConversionError("Invalid target format / 目标格式不合法")

    # 转换能力与文件内容无关，应优先返回最根本的不支持错误。
    converter = converter_registry.get(source_format, target_format)
    try:
        if not source.is_file():
            raise FileReadError(f"Input file does not exist / 输入文件不存在: {source}")
        if source_format in {"png", "jpg", "jpeg", "gif", "bmp", "webp"} and source.stat().st_size > 50 * 1024 * 1024:
            raise InvalidInputError("Invalid input / 输入图片超过 50MB，拒绝转换")
        sniffed_format = sniff_file_type(source)
    except FileReadError:
        raise
    except OSError as exc:
        raise FileReadError(f"Failed to read input / 输入文件读取失败: {exc}") from exc

    if sniffed_format == "unknown":
        raise UnknownFileTypeError(
            "无法识别文件真实类型：文件为空或内容不可识别，请检查文件后重试"
        )
    if not formats_match(source_format, sniffed_format):
        raise ExtensionMismatchError(
            f"文件扩展名是 .{source_format or 'unknown'}，但真实内容是 {sniffed_format}，请确认文件类型"
        )

    output_path = output_dir / f"{source.stem}.{target_format}"
    converter.convert(source, output_path)
    return output_path


def get_conversion_warning(source_format: str, target_format: str) -> ImageLossyWarning | None:
    """返回成功转换需要沉淀的图片质量警告。"""

    pair = (normalize_format(source_format), normalize_format(target_format))
    if pair == ("gif", "png"):
        return ImageLossyWarning("Image lossy warning / GIF 转 PNG 只保留第一帧")
    if pair in {("png", "jpg"), ("png", "webp"), ("jpg", "webp")}:
        return ImageLossyWarning("Image lossy warning / 图片经过有损转换，质量可能下降")
    return None


def append_failure_dataset(
    case: "ConversionCase",
    dataset_dir: Path,
    error: BaseException | str | None = None,
    message: str | None = None,
) -> None:
    """追加一条可回放的失败或警告样本。"""

    dataset_dir.mkdir(parents=True, exist_ok=True)
    error_type = classify_error_type(error if error is not None else case.error_message)
    record = {
        "case_id": case.id,
        "original_filename": case.original_filename,
        "source_format": case.source_format,
        "target_format": case.target_format,
        "file_size": case.file_size,
        "error_message": message if message is not None else case.error_message,
        "error_type": error_type,
        "severity": severity_for_error_type(error_type),
        "image_dimensions": getattr(error, "image_dimensions", None),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    with (dataset_dir / "conversion_failures.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
