from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas.badcase import BadCase, BadCaseListResponse, BadCaseStats
from app.services.badcase_service import BadCaseService

router = APIRouter()


def get_badcase_service() -> BadCaseService:
    dataset_path = Path(settings.storage_root) / "datasets" / "conversion_failures.jsonl"
    return BadCaseService(dataset_path)


@router.get("", response_model=BadCaseListResponse)
def list_badcases(
    source_format: str | None = None,
    target_format: str | None = None,
    error_type: str | None = None,
    keyword: str | None = None,
    sort_by: Literal["captured_at", "file_size"] = "captured_at",
    order: Literal["desc", "asc"] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BadCaseListResponse:
    return get_badcase_service().list_badcases(
        source_format=source_format,
        target_format=target_format,
        error_type=error_type,
        keyword=keyword,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=BadCaseStats)
def get_badcase_stats() -> BadCaseStats:
    return get_badcase_service().get_stats()


@router.get("/{case_id}", response_model=BadCase)
def get_badcase(case_id: str) -> BadCase:
    item = get_badcase_service().get_badcase(case_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Badcase not found / 未找到该失败案例")
    return item
