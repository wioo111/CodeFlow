import copy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.database import get_db
from backend.models import Batch, ChangeLog, Record
from backend.schemas import BulkUpdate, RecordUpdate, ReviewUpdate
from backend.services.diff_service import differences, flatten
from backend.services.schema_parser import get_path, set_path
from backend.services.schema_validator import validate_record


router = APIRouter(tags=["records"])


def base_query():
    return select(Record).options(joinedload(Record.batch).joinedload(Batch.project), selectinload(Record.change_logs))


def changed_fields(record: Record) -> list[str]:
    return [item["field_path"] for item in differences(record.original_data, record.current_data)]


def record_view(record: Record, detail: bool = False) -> dict:
    result = {
        "id": record.id, "batch_id": record.batch_id, "project_id": record.batch.project_id, "record_key": record.record_key,
        "current_data": record.current_data, "validation_status": record.validation_status,
        "validation_errors": record.validation_errors, "review_status": record.review_status,
        "reviewer": record.reviewer, "reviewed_at": record.reviewed_at, "review_note": record.review_note,
        "changed_fields": changed_fields(record), "created_at": record.created_at, "updated_at": record.updated_at,
    }
    if detail:
        result["original_data"] = record.original_data
        result["change_logs"] = [{
            "id": log.id, "field_path": log.field_path, "old_value": log.old_value,
            "new_value": log.new_value, "operator": log.operator, "changed_at": log.changed_at,
        } for log in sorted(record.change_logs, key=lambda item: item.id, reverse=True)]
        result["schema"] = record.batch.project.schema_data
        result["view_config"] = record.batch.project.view_config
        result["project_id"] = record.batch.project_id
    return result


@router.get("/batches/{batch_id}/records")
def list_records(
    batch_id: int, search: str = "", review_status: str = "", validation_status: str = "",
    field_path: str = "", field_value: str = "", min_value: float | None = None, max_value: float | None = None,
    sort_by: str = "", sort_order: str = Query("asc", pattern="^(asc|desc)$"), db: Session = Depends(get_db),
):
    records = list(db.scalars(base_query().where(Record.batch_id == batch_id).order_by(Record.id)).unique())
    if search:
        needle = search.lower()
        records = [record for record in records if needle in record.record_key.lower() or needle in str(record.current_data).lower()]
    if review_status: records = [record for record in records if record.review_status == review_status]
    if validation_status: records = [record for record in records if record.validation_status == validation_status]
    if field_path and field_value: records = [record for record in records if str(get_path(record.current_data, field_path, "")).lower() == field_value.lower()]
    if field_path and min_value is not None: records = [record for record in records if isinstance(get_path(record.current_data, field_path), (int, float)) and get_path(record.current_data, field_path) >= min_value]
    if field_path and max_value is not None: records = [record for record in records if isinstance(get_path(record.current_data, field_path), (int, float)) and get_path(record.current_data, field_path) <= max_value]
    if sort_by:
        records.sort(key=lambda record: (flatten(record.current_data).get(sort_by) is None, str(flatten(record.current_data).get(sort_by, ""))), reverse=sort_order == "desc")
    return [record_view(record) for record in records]


@router.get("/records/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db)):
    record = db.scalars(base_query().where(Record.id == record_id)).unique().first()
    if not record: raise HTTPException(404, "记录不存在")
    siblings = list(db.scalars(select(Record.id).where(Record.batch_id == record.batch_id).order_by(Record.id)))
    result = record_view(record, detail=True)
    index = siblings.index(record.id)
    result["previous_id"] = siblings[index - 1] if index > 0 else None
    result["next_id"] = siblings[index + 1] if index < len(siblings) - 1 else None
    return result


def apply_update(record: Record, data: dict, operator: str, db: Session):
    for change in differences(record.current_data, data):
        db.add(ChangeLog(record_id=record.id, operator=operator, **change))
    record.current_data = copy.deepcopy(data)
    errors = validate_record(record.batch.project.schema_data, data)
    record.validation_errors = errors
    record.validation_status = "invalid" if errors else "valid"
    if record.review_status == "unreviewed": record.review_status = "in_progress"


@router.patch("/records/{record_id}")
def update_record(record_id: int, payload: RecordUpdate, db: Session = Depends(get_db)):
    record = db.scalars(base_query().where(Record.id == record_id)).unique().first()
    if not record: raise HTTPException(404, "记录不存在")
    apply_update(record, payload.current_data, payload.operator, db)
    if payload.review_status == "approved" and record.validation_errors:
        raise HTTPException(422, {"message": "存在校验错误，不能标记通过", "errors": record.validation_errors})
    if payload.review_status:
        record.review_status = payload.review_status
        record.reviewer = payload.operator
        record.reviewed_at = datetime.now(timezone.utc)
    if payload.review_note is not None: record.review_note = payload.review_note
    db.commit(); db.refresh(record)
    return record_view(record, detail=True)


@router.patch("/records/{record_id}/review")
def review_record(record_id: int, payload: ReviewUpdate, db: Session = Depends(get_db)):
    record = db.scalars(base_query().where(Record.id == record_id)).unique().first()
    if not record: raise HTTPException(404, "记录不存在")
    if payload.status == "approved" and record.validation_errors:
        raise HTTPException(422, {"message": "存在校验错误，不能标记通过", "errors": record.validation_errors})
    record.review_status, record.reviewer, record.review_note = payload.status, payload.operator, payload.note
    record.reviewed_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(record)
    return record_view(record)


@router.patch("/batches/{batch_id}/records/bulk")
def bulk_update(batch_id: int, payload: BulkUpdate, db: Session = Depends(get_db)):
    records = list(db.scalars(base_query().where(Record.batch_id == batch_id, Record.id.in_(payload.record_ids))).unique())
    if len(records) != len(set(payload.record_ids)): raise HTTPException(404, "部分记录不存在")
    now = datetime.now(timezone.utc)
    for record in records:
        if payload.field_path:
            data = copy.deepcopy(record.current_data); old = flatten(data).get(payload.field_path)
            set_path(data, payload.field_path, payload.value)
            if old != payload.value: db.add(ChangeLog(record_id=record.id, field_path=payload.field_path, old_value=old, new_value=payload.value, operator=payload.operator))
            record.current_data = data
            record.validation_errors = validate_record(record.batch.project.schema_data, data)
            record.validation_status = "invalid" if record.validation_errors else "valid"
        if payload.review_status:
            if payload.review_status == "approved" and record.validation_errors: continue
            record.review_status, record.reviewer, record.reviewed_at = payload.review_status, payload.operator, now
    db.commit()
    return {"updated": len(records)}
