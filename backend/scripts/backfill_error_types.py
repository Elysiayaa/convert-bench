"""为历史 badcase 就地回填 error_type。"""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.error_severity import severity_for_error_type


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = BACKEND_ROOT / "storage" / "datasets" / "conversion_failures.jsonl"


@dataclass(frozen=True)
class BackfillStats:
    """一次回填任务的统计结果。"""

    total: int
    before_by_error_type: dict[str, int]
    after_by_error_type: dict[str, int]
    backfilled: int
    severity_backfilled: int
    unknown: int
    invalid_lines: int


def infer_error_type(error_message: str, current_error_type: str | None = None) -> str:
    """严格按照指定优先级从错误信息中推断类型。"""

    message = error_message.casefold()
    if "image decode error" in message or "图片无法解码" in message:
        return "image_decode_error"
    if "image encode error" in message or "图片编码失败" in message:
        return "image_encode_error"
    if "image lossy warning" in message or "有损转换" in message or "只保留第一帧" in message:
        return "image_lossy_warning"
    if "unsupported conversion" in message:
        return "unsupported_format"
    if "pandoc is unavailable" in message:
        return "missing_dependency"
    if "not a zip file" in message:
        return "invalid_input"
    if "文件扩展名是" in message and "真实内容是" in message:
        return "extension_mismatch"
    return _normalized_error_type(current_error_type)


def backfill_error_types(file_path: Path, *, dry_run: bool = False) -> BackfillStats:
    """处理 JSONL；非 dry-run 时先写临时文件，再原子替换源文件。"""

    before_counts: Counter[str] = Counter()
    after_counts: Counter[str] = Counter()
    output_lines: list[str] = []
    total = 0
    backfilled = 0
    severity_backfilled = 0
    invalid_lines = 0

    with file_path.open("r", encoding="utf-8", newline="") as source:
        for raw_line in source:
            stripped_line = raw_line.rstrip("\r\n")
            line_ending = raw_line[len(stripped_line) :]
            if not stripped_line.strip():
                output_lines.append(raw_line)
                continue

            try:
                payload = json.loads(stripped_line)
            except json.JSONDecodeError:
                output_lines.append(raw_line)
                invalid_lines += 1
                continue
            if not isinstance(payload, dict):
                output_lines.append(raw_line)
                invalid_lines += 1
                continue

            total += 1
            original_value = payload.get("error_type")
            original_type = _normalized_error_type(original_value)
            before_counts[original_type] += 1
            final_type = original_type

            # 已有明确分类属于历史事实，不能被错误消息规则覆盖。
            if original_type == "unknown":
                final_type = infer_error_type(
                    str(payload.get("error_message", "")),
                    original_type,
                )
                if original_value != final_type:
                    # Python 字典保持插入顺序：已有字段位置不变，新字段追加到末尾。
                    payload["error_type"] = final_type
                    backfilled += 1

            expected_severity = severity_for_error_type(final_type)
            if payload.get("severity") != expected_severity:
                # severity 始终由最终 error_type 推导，修正缺失值和历史错误值。
                payload["severity"] = expected_severity
                severity_backfilled += 1

            after_counts[final_type] += 1
            output_lines.append(json.dumps(payload, ensure_ascii=False) + line_ending)

    stats = BackfillStats(
        total=total,
        before_by_error_type=_sorted_counts(before_counts),
        after_by_error_type=_sorted_counts(after_counts),
        backfilled=backfilled,
        severity_backfilled=severity_backfilled,
        unknown=after_counts["unknown"],
        invalid_lines=invalid_lines,
    )
    if dry_run:
        return stats

    # 唯一名称可避免并发执行或历史残留临时文件相互冲突。
    temporary_path = file_path.with_name(f".{file_path.name}.{uuid4().hex}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="") as destination:
            destination.writelines(output_lines)
        temporary_path.replace(file_path)
    except Exception:
        # 更新失败时清理临时文件，原始 JSONL 保持不变。
        temporary_path.unlink(missing_ok=True)
        raise
    return stats


def _normalized_error_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    normalized = value.strip()
    return "unknown" if normalized.casefold() == "unknown" else normalized


def _sorted_counts(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def print_stats(stats: BackfillStats, *, dry_run: bool) -> None:
    """以稳定、便于人工核对的格式打印统计。"""

    print("运行模式：dry-run（未修改文件）" if dry_run else "运行模式：正式回填")
    print(f"共处理：{stats.total} 条")
    print("回填前：")
    for error_type, count in stats.before_by_error_type.items():
        print(f"  {error_type}: {count}")
    print("回填后：")
    for error_type, count in stats.after_by_error_type.items():
        print(f"  {error_type}: {count}")
    print(f"被回填：{stats.backfilled} 条")
    print(f"severity 被回填：{stats.severity_backfilled} 条")
    print(f"仍为 unknown：{stats.unknown} 条")
    if stats.invalid_lines:
        print(f"跳过无效 JSONL：{stats.invalid_lines} 行")


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 ConvertBench badcase 错误类型")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出预计结果，不修改文件",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="JSONL 文件路径，默认使用项目历史 badcase 数据集",
    )
    arguments = parser.parse_args()
    stats = backfill_error_types(arguments.file, dry_run=arguments.dry_run)
    print_stats(stats, dry_run=arguments.dry_run)


if __name__ == "__main__":
    main()
