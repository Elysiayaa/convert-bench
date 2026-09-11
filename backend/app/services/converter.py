import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.models.conversion_case import ConversionCase


class UnsupportedConversionError(ValueError):
    """Raised when no converter is registered / 没有匹配转换器时抛出。"""


def normalize_format(value: str) -> str:
    return value.strip().lower().lstrip(".")


def convert_file(source: Path, output_dir: Path, target_format: str) -> Path:
    source_format = normalize_format(source.suffix)
    target_format = normalize_format(target_format)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.{target_format}"

    if not target_format or not re.fullmatch(r"[a-z0-9]{1,16}", target_format):
        raise UnsupportedConversionError("Invalid target format / 目标格式不合法")

    if source_format == target_format:
        shutil.copy2(source, output)
    elif (source_format, target_format) == ("txt", "md"):
        text = source.read_text(encoding="utf-8")
        output.write_text(f"# {source.stem}\n\n{text}\n", encoding="utf-8")
    elif (source_format, target_format) == ("md", "txt"):
        text = source.read_text(encoding="utf-8")
        # Minimal Markdown stripping / MVP 阶段仅移除常见标记
        plain = re.sub(r"[`*_>#-]", "", text)
        output.write_text(plain, encoding="utf-8")
    else:
        raise UnsupportedConversionError(
            f"Unsupported conversion: {source_format or 'unknown'} -> {target_format} / 暂不支持该格式"
        )

    return output


def append_failure_dataset(case: ConversionCase, dataset_dir: Path) -> None:
    """Append one replayable failure record / 追加一条可回放的失败样本。"""

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

