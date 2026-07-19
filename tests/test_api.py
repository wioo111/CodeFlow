import csv
import io
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = Path(__file__).with_name("test-codeflow-review.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402
from backend.database import engine  # noqa: E402
from backend.main import app  # noqa: E402


def template_files(name: str):
    directory = ROOT / "project_templates" / name
    return {
        "schema_file": ("schema.json", (directory / "schema.json").read_bytes(), "application/json"),
        "view_file": ("view.json", (directory / "view.json").read_bytes(), "application/json"),
        "data_file": ("example.jsonl", (directory / "example.jsonl").read_bytes(), "application/x-ndjson"),
    }


@pytest.fixture(scope="module")
def client():
    TEST_DB.unlink(missing_ok=True)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture(scope="module")
def imported(client: TestClient):
    football = client.post("/api/imports", data={"project_name": "足球传播点审校", "batch_name": "Codex 输出", "data_version": "2026-07-19"}, files=template_files("football_cp"))
    inventory = client.post("/api/imports", data={"project_name": "库存审计", "batch_name": "库存批次"}, files=template_files("inventory"))
    assert football.status_code == inventory.status_code == 201
    return {"football": football.json(), "inventory": inventory.json()}


def test_imports_schema_view_and_jsonl_into_separate_original_and_current_data(client: TestClient, imported):
    result = imported["football"]
    assert result["record_count"] == 3 and result["invalid_count"] == 0
    projects = client.get("/api/projects").json()
    assert {project["schema_id"] for project in projects} == {"football_cp_v0.1", "inventory_audit_v1"}
    records = client.get(f"/api/batches/{result['batch_id']}/records").json()
    assert len(records) == 3
    detail = client.get(f"/api/records/{records[0]['id']}").json()
    assert detail["original_data"] == detail["current_data"]
    assert detail["schema"]["primary_key"] == "sample_id"
    assert detail["view_config"]["form"]["sections"][0]["title"] == "视频内容理解"


def test_dynamic_validation_locates_ranges_relations_and_conditions(client: TestClient, imported):
    batch_id = imported["football"]["batch_id"]
    record = client.get(f"/api/batches/{batch_id}/records").json()[0]
    data = dict(record["current_data"])
    data["confidence"] = 1.5
    data["evidence_span"] = {"start": 8.0, "end": 3.0}
    data["communicative_type"] = "P0"
    response = client.patch(f"/api/records/{record['id']}", json={"current_data": data, "operator": "tester"})
    assert response.status_code == 200
    errors = response.json()["validation_errors"]
    assert {error["path"] for error in errors} >= {"confidence", "evidence_span.start", "new_type_note"}
    blocked = client.patch(f"/api/records/{record['id']}/review", json={"status": "approved", "operator": "tester"})
    assert blocked.status_code == 422


def test_nested_edit_change_history_and_review_are_preserved(client: TestClient, imported):
    batch_id = imported["football"]["batch_id"]
    record = client.get(f"/api/batches/{batch_id}/records").json()[0]
    original = client.get(f"/api/records/{record['id']}").json()["original_data"]
    data = dict(original)
    data["literal_content"] = "球员自行绊倒后向裁判申诉，慢镜头清晰展示双脚接触。"
    data["communicative_type"] = "P3"
    data["confidence"] = 0.96
    data["evidence_span"] = {"start": 4.2, "end": 6.4}
    response = client.patch(f"/api/records/{record['id']}", json={"current_data": data, "operator": "coder_01", "review_status": "approved", "review_note": "补充关键细节"})
    assert response.status_code == 200
    detail = response.json()
    assert detail["original_data"] == original
    assert detail["current_data"] != original
    assert {"literal_content", "confidence", "evidence_span.end"}.issubset(detail["changed_fields"])
    assert {log["field_path"] for log in detail["change_logs"]} >= {"literal_content", "confidence", "evidence_span.end"}
    assert detail["review_status"] == "approved" and detail["reviewer"] == "coder_01"


def test_table_filters_bulk_review_and_validation_report(client: TestClient, imported):
    batch_id = imported["football"]["batch_id"]
    records = client.get(f"/api/batches/{batch_id}/records").json()
    response = client.patch(f"/api/batches/{batch_id}/records/bulk", json={"record_ids": [records[1]["id"], records[2]["id"]], "review_status": "needs_review", "operator": "coder_01"})
    assert response.json()["updated"] == 2
    filtered = client.get(f"/api/batches/{batch_id}/records?review_status=needs_review").json()
    assert len(filtered) == 2
    searched = client.get(f"/api/batches/{batch_id}/records?search=V003").json()
    assert [record["record_key"] for record in searched] == ["V003"]
    enum_filtered = client.get(f"/api/batches/{batch_id}/records?field_path=communicative_type&field_value=P2").json()
    assert [record["record_key"] for record in enum_filtered] == ["V003"]
    range_filtered = client.get(f"/api/batches/{batch_id}/records?field_path=confidence&min_value=0.93").json()
    assert {record["record_key"] for record in range_filtered} == {"V001", "V002"}
    report = client.get(f"/api/validation/batches/{batch_id}").json()
    assert report == {"total": 3, "valid": 3, "invalid": 0, "records": []}


def test_json_jsonl_csv_original_and_change_exports_are_machine_readable(client: TestClient, imported):
    batch_id = imported["football"]["batch_id"]
    json_rows = client.get(f"/api/exports/batches/{batch_id}/json?source=current").json()
    jsonl_text = client.get(f"/api/exports/batches/{batch_id}/jsonl?source=current").text
    jsonl_rows = [json.loads(line) for line in jsonl_text.strip().splitlines()]
    csv_text = client.get(f"/api/exports/batches/{batch_id}/csv?source=current").text.lstrip("\ufeff")
    csv_rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(json_rows) == len(jsonl_rows) == len(csv_rows) == 3
    assert json_rows[0]["_meta"]["schema_id"] == "football_cp_v0.1"
    assert "evidence_span.start" in csv_rows[0]
    assert json_rows[0]["_review"]["status"] == "approved"
    original = client.get(f"/api/exports/batches/{batch_id}/jsonl?source=original").text
    assert "慢镜头清晰" not in original
    changes = [json.loads(line) for line in client.get(f"/api/exports/batches/{batch_id}/jsonl?source=changes").text.strip().splitlines()]
    assert any(row["field_path"] == "literal_content" for row in changes)


def test_non_football_schema_uses_same_engine_and_frontend_has_no_business_codes(client: TestClient, imported):
    batch_id = imported["inventory"]["batch_id"]
    records = client.get(f"/api/batches/{batch_id}/records").json()
    assert len(records) == 2 and records[0]["current_data"]["sku"].startswith("SKU-")
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "frontend" / "src").rglob("*.tsx"))
    assert "communicative_type" not in source
    assert '"P1"' not in source and "足球" not in source


def test_duplicate_primary_keys_are_rejected(client: TestClient):
    files = template_files("inventory")
    files["data_file"] = ("duplicate.jsonl", b'{"sku":"X","product_name":"A","category":"office","stock":1}\n{"sku":"X","product_name":"B","category":"office","stock":2}\n', "application/x-ndjson")
    response = client.post("/api/imports", data={"project_name": "重复数据"}, files=files)
    assert response.status_code == 422
    assert "主键重复" in response.json()["detail"]
