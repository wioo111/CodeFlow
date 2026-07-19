from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Batch, DatasetVersion, Project, Record


router = APIRouter(prefix="/projects", tags=["projects"])


def project_summary(project: Project, db: Session) -> dict:
    total, invalid, approved, needs_review = db.execute(
        select(
            func.count(Record.id),
            func.count(Record.id).filter(Record.validation_status == "invalid"),
            func.count(Record.id).filter(Record.review_status == "approved"),
            func.count(Record.id).filter(Record.review_status == "needs_review"),
        ).join(Batch, Record.batch_id == Batch.id, isouter=True).where(Batch.project_id == project.id)
    ).one()
    latest_batch = db.scalar(select(Batch).where(Batch.project_id == project.id).order_by(Batch.id.desc()).limit(1))
    latest_dataset = db.scalar(select(DatasetVersion).where(DatasetVersion.project_id == project.id).order_by(DatasetVersion.id.desc()).limit(1))
    return {
        "id": project.id, "name": project.name, "description": project.description,
        "schema_id": project.schema_id, "schema_version": project.schema_version,
        "created_at": project.created_at, "updated_at": project.updated_at,
        "record_count": total or 0, "invalid_count": invalid or 0, "approved_count": approved or 0,
        "needs_review_count": needs_review or 0, "latest_batch_id": latest_batch.id if latest_batch else None,
        "latest_batch_name": latest_batch.name if latest_batch else None,
        "latest_dataset_version_id": latest_dataset.id if latest_dataset else None,
        "latest_dataset_version": latest_dataset.dataset_version if latest_dataset else None,
        "research_sample_count": latest_dataset.sample_count if latest_dataset else 0,
    }


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    return [project_summary(project, db) for project in db.scalars(select(Project).order_by(Project.updated_at.desc()))]


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: raise HTTPException(404, "项目不存在")
    result = project_summary(project, db)
    result["batches"] = [{
        "id": batch.id, "name": batch.name, "data_version": batch.data_version,
        "source_filename": batch.source_filename, "record_count": batch.record_count, "created_at": batch.created_at,
    } for batch in db.scalars(select(Batch).where(Batch.project_id == project_id).order_by(Batch.id.desc()))]
    return result


@router.get("/{project_id}/schema")
def get_schema(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: raise HTTPException(404, "项目不存在")
    return project.schema_data


@router.get("/{project_id}/view")
def get_view(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: raise HTTPException(404, "项目不存在")
    return project.view_config
