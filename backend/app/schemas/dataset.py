from pydantic import BaseModel

from app.schemas.badcase import BadCase


class DatasetStats(BaseModel):
    """数据集概览及最新失败案例。"""

    total: int
    by_source_format: dict[str, int]
    by_target_format: dict[str, int]
    by_error_type: dict[str, int]
    by_severity: dict[str, int]
    by_date: dict[str, int]
    latest_badcases: list[BadCase]
