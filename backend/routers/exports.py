import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import (
    AIRawAnnotation, Adjudication, AnnotationAssignment, Batch, ChangeLog, DataRecord,
    DatasetVersion, Export, GoldAnnotation, HumanAnnotation, ModelRun, Record, ResearchChangeLog,
)
from backend.services.export_service import export_row, to_csv, to_json, to_jsonl
from backend.services.diff_service import flatten


router = APIRouter(prefix="/exports", tags=["exports"])


class ResearchExportRequest(BaseModel):
    project_id: int
    dataset_version_id: int | None = None
    gold_version: str | None = None
    anonymize_coders: bool = False


@router.get("/batches/{batch_id}/{format}")
def export_batch(
    batch_id: int, format: str, source: str = Query("current", pattern="^(current|original|changes)$"),
    review_status: str = "", db: Session = Depends(get_db),
):
    if format not in {"json", "jsonl", "csv"}: raise HTTPException(422, "仅支持 json、jsonl、csv")
    batch = db.get(Batch, batch_id)
    if not batch: raise HTTPException(404, "批次不存在")
    records = list(db.scalars(select(Record).options(joinedload(Record.batch).joinedload(Batch.project)).where(Record.batch_id == batch_id).order_by(Record.id)).unique())
    if review_status: records = [record for record in records if record.review_status == review_status]
    if source == "changes":
        ids = [record.id for record in records]
        logs = list(db.scalars(select(ChangeLog).where(ChangeLog.record_id.in_(ids)).order_by(ChangeLog.id))) if ids else []
        rows = [{"record_id": log.record_id, "field_path": log.field_path, "old_value": log.old_value, "new_value": log.new_value, "operator": log.operator, "changed_at": log.changed_at.isoformat()} for log in logs]
    else: rows = [export_row(record, source) for record in records]
    if format == "json": content, media = to_json(rows), "application/json"
    elif format == "jsonl": content, media = to_jsonl(rows), "application/x-ndjson"
    else: content, media = to_csv(rows), "text/csv; charset=utf-8"
    filename = f"reviewed_data.{format}" if source == "current" else f"{source}_data.{format}"
    db.add(Export(project_id=batch.project_id, batch_id=batch.id, format=format, filter_condition={"source": source, "review_status": review_status}, file_path=filename)); db.commit()
    return Response(content, media_type=media, headers={"Content-Disposition": f"attachment; filename={filename}"})


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return ("\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in rows) + ("\n" if rows else "")).encode("utf-8")


def _csv(rows: list[dict[str, Any]]) -> bytes:
    columns = sorted({key for row in rows for key in row})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    return ("\ufeff" + output.getvalue()).encode("utf-8")


@router.post("")
def export_research_package(payload: ResearchExportRequest, db: Session = Depends(get_db)):
    dataset_query = select(DatasetVersion).where(DatasetVersion.project_id == payload.project_id)
    if payload.dataset_version_id: dataset_query = dataset_query.where(DatasetVersion.id == payload.dataset_version_id)
    dataset = db.scalar(dataset_query.order_by(DatasetVersion.id.desc()))
    if not dataset: raise HTTPException(404, "数据版本不存在")
    assignments = db.scalars(select(AnnotationAssignment).where(AnnotationAssignment.dataset_version_id == dataset.id).order_by(AnnotationAssignment.id)).all()
    assignment_ids = [item.id for item in assignments]
    humans = {item.assignment_id: item for item in db.scalars(select(HumanAnnotation).where(HumanAnnotation.assignment_id.in_(assignment_ids))).all()} if assignment_ids else {}
    samples = {item.id: item for item in db.scalars(select(DataRecord).where(DataRecord.dataset_version_id == dataset.id)).all()}
    coder_alias: dict[str, str] = {}
    def coder(value: str | None) -> str | None:
        if not value or not payload.anonymize_coders: return value
        if value not in coder_alias: coder_alias[value] = f"coder_{len(coder_alias) + 1:02d}"
        return coder_alias[value]
    ai_rows = []
    runs = {row.id: row for row in db.scalars(select(ModelRun).where(ModelRun.project_id == payload.project_id)).all()}
    sample_ids = [row.id for row in samples.values()]
    for item in db.scalars(select(AIRawAnnotation).where(AIRawAnnotation.sample_record_id.in_(sample_ids))).all() if sample_ids else []:
        run = runs.get(item.model_run_id)
        ai_rows.append({"sample_id": samples[item.sample_record_id].record_key, "model_run_id": item.model_run_id,
                        "model_version": run.model_version if run else None, "prompt_version": run.prompt_version if run else None,
                        "raw_output": item.raw_output, "parse_status": item.parse_status, "validation_errors": item.validation_errors})
    wide, long_rows, decisions, assignment_rows, agreement = [], [], [], [], []
    for assignment in assignments:
        human = humans.get(assignment.id); sample = samples.get(assignment.sample_record_id)
        if not human or not sample: continue
        annotation = human.submitted_data if human.locked else human.current_data
        meta = {"sample_id": sample.record_key, "assignment_id": assignment.id, "coder_id": coder(assignment.coder_id),
                "stage": assignment.stage, "experiment_group": assignment.experiment_group,
                "dataset_version": dataset.dataset_version, **dataset.versions}
        wide.append({**meta, "annotation": annotation, "evidence_spans": human.evidence_spans, "locked": human.locked})
        for field_path, value in flatten(annotation or {}).items():
            long_rows.append({**meta, "field_path": field_path, "value": value})
            agreement.append({"sample_id": sample.record_key, "coder_id": coder(assignment.coder_id), "field_path": field_path, "value": value, "stage": assignment.stage})
        for field_path, decision in (human.field_decisions or {}).items():
            decisions.append({**meta, "field_path": field_path, "decision": decision})
        assignment_rows.append({**meta, "status": assignment.status, "blind": assignment.blind,
                                "started_at": assignment.started_at, "first_saved_at": assignment.first_saved_at,
                                "submitted_at": assignment.submitted_at, "active_seconds": assignment.active_seconds})
    logs = [{"sample_id": samples[db.get(AnnotationAssignment, item.assignment_id).sample_record_id].record_key,
             "assignment_id": item.assignment_id, "coder_id": coder(item.operator), "stage": item.stage,
             "field_path": item.field_path, "old_value": item.old_value, "new_value": item.new_value,
             "change_type": item.change_type, "reason": item.reason, "versions": item.versions,
             "changed_at": item.changed_at} for item in (db.scalars(select(ResearchChangeLog).where(ResearchChangeLog.assignment_id.in_(assignment_ids))).all() if assignment_ids else [])]
    adjudications = [{"id": item.id, "sample_id": samples[item.sample_record_id].record_key,
                      "assignment_ids": item.assignment_ids, "differences": item.differences,
                      "resolution": item.resolution, "adjudicator_id": coder(item.adjudicator_id),
                      "rationale": item.rationale, "status": item.status, "resolved_at": item.resolved_at}
                     for item in db.scalars(select(Adjudication).where(Adjudication.dataset_version_id == dataset.id)).all()]
    gold_query = select(GoldAnnotation).where(GoldAnnotation.dataset_version_id == dataset.id)
    if payload.gold_version: gold_query = gold_query.where(GoldAnnotation.gold_version == payload.gold_version)
    gold = [{"sample_id": samples[item.sample_record_id].record_key, "gold_version": item.gold_version,
             "annotation": item.annotation_data, "source_adjudication_id": item.source_adjudication_id,
             "frozen_by": coder(item.frozen_by), "frozen_at": item.frozen_at} for item in db.scalars(gold_query).all()]
    metrics = {"total_assignments": len(assignments), "submitted": sum(item.status == "submitted" for item in assignments),
               "field_decisions": {name: sum(row["decision"] == name for row in decisions) for name in sorted({row["decision"] for row in decisions})}}
    files: dict[str, bytes] = {
        "ai_raw_annotations.jsonl": _jsonl(ai_rows), "human_annotations_long.jsonl": _jsonl(long_rows),
        "human_annotations_wide.jsonl": _jsonl(wide), "field_decisions.jsonl": _jsonl(decisions),
        "change_logs.jsonl": _jsonl(logs), "adjudications.jsonl": _jsonl(adjudications),
        "gold_annotations.jsonl": _jsonl(gold), "assignments.csv": _csv(assignment_rows),
        "agreement_input.csv": _csv(agreement),
        "annotation_metrics.json": json.dumps(metrics, ensure_ascii=False, indent=2).encode("utf-8"),
    }
    manifest = {"project_id": dataset.external_project_id, "dataset_version": dataset.dataset_version,
                "versions": dataset.versions, "generated_at": datetime.now(timezone.utc).isoformat(),
                "record_counts": {name: (content.count(b"\n") if name.endswith((".jsonl", ".csv")) else 1) for name, content in files.items()},
                "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
    files["export_manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items(): archive.writestr(name, content)
    return Response(output.getvalue(), media_type="application/zip", headers={"Content-Disposition": "attachment; filename=codeflow_research_export.zip"})
