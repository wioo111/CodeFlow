import csv
import io
import json
from typing import Any

from backend.models import Record
from .diff_service import flatten


def review_metadata(record: Record) -> dict[str, Any]:
    original_flat, current_flat = flatten(record.original_data), flatten(record.current_data)
    changed = sorted(path for path in set(original_flat) | set(current_flat) if original_flat.get(path) != current_flat.get(path))
    return {
        "status": record.review_status, "reviewer": record.reviewer,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "changed_fields": changed, "note": record.review_note,
    }


def export_row(record: Record, source: str = "current") -> dict[str, Any]:
    data = dict(record.original_data if source == "original" else record.current_data)
    data["_review"] = review_metadata(record)
    data["_meta"] = {
        "schema_id": record.batch.project.schema_id, "schema_version": record.batch.project.schema_version,
        "data_version": record.batch.data_version,
    }
    return data


def to_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


def to_jsonl(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else "")


def to_csv(rows: list[dict[str, Any]]) -> str:
    flat_rows = [flatten(row) for row in rows]
    columns = sorted({key for row in flat_rows for key in row})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in flat_rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value for key, value in row.items()})
    return "\ufeff" + output.getvalue()

