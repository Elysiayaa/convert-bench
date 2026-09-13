from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.core.config import settings
from app.schemas.dataset import DatasetStats
from app.services.badcase_service import BadCaseService

router = APIRouter()


def get_badcase_service() -> BadCaseService:
    dataset_path = Path(settings.storage_root) / "datasets" / "conversion_failures.jsonl"
    return BadCaseService(dataset_path)


@router.get("/export")
def export_dataset(
    export_format: Annotated[
        Literal["json", "csv", "jsonl"],
        Query(alias="format"),
    ] = "jsonl",
    source_format: str | None = None,
    target_format: str | None = None,
    error_type: str | None = None,
) -> Response:
    content = get_badcase_service().export_dataset(
        export_format,
        source_format=source_format,
        target_format=target_format,
        error_type=error_type,
    )
    media_types = {
        "json": "application/json; charset=utf-8",
        "csv": "text/csv; charset=utf-8",
        "jsonl": "application/x-ndjson; charset=utf-8",
    }
    filename = f"convertbench_dataset_{datetime.now().strftime('%Y%m%d')}.{export_format}"
    return Response(
        content=content,
        media_type=media_types[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/stats", response_model=DatasetStats)
def get_dataset_stats() -> DatasetStats:
    return get_badcase_service().get_dataset_stats()
