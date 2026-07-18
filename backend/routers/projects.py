from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Assignment, Project
from backend.schemas import ProjectCreate
from backend.services.schema_validator import validate_schema


router = APIRouter(prefix="/projects", tags=["projects"])


def project_view(project: Project, db: Session) -> dict:
    total, completed = db.execute(
        select(func.count(Assignment.id), func.count(Assignment.submitted_at)).where(Assignment.project_id == project.id)
    ).one()
    return {
        "id": project.id, "name": project.name, "description": project.description,
        "schema_version": project.schema_version, "codebook_version": project.codebook_version,
        "status": project.status, "created_at": project.created_at, "total": total, "completed": completed,
    }


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    return [project_view(project, db) for project in db.scalars(select(Project).order_by(Project.id))]


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    validate_schema(payload.schema_data)
    project = Project(
        name=payload.name, description=payload.description, schema_data=payload.schema_data,
        schema_version=payload.schema_data["version"], codebook_version=payload.codebook_version,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_view(project, db)


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project_view(project, db)


@router.get("/{project_id}/schema")
def get_schema(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project.schema_data

