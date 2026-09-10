from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.conversion_case import ConversionCase
from app.schemas.conversion import ConversionRead
from app.services.converter import append_failure_dataset, convert_file, normalize_format

router = APIRouter()


@router.post("", response_model=ConversionRead, status_code=status.HTTP_201_CREATED)
async def create_conversion(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    db: Session = Depends(get_db),
) -> ConversionCase:
    safe_name = Path(file.filename or "unnamed.bin").name
    case_id = str(uuid4())
    source_format = normalize_format(Path(safe_name).suffix)
    upload_dir = settings.storage_root / "uploads" / case_id
    output_dir = settings.storage_root / "outputs" / case_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    input_path = upload_dir / safe_name

    # Stream upload to disk / 分块写盘，避免大文件全部进入内存
    file_size = 0
    async with aiofiles.open(input_path, "wb") as destination:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            await destination.write(chunk)

    case = ConversionCase(
        id=case_id,
        original_filename=safe_name,
        source_format=source_format or "unknown",
        target_format=normalize_format(target_format),
        status="pending",
        input_path=str(input_path),
        file_size=file_size,
    )
    db.add(case)
    db.commit()

    try:
        output_path = convert_file(input_path, output_dir, target_format)
        case.status = "succeeded"
        case.output_path = str(output_path)
    except Exception as exc:  # Capture converter failures / 统一沉淀转换失败
        case.status = "failed"
        case.error_message = str(exc)
        append_failure_dataset(case, settings.storage_root / "datasets")

    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[ConversionRead])
def list_conversions(db: Session = Depends(get_db)) -> list[ConversionCase]:
    statement = select(ConversionCase).order_by(ConversionCase.created_at.desc()).limit(100)
    return list(db.scalars(statement))


@router.get("/{case_id}", response_model=ConversionRead)
def get_conversion(case_id: str, db: Session = Depends(get_db)) -> ConversionCase:
    case = db.get(ConversionCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Conversion not found / 转换任务不存在")
    return case


@router.get("/{case_id}/download", response_class=FileResponse)
def download_conversion(case_id: str, db: Session = Depends(get_db)) -> FileResponse:
    case = db.get(ConversionCase, case_id)
    if case is None or case.status != "succeeded" or not case.output_path:
        raise HTTPException(status_code=404, detail="Output not found / 转换结果不存在")

    output_path = Path(case.output_path)
    if not output_path.is_file():
        raise HTTPException(status_code=410, detail="Output file is gone / 转换结果文件已丢失")

    return FileResponse(output_path, filename=output_path.name)
