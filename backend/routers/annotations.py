from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Annotation, Assignment, Project
from backend.schemas import AnnotationPayload
from backend.services.schema_validator import validate_annotation


router = APIRouter(prefix="/annotations", tags=["annotations"])


def get_context(assignment_id: int, db: Session):
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "任务不存在")
    project = db.get(Project, assignment.project_id)
    return assignment, project


@router.put("/{assignment_id}/draft")
def save_draft(assignment_id: int, payload: AnnotationPayload, db: Session = Depends(get_db)):
    assignment, project = get_context(assignment_id, db)
    if assignment.status == "submitted":
        raise HTTPException(409, "已提交结果已锁定，不能覆盖")
    annotation = assignment.annotation or Annotation(
        assignment_id=assignment.id, schema_version=project.schema_version,
        codebook_version=project.codebook_version,
    )
    annotation.annotation_data = payload.annotation_data
    annotation.updated_at = datetime.now(timezone.utc)
    assignment.status = "draft"
    assignment.duration_seconds = max(assignment.duration_seconds, payload.duration_seconds)
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return {"status": "saved", "updated_at": annotation.updated_at}


@router.post("/{assignment_id}/submit")
def submit_annotation(assignment_id: int, payload: AnnotationPayload, db: Session = Depends(get_db)):
    assignment, project = get_context(assignment_id, db)
    if assignment.status == "submitted":
        raise HTTPException(409, "已提交结果已锁定，不能覆盖")
    normalized = validate_annotation(project.schema_data, payload.annotation_data)
    now = datetime.now(timezone.utc)
    annotation = assignment.annotation or Annotation(
        assignment_id=assignment.id, schema_version=project.schema_version,
        codebook_version=project.codebook_version,
    )
    annotation.annotation_data = normalized
    annotation.schema_version = project.schema_version
    annotation.codebook_version = project.codebook_version
    annotation.is_submitted = True
    annotation.updated_at = now
    assignment.status = "submitted"
    assignment.submitted_at = now
    assignment.duration_seconds = max(assignment.duration_seconds, payload.duration_seconds)
    db.add(annotation)
    db.commit()
    return {"status": "submitted", "submitted_at": now}

