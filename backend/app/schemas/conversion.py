from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    source_format: str
    target_format: str
    status: str
    file_size: int
    output_path: str | None
    error_message: str | None
    created_at: datetime

