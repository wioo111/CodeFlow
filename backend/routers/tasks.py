from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Assignment, Annotation


router = APIRouter(prefix="/tasks", tags=["tasks"])


def task_view(task: Assignment) -> dict:
    return {
        "id": task.id, "project_id": task.project_id, "stage": task.stage, "status": task.status,
        "assigned_at": task.assigned_at, "submitted_at": task.submitted_at, "duration_seconds": task.duration_seconds,
        "coder": {"id": task.coder.id, "name": task.coder.name},
        "material": {
            "id": task.material.id, "material_type": task.material.material_type,
            "material_data": task.material.material_data, "metadata": task.material.metadata_data,
        },
        "annotation": None if not task.annotation else {
            "annotation_data": task.annotation.annotation_data,
            "is_submitted": task.annotation.is_submitted,
            "schema_version": task.annotation.schema_version,
            "codebook_version": task.annotation.codebook_version,
            "updated_at": task.annotation.updated_at,
        },
    }


def task_query():
    return select(Assignment).options(
        joinedload(Assignment.material), joinedload(Assignment.coder), joinedload(Assignment.annotation)
    )


@router.get("")
def list_tasks(project_id: int = 1, coder_id: int = 1, db: Session = Depends(get_db)):
    tasks = db.scalars(task_query().where(
        Assignment.project_id == project_id, Assignment.coder_id == coder_id
    ).order_by(Assignment.id)).unique()
    return [task_view(task) for task in tasks]


@router.get("/next")
def next_task(project_id: int = 1, coder_id: int = 1, after_id: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = task_query().where(
        Assignment.project_id == project_id, Assignment.coder_id == coder_id,
        Assignment.status != "submitted", Assignment.id > after_id,
    ).order_by(Assignment.id).limit(1)
    task = db.scalars(query).unique().first()
    if not task and after_id:
        task = db.scalars(task_query().where(
            Assignment.project_id == project_id, Assignment.coder_id == coder_id,
            Assignment.status != "submitted",
        ).order_by(Assignment.id).limit(1)).unique().first()
    return task_view(task) if task else None


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.scalars(task_query().where(Assignment.id == task_id)).unique().first()
    if not task:
        raise HTTPException(404, "任务不存在")
    return task_view(task)

