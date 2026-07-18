from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    schema_data: dict[str, Any]
    codebook_version: str = "v0.1"


class AnnotationPayload(BaseModel):
    annotation_data: dict[str, Any]
    duration_seconds: int = Field(default=0, ge=0)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    schema_version: str
    codebook_version: str
    status: str
    created_at: datetime
    total: int = 0
    completed: int = 0

