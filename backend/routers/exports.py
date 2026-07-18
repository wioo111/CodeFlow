import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Assignment


router = APIRouter(prefix="/exports", tags=["exports"])


def export_rows(project_id: int, db: Session) -> list[dict]:
    assignments = db.scalars(select(Assignment).options(
        joinedload(Assignment.material), joinedload(Assignment.coder), joinedload(Assignment.annotation)
    ).where(Assignment.project_id == project_id, Assignment.status == "submitted").order_by(Assignment.id)).unique()
    return [{
        "assignment_id": item.id, "material_id": item.material_id,
        "sample_number": item.material.material_data.get("sample_number"),
        "coder_id": item.coder_id, "coder_name": item.coder.name,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "duration_seconds": item.duration_seconds,
        "schema_version": item.annotation.schema_version, "codebook_version": item.annotation.codebook_version,
        "annotation_data": item.annotation.annotation_data,
    } for item in assignments]


@router.get("/{project_id}/jsonl")
def export_jsonl(project_id: int, db: Session = Depends(get_db)):
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in export_rows(project_id, db))
    if content:
        content += "\n"
    return Response(content, media_type="application/x-ndjson", headers={"Content-Disposition": "attachment; filename=codeflow-results.jsonl"})


@router.get("/{project_id}/csv")
def export_csv(project_id: int, db: Session = Depends(get_db)):
    rows = export_rows(project_id, db)
    output = io.StringIO()
    fieldnames = ["assignment_id", "material_id", "sample_number", "coder_id", "coder_name", "submitted_at", "duration_seconds", "schema_version", "codebook_version", "annotation_data"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        row["annotation_data"] = json.dumps(row["annotation_data"], ensure_ascii=False)
        writer.writerow(row)
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=codeflow-results.csv"})

