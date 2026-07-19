from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnnotationAssignment, DataRecord, DataTable, DatasetVersion, HumanAnnotation, Project
from backend.services.package_service import ParsedPackage, parse_dataset_package


router = APIRouter(prefix="/dataset-packages", tags=["dataset packages"])


def _custom_schema(parsed: ParsedPackage) -> dict[str, Any]:
    schema = parsed.schemas.get("__annotation_schema__") or parsed.schemas.get("__review_schema__")
    if schema and "fields" in schema:
        return schema
    if schema and schema.get("type") == "object":
        required = set(schema.get("required", []))
        fields = []
        for key, definition in schema.get("properties", {}).items():
            field_type = definition.get("x-codeflow-type") or definition.get("type", "string")
            if field_type == "array":
                field_type = "multi_enum" if definition.get("items", {}).get("enum") else "string_array"
            if field_type == "string" and definition.get("enum"):
                field_type = "enum"
            field = {"key": key, "label": definition.get("title", key), "type": field_type, "required": key in required}
            if definition.get("enum"):
                field["options"] = [{"value": value, "label": str(value)} for value in definition["enum"]]
            if definition.get("items", {}).get("enum"):
                field["options"] = [{"value": value, "label": str(value)} for value in definition["items"]["enum"]]
            for source, target in (("minimum", "min"), ("maximum", "max"), ("description", "description")):
                if source in definition:
                    field[target] = definition[source]
            fields.append(field)
        return {
            "schema_id": schema.get("$id", f"{parsed.manifest.get('project_id')}.annotation"),
            "version": str(parsed.manifest.get("versions", {}).get("annotation_schema_version", "v1")),
            "primary_key": parsed.manifest.get("primary_key", "sample_id"), "fields": fields,
        }
    return {
        "schema_id": f"{parsed.manifest.get('project_id')}.annotation", "version": "v1",
        "primary_key": parsed.manifest.get("primary_key", "sample_id"),
        "fields": [{"key": "notes", "label": "标注说明", "type": "long_text"},
                   {"key": "evidence_span", "label": "主要证据区间", "type": "time_span"}],
    }


def _default_view(schema: dict[str, Any], parsed: ParsedPackage) -> dict[str, Any]:
    if parsed.view:
        return parsed.view
    keys = [field["key"] for field in schema.get("fields", [])]
    return {
        "workspace": {"left": "queue", "center": ["video", "frames"], "right": ["ai", "form", "codebook"], "drawer": ["comments", "metadata", "changes"]},
        "table": {"columns": keys[:6]}, "form": {"sections": [{"title": "人工标注", "fields": keys}]},
    }


@router.post("/preflight")
async def preflight_package(
    package_file: UploadFile = File(...), media_root: str | None = Form(None), db: Session = Depends(get_db),
):
    parsed = parse_dataset_package(await package_file.read(), package_file.filename or "dataset.zip", media_root)
    project = db.scalar(select(Project).where(Project.schema_id == str(parsed.manifest.get("project_id"))))
    duplicate = False
    if project:
        duplicate = db.scalar(select(DatasetVersion.id).where(
            DatasetVersion.project_id == project.id,
            DatasetVersion.dataset_version == parsed.dataset_version,
            DatasetVersion.package_digest == parsed.digest,
        )) is not None
    return {**parsed.report, "duplicate": duplicate, "source_filename": package_file.filename}


