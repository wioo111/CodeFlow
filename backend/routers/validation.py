from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Record


router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/batches/{batch_id}")
def validation_report(batch_id: int, db: Session = Depends(get_db)):
    records = list(db.scalars(select(Record).where(Record.batch_id == batch_id).order_by(Record.id)))
    invalid = [{"record_id": record.id, "record_key": record.record_key, "errors": record.validation_errors} for record in records if record.validation_errors]
    return {"total": len(records), "valid": len(records) - len(invalid), "invalid": len(invalid), "records": invalid}

