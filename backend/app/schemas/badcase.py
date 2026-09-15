from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services.error_severity import Severity


class ImageDimensions(BaseModel):
    """发生图片转换问题时记录的像素尺寸。"""

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    total_pixels: int = Field(gt=0)


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
    severity: Severity = "error"
    image_dimensions: ImageDimensions | None = None
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
    by_severity: dict[str, int]
    by_date: dict[str, int]
