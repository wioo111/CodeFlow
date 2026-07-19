from typing import Any, Literal

from pydantic import BaseModel, Field


ReviewStatus = Literal["unreviewed", "in_progress", "approved", "rejected", "needs_review"]


class RecordUpdate(BaseModel):
    current_data: dict[str, Any]
    operator: str = Field(default="local_reviewer", min_length=1, max_length=120)
    review_status: ReviewStatus | None = None
    review_note: str | None = None


class ReviewUpdate(BaseModel):
    status: ReviewStatus
    operator: str = Field(default="local_reviewer", min_length=1, max_length=120)
    note: str = ""


class BulkUpdate(BaseModel):
    record_ids: list[int] = Field(min_length=1)
    field_path: str | None = None
    value: Any = None
    review_status: ReviewStatus | None = None
    operator: str = "local_reviewer"

