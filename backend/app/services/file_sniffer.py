import csv
import json
import re
import zipfile
from io import StringIO
from pathlib import Path
from typing import Literal


SniffedFileType = Literal[
    "xlsx",
    "docx",
    "zip",
    "pdf",
    "png",
    "jpg",
    "gif",
    "bmp",
    "webp",
    "json",
    "yaml",
    "csv",
    "markdown",
    "srt",
    "text",
    "unknown",
]

_MIME_TYPE_MAP: dict[str, SniffedFileType] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/x-ms-bmp": "bmp",
    "image/webp": "webp",
    "application/json": "json",
    "application/ld+json": "json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/x-yaml": "yaml",
    "text/csv": "csv",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "text/vtt": "text",
    "text/yaml": "yaml",
}

_DECLARED_TYPE_ALIASES = {
    "jpeg": "jpg",
    "jpe": "jpg",
    "md": "markdown",
    "markdown": "markdown",
    "txt": "text",
    "text": "text",
    "yml": "yaml",
    "yaml": "yaml",
}

_TEXT_FILE_TYPES = {"csv", "json", "markdown", "srt", "text", "yaml"}


def sniff_file_type(file_path: str | Path) -> SniffedFileType:
    """识别文件真实类型，python-magic 不可用时自动使用内置规则。"""

    path = Path(file_path)
    if path.stat().st_size == 0:
        return "unknown"

    magic_result = _sniff_with_python_magic(path)
    if magic_result is not None:
        return magic_result

    prefix = _read_prefix(path)
    # 图片格式使用稳定的文件签名识别，不依赖文件扩展名。
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if prefix.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if prefix.startswith(b"BM"):
        return "bmp"
    if len(prefix) >= 12 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
        return "webp"
    if prefix.startswith(b"%PDF"):
        return "pdf"
    if prefix.startswith(b"PK\x03\x04"):
        return _sniff_zip_type(path)

    text = _decode_text(path.read_bytes())
    if text is None or not text.strip():
        return "unknown"
    return _sniff_text_type(text)


def formats_match(declared_format: str, sniffed_format: SniffedFileType) -> bool:
    """比较扩展名与嗅探结果，并兼容常见别名和无法细分的纯文本。"""

    declared = declared_format.strip().lower().lstrip(".")
    normalized_declared = _DECLARED_TYPE_ALIASES.get(declared, declared)
    if normalized_declared == sniffed_format:
        return True

    # 没有明显结构的纯文本可能是合法的单行 Markdown、YAML 或 CSV。
    if sniffed_format == "text" and normalized_declared in _TEXT_FILE_TYPES:
        return True
    return False


def _sniff_with_python_magic(path: Path) -> SniffedFileType | None:
    """优先使用 libmagic；模块、动态库或识别过程异常时返回 None。"""

    try:
        import magic
    except (ImportError, OSError):
        return None

    try:
        mime_type = str(magic.from_file(str(path), mime=True)).split(";", 1)[0].strip().lower()
    except Exception:  # python-magic 的平台异常不能阻断内置嗅探。
        return None

    direct_match = _MIME_TYPE_MAP.get(mime_type)
    if direct_match is not None:
        return direct_match
    if mime_type in ("application/zip", "application/x-zip", "application/x-zip-compressed"):
        return _sniff_zip_type(path)
    if mime_type.startswith("text/"):
        text = _decode_text(path.read_bytes())
        return _sniff_text_type(text) if text and text.strip() else "unknown"
    return None


def _read_prefix(path: Path, size: int = 8192) -> bytes:
    with path.open("rb") as source:
        return source.read(size)


def _sniff_zip_type(path: Path) -> SniffedFileType:
    """根据 Open XML 压缩包中的目录判断 Office 文档类型。"""

    try:
        with zipfile.ZipFile(path) as archive:
            names = {name.replace("\\", "/").lower() for name in archive.namelist()}
    except (OSError, zipfile.BadZipFile):
        return "zip"

    if any(name.startswith("xl/") for name in names):
        return "xlsx"
    if any(name.startswith("word/") for name in names):
        return "docx"
    return "zip"


def _decode_text(content: bytes) -> str | None:
    """解码常见 Unicode 文本，并拒绝带大量二进制控制字符的内容。"""

    encodings = ["utf-8-sig"]
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings.insert(0, "utf-16")

    for encoding in encodings:
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        control_count = sum(ord(character) < 32 and character not in "\n\r\t" for character in text)
        if control_count > max(1, len(text) // 100):
            return None
        return text
    return None


def _sniff_text_type(text: str) -> SniffedFileType:
    stripped = text.strip()

    try:
        json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        pass
    else:
        return "json"

    if re.search(
        r"(?m)^\s*\d+\s*\r?\n\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+"
        r"\d{1,2}:\d{2}:\d{2}[,.]\d{3}",
        stripped,
    ):
        return "srt"

    if _looks_like_csv(stripped):
        return "csv"
    if _looks_like_yaml(stripped):
        return "yaml"
    if _looks_like_markdown(stripped):
        return "markdown"
    return "text"


def _looks_like_markdown(text: str) -> bool:
    strong_line = re.search(
        r"(?m)^\s{0,3}(?:#{1,6}\s+|```|~~~|>\s+|[-*+]\s+|\d+[.)]\s+)",
        text,
    )
    inline_markup = re.search(r"!?\[[^\]\n]+\]\([^\)\n]+\)|\*\*[^*\n]+\*\*|`[^`\n]+`", text)
    markdown_table = re.search(r"(?m)^\s*\|?.+\|.+\r?\n\s*\|?\s*:?-{3,}", text)
    return any((strong_line, inline_markup, markdown_table))


def _looks_like_csv(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    sample = "\n".join(lines[:20])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        rows = list(csv.reader(StringIO(sample), dialect=dialect))
    except csv.Error:
        return False

    widths = [len(row) for row in rows if row]
    return bool(widths) and min(widths) > 1 and len(set(widths)) == 1


def _looks_like_yaml(text: str) -> bool:
    try:
        import yaml
    except ImportError:
        return False

    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError:
        return False

    if text.lstrip().startswith("---") and payload is not None:
        return True
    return isinstance(payload, dict)
