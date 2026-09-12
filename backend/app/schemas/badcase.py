from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BadCase(BaseModel):
    """JSONL 中单条失败案例的数据结构。"""

    model_config = ConfigDict(extra="ignore")

    case_id: str
    original_filename: str
    source_format: str
    target_format: str
    file_size: int = Field(ge=0)
    error_message: str
    error_type: str = "unknown"
    captured_at: datetime


class BadCaseListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[BadCase]


class BadCaseStats(BaseModel):
    total: int
    by_source_format: dict[str, int]
    by_target_format: dict[str, int]
    by_error_type: dict[str, int]
    by_date: dict[str, int]
