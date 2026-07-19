from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Batch, ChangeLog, Export, Record
from backend.services.export_service import export_row, to_csv, to_json, to_jsonl


router = APIRouter(prefix="/exports", tags=["exports"])


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
