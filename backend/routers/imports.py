from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Batch, Project, Record
from backend.services.import_service import parse_config, parse_json_data
from backend.services.schema_parser import validate_schema_config
from backend.services.schema_validator import validate_record


router = APIRouter(prefix="/imports", tags=["imports"])


def default_view(schema: dict) -> dict:
    keys = [field["key"] for field in schema["fields"]]
    return {
        "default_view": "table",
        "table": {"columns": keys[:6] + ["_review.status"]},
        "form": {"sections": [{"title": "记录字段", "fields": keys}]},
    }


@router.post("", status_code=201)
async def import_project(
    project_name: str = Form(...),
    batch_name: str = Form("首批数据"),
    data_version: str = Form("v1"),
    description: str = Form(""),
    schema_file: UploadFile = File(...),
    data_file: UploadFile = File(...),
    view_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    schema = parse_config(await schema_file.read(), "Schema")
    validate_schema_config(schema)
    view = parse_config(await view_file.read(), "View 配置") if view_file else default_view(schema)
    rows = parse_json_data(await data_file.read(), data_file.filename or "data.jsonl")
    primary_key = schema["primary_key"]
    keys: set[str] = set()
    for index, row in enumerate(rows, 1):
        if primary_key not in row or row[primary_key] in (None, ""):
            from fastapi import HTTPException
            raise HTTPException(422, f"第 {index} 条记录缺少主键 {primary_key}")
        key = str(row[primary_key])
        if key in keys:
            from fastapi import HTTPException
            raise HTTPException(422, f"主键重复：{key}")
        keys.add(key)
    project = Project(
        name=project_name, description=description, schema_id=schema["schema_id"],
        schema_version=str(schema["version"]), schema_data=schema, view_config=view,
    )
    db.add(project); db.flush()
    batch = Batch(
        project_id=project.id, name=batch_name, data_version=data_version,
        source_filename=data_file.filename or "data.jsonl", record_count=len(rows),
    )
    db.add(batch); db.flush()
    invalid = 0
    for row in rows:
        errors = validate_record(schema, row)
        invalid += bool(errors)
        db.add(Record(
            batch_id=batch.id, record_key=str(row[primary_key]), original_data=row, current_data=row,
            validation_status="invalid" if errors else "valid", validation_errors=errors,
        ))
    db.commit()
    return {"project_id": project.id, "batch_id": batch.id, "record_count": len(rows), "invalid_count": invalid}

