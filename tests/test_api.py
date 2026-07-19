import csv
import io
import json
import os
from pathlib import Path

import pytest


TEST_DB = Path(__file__).with_name("test-codeflow.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402
from backend.database import engine  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    TEST_DB.unlink(missing_ok=True)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def valid_annotation():
    return {
        "literal_content": "测试材料的客观描述",
        "communicative_type": "P1",
        "secondary_features": ["skill"],
        "has_clear_climax": True,
        "confidence": 4,
        "notes": "测试提交",
    }


def test_seeded_project_and_ten_tasks(client: TestClient):
    projects = client.get("/api/projects").json()
    assert len(projects) == 1
    assert projects[0]["total"] == 10
    tasks = client.get("/api/tasks?project_id=1").json()
    assert len(tasks) == 10
    assert {task["material"]["material_type"] for task in tasks} == {"mock", "text"}


def test_schema_is_dynamic_and_supports_required_types(client: TestClient):
    schema = client.get("/api/projects/1/schema").json()
    assert schema["version"] == "football_v0.1"
    assert {field["type"] for field in schema["fields"]} >= {"long_text", "short_text", "single_select", "multi_select", "boolean", "scale"}


def test_draft_restores_then_submit_locks(client: TestClient):
    draft = {"literal_content": "尚未完成的草稿"}
    response = client.put("/api/annotations/1/draft", json={"annotation_data": draft, "duration_seconds": 12})
    assert response.status_code == 200
    assert client.get("/api/tasks/1").json()["annotation"]["annotation_data"] == draft

    invalid = client.post("/api/annotations/1/submit", json={"annotation_data": draft, "duration_seconds": 15})
    assert invalid.status_code == 422

    submitted = client.post("/api/annotations/1/submit", json={"annotation_data": valid_annotation(), "duration_seconds": 20})
    assert submitted.status_code == 200
    task = client.get("/api/tasks/1").json()
    assert task["status"] == "submitted"
    assert task["annotation"]["schema_version"] == "football_v0.1"
    assert task["coder"]["name"] == "演示编码员"
    assert task["submitted_at"]

    locked = client.put("/api/annotations/1/draft", json={"annotation_data": draft, "duration_seconds": 25})
    assert locked.status_code == 409


def test_next_task_and_exports(client: TestClient):
    next_task = client.get("/api/tasks/next?project_id=1&after_id=1").json()
    assert next_task["id"] == 2

    jsonl = client.get("/api/exports/1/jsonl")
    rows = [json.loads(line) for line in jsonl.text.strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["coder_name"] == "演示编码员"
    assert rows[0]["schema_version"] == "football_v0.1"

    csv_response = client.get("/api/exports/1/csv")
    csv_rows = list(csv.DictReader(io.StringIO(csv_response.text.lstrip("\ufeff"))))
    assert len(csv_rows) == 1
    assert json.loads(csv_rows[0]["annotation_data"])["communicative_type"] == "P1"


def test_all_ten_tasks_can_be_completed_continuously(client: TestClient):
    for assignment_id in range(2, 11):
        annotation = valid_annotation()
        annotation["literal_content"] = f"样本 {assignment_id} 的客观描述"
        response = client.post(
            f"/api/annotations/{assignment_id}/submit",
            json={"annotation_data": annotation, "duration_seconds": assignment_id * 5},
        )
        assert response.status_code == 200

    assert client.get("/api/tasks/next?project_id=1").json() is None
    project = client.get("/api/projects/1").json()
    assert project["completed"] == project["total"] == 10

    jsonl_rows = [
        json.loads(line)
        for line in client.get("/api/exports/1/jsonl").text.strip().splitlines()
    ]
    csv_rows = list(
        csv.DictReader(
            io.StringIO(client.get("/api/exports/1/csv").text.lstrip("\ufeff"))
        )
    )
    assert len(jsonl_rows) == len(csv_rows) == 10
