import json
import csv
from io import StringIO
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.schemas.badcase import BadCase, BadCaseListResponse, BadCaseStats
from app.schemas.dataset import DatasetStats

SortField = Literal["captured_at", "file_size"]
SortOrder = Literal["asc", "desc"]


class BadCaseService:
    """从 JSONL 文件读取、筛选和统计失败案例。"""

    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path

    def read_all(self) -> list[BadCase]:
        if not self.dataset_path.is_file():
            return []

        items: list[BadCase] = []
        try:
            with self.dataset_path.open("r", encoding="utf-8") as dataset:
                for line in dataset:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                        if not isinstance(payload, dict):
                            continue
                        payload.setdefault("error_type", "unknown")
                        items.append(BadCase.model_validate(payload))
                    except (json.JSONDecodeError, ValidationError, TypeError):
                        # 单行损坏不能影响其他有效记录。
                        continue
        except (OSError, UnicodeError):
            # 文件暂时不可读时返回空集合，保持浏览接口可用。
            return []
        return items

    def list_badcases(
        self,
        *,
        source_format: str | None = None,
        target_format: str | None = None,
        error_type: str | None = None,
        keyword: str | None = None,
        sort_by: SortField = "captured_at",
        order: SortOrder = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> BadCaseListResponse:
        items = self.filter_badcases(
            source_format=source_format,
            target_format=target_format,
            error_type=error_type,
        )
        if keyword:
            expected = keyword.strip().casefold()
            if expected:
                items = [
                    item
                    for item in items
                    if expected in item.original_filename.casefold()
                    or expected in item.error_message.casefold()
                ]

        items.sort(key=lambda item: getattr(item, sort_by), reverse=order == "desc")
        total = len(items)
        start = (page - 1) * page_size
        return BadCaseListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items[start : start + page_size],
        )

    def filter_badcases(
        self,
        *,
        source_format: str | None = None,
        target_format: str | None = None,
        error_type: str | None = None,
    ) -> list[BadCase]:
        """按导出与浏览接口共用的格式条件筛选记录。"""

        items = self.read_all()
        if source_format:
            expected = source_format.strip().lower().lstrip(".")
            items = [item for item in items if item.source_format.lower() == expected]
        if target_format:
            expected = target_format.strip().lower().lstrip(".")
            items = [item for item in items if item.target_format.lower() == expected]
        if error_type:
            expected = error_type.strip().lower()
            items = [item for item in items if item.error_type.lower() == expected]
        return items

    def get_badcase(self, case_id: str) -> BadCase | None:
        return next((item for item in self.read_all() if item.case_id == case_id), None)

    def get_stats(self) -> BadCaseStats:
        items = self.read_all()
        return BadCaseStats(
            total=len(items),
            by_source_format=self._sorted_counts(item.source_format for item in items),
            by_target_format=self._sorted_counts(item.target_format for item in items),
            by_error_type=self._sorted_counts(item.error_type for item in items),
            by_date=self._sorted_counts(item.captured_at.date().isoformat() for item in items),
        )

    def get_dataset_stats(self) -> DatasetStats:
        """返回完整数据集统计和按时间倒序的最新十条记录。"""

        items = self.read_all()
        latest = sorted(items, key=lambda item: item.captured_at, reverse=True)[:10]
        return DatasetStats(
            total=len(items),
            by_source_format=self._sorted_counts(item.source_format for item in items),
            by_target_format=self._sorted_counts(item.target_format for item in items),
            by_error_type=self._sorted_counts(item.error_type for item in items),
            by_date=self._sorted_counts(item.captured_at.date().isoformat() for item in items),
            latest_badcases=latest,
        )

    def export_dataset(
        self,
        export_format: Literal["json", "csv", "jsonl"],
        *,
        source_format: str | None = None,
        target_format: str | None = None,
        error_type: str | None = None,
    ) -> bytes:
        """将筛选后的记录序列化为指定下载格式。"""

        items = self.filter_badcases(
            source_format=source_format,
            target_format=target_format,
            error_type=error_type,
        )
        items.sort(key=lambda item: item.captured_at, reverse=True)
        records = [item.model_dump(mode="json") for item in items]

        if export_format == "json":
            return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")
        if export_format == "jsonl":
            content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
            return (content + ("\n" if content else "")).encode("utf-8")

        fieldnames = [
            "case_id",
            "original_filename",
            "source_format",
            "target_format",
            "file_size",
            "error_message",
            "error_type",
            "captured_at",
        ]
        output = StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        # 写入 UTF-8 BOM，方便 Excel 正确识别中文。
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    @staticmethod
    def _sorted_counts(values: Iterable[str]) -> dict[str, int]:
        counts = Counter(values)
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
