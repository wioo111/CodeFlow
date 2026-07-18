from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Assignment


router = APIRouter(prefix="/results", tags=["results"])


@router.get("")
def list_results(project_id: int = 1, status: str | None = None, db: Session = Depends(get_db)):
    query = select(Assignment).options(
        joinedload(Assignment.material), joinedload(Assignment.coder), joinedload(Assignment.annotation)
    ).where(Assignment.project_id == project_id)
    if status:
        query = query.where(Assignment.status == status)
    assignments = db.scalars(query.order_by(Assignment.id)).unique()
    return [{
        "assignment_id": item.id,
        "sample_number": item.material.material_data.get("sample_number", str(item.material.id)),
        "coder": item.coder.name, "stage": item.stage, "status": item.status,
        "submitted_at": item.submitted_at, "duration_seconds": item.duration_seconds,
        "schema_version": item.annotation.schema_version if item.annotation else None,
        "codebook_version": item.annotation.codebook_version if item.annotation else None,
        "annotation_data": item.annotation.annotation_data if item.annotation else {},
    } for item in assignments]