@router.post("/import", status_code=201)
async def import_package(
    package_file: UploadFile = File(...), media_root: str | None = Form(None), db: Session = Depends(get_db),
):
    parsed = parse_dataset_package(await package_file.read(), package_file.filename or "dataset.zip", media_root)
    if not parsed.report["valid"]:
        raise HTTPException(422, {"message": "数据包预检失败，未写入任何数据", "report": parsed.report})
    external_id = str(parsed.manifest["project_id"])
    project = db.scalar(select(Project).where(Project.schema_id == external_id))
    annotation_schema = _custom_schema(parsed)
    if not project:
        project = Project(
            name=str(parsed.manifest["name"]), description=str(parsed.manifest.get("description", "")),
            schema_id=external_id, schema_version=str(annotation_schema.get("version", "v1")),
            schema_data=annotation_schema, view_config=_default_view(annotation_schema, parsed),
        )
        db.add(project); db.flush()
    existing = db.scalar(select(DatasetVersion).where(
        DatasetVersion.project_id == project.id, DatasetVersion.dataset_version == parsed.dataset_version,
        DatasetVersion.package_digest == parsed.digest,
    ))
    if existing:
        return JSONResponse(status_code=200, content={
            "status": "already_exists", "project_id": project.id, "dataset_version_id": existing.id,
            "dataset_version": existing.dataset_version, "digest": existing.package_digest,
        })
    versions = copy.deepcopy(parsed.manifest.get("versions", {}))
    versions.setdefault("dataset_version", parsed.dataset_version)
    versions.setdefault("sample_schema_version", "v1")
    versions.setdefault("annotation_schema_version", str(annotation_schema.get("version", "v1")))
    versions.setdefault("view_version", str(parsed.view.get("version", "v1")))
    versions.setdefault("codebook_version", str(parsed.codebook.get("version", "v1")))
    versions.setdefault("prompt_version", "not_applicable")
    stored_schemas = copy.deepcopy(parsed.schemas)
    stored_schemas["__resolved_annotation_schema__"] = copy.deepcopy(annotation_schema)
    dataset = DatasetVersion(
        project_id=project.id, external_project_id=external_id, dataset_version=parsed.dataset_version,
        package_digest=parsed.digest, source_filename=package_file.filename or "dataset.zip",
        project_config=parsed.manifest, schemas=stored_schemas, view_config=parsed.view,
        codebook=parsed.codebook, versions=versions,
        media_root=str(__import__("pathlib").Path(media_root).expanduser().resolve()) if media_root else None,
        validation_report=parsed.report, sample_count=parsed.report["sample_count"],
    )
    try:
        db.add(dataset); db.flush()
        primary_table = str(parsed.manifest["primary_table"])
        primary_key = str(parsed.manifest["primary_key"])
        sample_records: dict[str, DataRecord] = {}
        for spec in parsed.table_specs:
            name = str(spec["name"])
            rows = parsed.tables.get(name, [])
            table = DataTable(
                dataset_version_id=dataset.id, name=name,
                primary_key=spec.get("primary_key") or (primary_key if name == primary_table else None),
                foreign_key=spec.get("foreign_key"), relation=spec.get("relation"),
                schema_data=parsed.schemas.get(name, {}), record_count=len(rows),
            )
            db.add(table); db.flush()
            pk = table.primary_key
            pending_records: list[DataRecord] = []
            for index, row in enumerate(rows, 1):
                key = row.get(pk) if pk else row.get("id") or row.get(f"{name.rstrip('s')}_id") or f"{name}:{index}"
                sample_key = row.get(table.foreign_key) if table.foreign_key else (row.get(primary_key) if name == primary_table else None)
                record = DataRecord(
                    dataset_version_id=dataset.id, table_id=table.id, table_name=name,
                    record_key=str(key), sample_key=str(sample_key) if sample_key is not None else None,
                    clean_data=copy.deepcopy(row),
                )
                pending_records.append(record)
            db.add_all(pending_records); db.flush()
            if name == primary_table:
                sample_records.update({record.record_key: record for record in pending_records})
        workflow = parsed.manifest.get("workflow", {}) if isinstance(parsed.manifest.get("workflow"), dict) else {}
        coders = workflow.get("default_coders") or ["local_reviewer"]
        stage = str(workflow.get("default_stage", "pilot_independent_review"))
        evidence = workflow.get("default_evidence") or {
            "video": True, "frames": True, "title": True, "comments": True,
            "metadata": True, "ai_suggestion": True,
        }
        for sample in sample_records.values():
            for coder in coders:
                assignment = AnnotationAssignment(
                    project_id=project.id, dataset_version_id=dataset.id, sample_record_id=sample.id,
                    coder_id=str(coder), stage=stage, experiment_group="default",
                    blind=not bool(evidence.get("ai_suggestion", True)), evidence_config=copy.deepcopy(evidence),
                )
                db.add(assignment); db.flush()
                db.add(HumanAnnotation(assignment_id=assignment.id, current_data={}, versions=copy.deepcopy(versions)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "status": "imported", "project_id": project.id, "dataset_version_id": dataset.id,
        "dataset_version": dataset.dataset_version, "digest": dataset.package_digest,
        "tables": parsed.report["tables"], "sample_count": dataset.sample_count,
    }
