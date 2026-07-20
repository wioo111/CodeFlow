import csv
import io
import json
import os
import time
import zipfile
from pathlib import Path

import pytest

from scripts.generate_scale_fixture import build_scale_package


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


def research_package(name: str, replacements: dict[str, bytes] | None = None) -> bytes:
    directory = ROOT / "project_templates" / name / "clean"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in directory.rglob("*"):
            if path.is_file():
                arcname = f"clean/{path.relative_to(directory).as_posix()}"
                archive.writestr(arcname, (replacements or {}).get(arcname, path.read_bytes()))
    return output.getvalue()


def current_football_shape_package(project_id: str) -> bytes:
    manifest = {
        "project_id": project_id,
        "name": "Current football package shape",
        "dataset_version": "current-shape-v1",
        "primary_table": "samples",
        "primary_key": "sample_id",
        "annotation_schemas": {
            "ai_raw": "schemas/codex_annotation_schema.json",
            "human_review": "schemas/review_schema.json",
        },
        "tables": [
            {"name": "samples", "file": "samples.jsonl", "schema": "schemas/sample_schema.json", "primary_key": "sample_id"},
            {"name": "comments", "file": "comments.jsonl", "schema": "schemas/comment_schema.json", "foreign_key": "sample_id"},
            {"name": "frames", "file": "frames.jsonl", "schema": "schemas/frame_schema.json", "foreign_key": "sample_id"},
            {"name": "assets", "file": "assets.jsonl", "schema": "schemas/asset_schema.json", "foreign_key": "sample_id"},
        ],
    }
    ai_schema = {
        "schema_id": "football_ai_v1", "version": "1", "primary_key": "sample_id",
        "fields": [
            {"key": "sample_id", "label": "Sample", "type": "string", "required": True},
            {"key": "ai_raw_annotation", "label": "AI", "type": "object", "properties": [
                {"key": "literal_content", "label": "Literal", "type": "long_text", "required": True},
                {"key": "key_detail", "label": "Detail", "type": "long_text"},
                {"key": "communicative_point", "label": "Point", "type": "long_text"},
                {"key": "evidence_span", "label": "Span", "type": "object", "properties": [
                    {"key": "start", "label": "Start", "type": "number"},
                    {"key": "end", "label": "End", "type": "number"},
                ]},
                {"key": "provisional_open_codes", "label": "Codes", "type": "string_array"},
                {"key": "suggested_type", "label": "Type", "type": "string"},
                {"key": "alternative_type", "label": "Alternative", "type": "string"},
                {"key": "uncertainty", "label": "Uncertainty", "type": "string"},
            ]},
        ],
    }
    review_schema = {
        "schema_id": "football_review_v1", "version": "1", "primary_key": "sample_id",
        "fields": [
            {"key": "sample_id", "label": "Sample", "type": "string", "required": True},
            {"key": "human_validated_annotation", "label": "Review", "type": "object", "properties": [
                {"key": "literal_content", "label": "Literal", "type": "long_text", "required": True},
                {"key": "key_detail", "label": "Detail", "type": "long_text", "required": True},
                {"key": "communicative_point", "label": "Point", "type": "long_text", "required": True},
                {"key": "evidence_span", "label": "Span", "type": "object", "properties": []},
                {"key": "final_type", "label": "Type", "type": "enum", "required": True,
                 "options": [{"value": "P1", "label": "P1"}, {"value": "P0", "label": "P0"}]},
                {"key": "annotation_confidence", "label": "Confidence", "type": "number", "min": 0, "max": 1},
            ]},
            {"key": "field_decisions", "label": "Decisions", "type": "object"},
        ],
    }
    rows = {
        "samples.jsonl": [{
            "sample_id": "VID-001", "aweme_id": "7659",
            "platform_metadata": {"duration_seconds": 15.766, "title": "must stay hidden", "metrics": {"like_count": 99}},
            "source": {"account": "must stay hidden", "original_url": "https://example.invalid/video"},
            "media": {"video_path": "B500-000001/video.mp4"},
        }],
        "comments.jsonl": [{"sample_id": "VID-001", "comment_id": "C1", "comment_kind": "text", "text": "comment", "rank_by_like": 1}],
        "frames.jsonl": [{"sample_id": "VID-001", "frame_index": 1, "time_seconds": 0.1, "relative_path": "B500-000001/frames/frame_0001.jpg", "exists": True}],
        "assets.jsonl": [{"sample_id": "VID-001", "assets": [
            {"asset_type": "frame", "relative_path": "B500-000001/frames/frame_0001.jpg", "exists": True},
            {"asset_type": "video", "relative_path": "B500-000001/video.mp4", "exists": True},
        ]}],
    }
    schemas = {name: {"schema_id": name, "version": "1", "fields": []} for name in ("sample_schema", "comment_schema", "frame_schema", "asset_schema")}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("clean/codeflow_project.json", json.dumps(manifest))
        archive.writestr("clean/schemas/codex_annotation_schema.json", json.dumps(ai_schema))
        archive.writestr("clean/schemas/review_schema.json", json.dumps(review_schema))
        for name, schema in schemas.items():
            archive.writestr(f"clean/schemas/{name}.json", json.dumps(schema))
        for filename, values in rows.items():
            archive.writestr(f"clean/{filename}", "\n".join(json.dumps(value) for value in values) + "\n")
    return output.getvalue()


@pytest.fixture(scope="module")
def research_import(client: TestClient):
    content = research_package("research_football")
    files = {"package_file": ("football.zip", content, "application/zip")}
    media_root = str(ROOT / "project_templates" / "research_football" / "media")
    preflight = client.post("/api/dataset-packages/preflight", data={"media_root": media_root}, files=files)
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["valid"] and preflight.json()["tables"] == {"samples": 2, "comments": 3, "frames": 3, "assets": 3}
    result = client.post("/api/dataset-packages/import", data={"media_root": media_root}, files=files)
    assert result.status_code == 201, result.text
    duplicate = client.post("/api/dataset-packages/import", data={"media_root": media_root}, files=files)
    assert duplicate.status_code == 200 and duplicate.json()["status"] == "already_exists"
    return result.json()


def test_research_package_import_is_multitable_versioned_and_idempotent(client: TestClient, research_import):
    project_id = research_import["project_id"]
    versions = client.get(f"/api/projects/{project_id}/dataset-versions").json()
    assert len(versions) == 1
    assert versions[0]["dataset_version"] == "2026.07-demo"
    queue = client.get(f"/api/projects/{project_id}/samples").json()
    assert queue["total"] == 2 and queue["items"][0]["sample_id"] == "V001"
    assert all(item["coder_id"] == "local_reviewer" for item in queue["items"])


@pytest.mark.parametrize("replacement, expected", [
    ({"clean/comments.jsonl": b'{"comment_id":"C1","sample_id":"MISSING","text":"x"}\n'}, "外键无法关联主表"),
    ({"clean/samples.jsonl": b'{"sample_id":"V001","duration_seconds":8}\n{"sample_id":"V001","duration_seconds":8}\n'}, "主键重复"),
    ({"clean/assets.jsonl": b'{"asset_id":"A1","sample_id":"V001","asset_type":"video","video_path":"../secret.mp4"}\n'}, "媒体路径越界"),
    ({"clean/samples.jsonl": b'{"sample_id":"V001","duration_seconds":"eight"}\n'}, "Schema 校验失败"),
])
def test_package_preflight_rejects_integrity_and_path_errors(client: TestClient, replacement, expected):
    response = client.post("/api/dataset-packages/preflight", files={
        "package_file": ("broken.zip", research_package("research_football", replacement), "application/zip")
    })
    assert response.status_code == 200
    report = response.json()
    assert not report["valid"] and expected in json.dumps(report["errors"], ensure_ascii=False)


def test_zip_path_traversal_is_rejected_before_preflight(client: TestClient):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../codeflow_project.json", "{}")
    response = client.post("/api/dataset-packages/preflight", files={"package_file": ("unsafe.zip", output.getvalue(), "application/zip")})
    assert response.status_code == 422 and "不安全路径" in response.json()["detail"]


def test_missing_declared_file_fails_without_partial_import(client: TestClient):
    manifest = json.loads((ROOT / "project_templates/research_inventory/clean/codeflow_project.json").read_text(encoding="utf-8"))
    manifest["project_id"] = "broken_missing_file"
    manifest["tables"][1]["file"] = "missing.jsonl"
    replacement = {"clean/codeflow_project.json": json.dumps(manifest, ensure_ascii=False).encode()}
    package = research_package("research_inventory", replacement)
    preflight = client.post("/api/dataset-packages/preflight", files={"package_file": ("broken.zip", package, "application/zip")}).json()
    assert not preflight["valid"]
    imported = client.post("/api/dataset-packages/import", files={"package_file": ("broken.zip", package, "application/zip")})
    assert imported.status_code == 422
    assert not any(project["schema_id"] == "broken_missing_file" for project in client.get("/api/projects").json())


def test_video_range_frames_comments_and_server_side_visibility(client: TestClient, research_import):
    project_id = research_import["project_id"]
    item = client.get(f"/api/projects/{project_id}/samples").json()["items"][0]
    assignment_id, sample_record_id = item["assignment_id"], item["sample_record_id"]
    comments = client.get(f"/api/samples/{sample_record_id}/comments?assignment_id={assignment_id}").json()
    frames = client.get(f"/api/samples/{sample_record_id}/frames?assignment_id={assignment_id}").json()
    assert [row["rank_by_like"] for row in comments] == [1, 2]
    assert [row["time_seconds"] for row in frames] == [1.0, 4.2]
    video = client.get(f"/api/samples/{sample_record_id}/media/video?assignment_id={assignment_id}", headers={"Range": "bytes=0-99"})
    assert video.status_code == 206 and len(video.content) == 100 and video.headers["accept-ranges"] == "bytes"
    other = client.get(f"/api/assignments/{assignment_id}", headers={"X-User-ID": "coder_02"})
    assert other.status_code == 403


def test_current_250_package_shape_supports_nested_media_schemas_duration_and_blinding(client: TestClient, tmp_path: Path):
    media_root = tmp_path / "media"
    frame_path = media_root / "B500-000001" / "frames" / "frame_0001.jpg"
    video_path = media_root / "B500-000001" / "video.mp4"
    frame_path.parent.mkdir(parents=True)
    frame_path.write_bytes(b"jpeg-frame")
    video_path.write_bytes(bytes(range(256)))
    content = current_football_shape_package("current_football_shape")
    files = {"package_file": ("current-shape.zip", content, "application/zip")}

    preflight = client.post("/api/dataset-packages/preflight", data={"media_root": str(media_root)}, files=files)
    assert preflight.status_code == 200 and preflight.json()["valid"], preflight.text
    imported = client.post("/api/dataset-packages/import", data={"media_root": str(media_root)}, files=files)
    assert imported.status_code == 201, imported.text
    project_id = imported.json()["project_id"]
    queue_item = client.get(f"/api/projects/{project_id}/samples").json()["items"][0]
    assignment_id = queue_item["assignment_id"]
    sample_record_id = queue_item["sample_record_id"]

    detail = client.get(f"/api/assignments/{assignment_id}").json()
    field_keys = {field["key"] for field in detail["annotation_schema"]["fields"]}
    assert {"literal_content", "key_detail", "communicative_point", "final_type"}.issubset(field_keys)
    assert "sample_id" not in field_keys and "evidence_span" not in field_keys and "notes" not in field_keys
    comments = client.get(f"/api/samples/{sample_record_id}/comments?assignment_id={assignment_id}").json()
    assert comments[0]["comment_type"] == "text"
    frames = client.get(f"/api/samples/{sample_record_id}/frames?assignment_id={assignment_id}").json()
    assert frames[0]["frame_id"] and frames[0]["path"].endswith("frame_0001.jpg")
    frame = client.get(f"/api/samples/{sample_record_id}/frames/{frames[0]['frame_id']}/media?assignment_id={assignment_id}")
    assert frame.status_code == 200 and frame.content == b"jpeg-frame"
    video = client.get(f"/api/samples/{sample_record_id}/media/video?assignment_id={assignment_id}", headers={"Range": "bytes=0-9"})
    assert video.status_code == 206 and video.content == bytes(range(10))

    human = {"literal_content": "visible action", "key_detail": "key moment", "communicative_point": "shareable point", "final_type": "P1"}
    invalid_span = client.patch(f"/api/assignments/{assignment_id}/draft", json={
        "annotation": human, "field_decisions": {}, "evidence_spans": [{"start": 1, "end": 999, "primary": True}],
    })
    assert invalid_span.status_code == 200
    assert any(error["code"] == "duration" for error in invalid_span.json()["validation_errors"])

    ai_output = {
        "literal_content": "visible action", "key_detail": "key moment", "communicative_point": "shareable point",
        "evidence_span": {"start": 1.0, "end": 2.0}, "provisional_open_codes": ["skill"],
        "suggested_type": "P1", "alternative_type": "", "uncertainty": "",
    }
    model = client.post("/api/model-runs/import", json={
        "project_id": project_id, "name": "shape-regression", "model_version": "test-model", "prompt_version": "test-prompt",
        "annotations": [{"sample_id": "VID-001", "annotation": ai_output}],
    })
    assert model.status_code == 201, model.text
    assert client.get(f"/api/assignments/{assignment_id}").json()["ai_raw_annotation"]["raw_output"] == ai_output
    repaired = client.post("/api/dataset-packages/import", data={"media_root": str(media_root)}, files=files)
    assert repaired.status_code == 200
    assert repaired.json()["metadata_repaired"] is True and repaired.json()["ai_annotations_revalidated"] == 1
    assert not client.get(f"/api/assignments/{assignment_id}").json()["ai_raw_annotation"]["validation_errors"]

    manager = {"X-User-ID": "manager", "X-User-Role": "research_manager"}
    created = client.post(f"/api/projects/{project_id}/assignments", headers=manager, json={
        "dataset_version_id": imported.json()["dataset_version_id"], "sample_ids": ["VID-001"], "coder_ids": ["blind_current"],
        "stage": "blind_control", "experiment_group": "video-only", "blind": True,
        "evidence_config": {"video": True, "frames": False, "title": False, "comments": False, "metadata": False, "ai_suggestion": False},
    })
    assert created.status_code == 201
    blind_assignment = created.json()["created"][0]
    blind_headers = {"X-User-ID": "blind_current", "X-User-Role": "coder"}
    sample = client.get(f"/api/samples/{sample_record_id}?assignment_id={blind_assignment}", headers=blind_headers).json()["data"]
    assert sample["duration_seconds"] == pytest.approx(15.766)
    assert "platform_metadata" not in sample and "source" not in sample and "title" not in sample


def test_ai_raw_human_draft_span_validation_submit_lock_and_isolation(client: TestClient, research_import):
    project_id = research_import["project_id"]
    local_item = client.get(f"/api/projects/{project_id}/samples").json()["items"][0]
    sample_id, assignment_id = local_item["sample_id"], local_item["assignment_id"]
    model = client.post("/api/model-runs/import", json={
        "project_id": project_id, "name": "demo", "model_version": "m1", "prompt_version": "p1",
        "annotations": [{"sample_id": sample_id, "annotation": {"literal_content": "AI 原始事实", "final_type": "controversy"}}],
    })
    assert model.status_code == 201
    detail = client.get(f"/api/assignments/{assignment_id}").json()
    assert detail["ai_raw_annotation"]["immutable"] is True
    payload = {"annotation": {"literal_content": "人工事实", "key_detail": "接触瞬间", "communicative_point": "判罚争议", "final_type": "controversy", "annotation_confidence": 0.9},
               "field_decisions": {"literal_content": "minor_edit", "key_detail": "supplement", "final_type": "accept"},
               "evidence_spans": [{"start": 1.2, "end": 3.4, "primary": True}], "active_seconds": 12.5}
    draft = client.patch(f"/api/assignments/{assignment_id}/draft", json=payload)
    assert draft.status_code == 200 and not draft.json()["validation_errors"]
    bad = {**payload, "evidence_spans": [{"start": 2, "end": 9, "primary": True}]}
    rejected = client.post(f"/api/assignments/{assignment_id}/submit", json=bad)
    assert rejected.status_code == 422
    submitted = client.post(f"/api/assignments/{assignment_id}/submit", json=payload)
    assert submitted.status_code == 200 and submitted.json()["locked"]
    assert client.post(f"/api/assignments/{assignment_id}/submit", json=payload).json()["idempotent"]
    assert client.patch(f"/api/assignments/{assignment_id}/draft", json=payload).status_code == 409
    locked = client.get(f"/api/assignments/{assignment_id}").json()
    assert locked["ai_raw_annotation"]["raw_output"]["literal_content"] == "AI 原始事实"
    assert locked["human_annotation"]["submitted_data"]["literal_content"] == "人工事实"
    assert any(log["field_path"] == "evidence_spans" for log in locked["change_logs"])


def test_blind_nonfootball_package_uses_same_kernel_and_hides_evidence_by_api(client: TestClient):
    content = research_package("research_inventory")
    response = client.post("/api/dataset-packages/import", files={"package_file": ("inventory.zip", content, "application/zip")})
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    item = client.get(f"/api/projects/{project_id}/samples").json()["items"][0]
    assert "title" not in item["sample"]
    assert client.get(f"/api/samples/{item['sample_record_id']}/comments?assignment_id={item['assignment_id']}").status_code == 403
    detail = client.get(f"/api/assignments/{item['assignment_id']}").json()
    assert detail["blind"] and detail["ai_raw_annotation"] is None
    assert detail["annotation_schema"]["schema_id"] == "warehouse_annotation"


def test_two_coders_adjudication_gold_and_research_export(client: TestClient, research_import):
    project_id = research_import["project_id"]
    coder_headers = {"X-User-ID": "coder_02", "X-User-Role": "coder"}
    item = client.get(f"/api/projects/{project_id}/samples", headers=coder_headers).json()["items"][0]
    payload = {"annotation": {"literal_content": "第二人事实", "key_detail": "接触", "communicative_point": "存在争议", "final_type": "controversy"},
               "field_decisions": {"literal_content": "major_edit"}, "evidence_spans": [{"start": 1.0, "end": 3.0, "primary": True}]}
    assert client.post(f"/api/assignments/{item['assignment_id']}/submit", json=payload, headers=coder_headers).status_code == 200
    manager = {"X-User-ID": "manager", "X-User-Role": "research_manager"}
    prepared = client.post(f"/api/projects/{project_id}/adjudications/prepare", headers=manager)
    assert prepared.status_code == 201 and prepared.json()["count"] >= 1
    adjudication_id = prepared.json()["created"][0]
    comparison = client.get(f"/api/adjudications/{adjudication_id}", headers=manager).json()
    assert len(comparison["human_annotations"]) == 2 and comparison["differences"]
    resolution = {"literal_content": "仲裁事实", "key_detail": "接触瞬间", "communicative_point": "判罚争议", "final_type": "controversy"}
    assert client.post(f"/api/adjudications/{adjudication_id}/resolve", json={"resolution": resolution, "rationale": "逐字段核对视频"}, headers=manager).status_code == 200
    frozen = client.post(f"/api/gold/{project_id}/freeze", json={"gold_version": "gold-v1"}, headers=manager)
    assert frozen.status_code == 201 and frozen.json()["frozen"] >= 1
    exported = client.post("/api/exports", json={"project_id": project_id, "gold_version": "gold-v1", "anonymize_coders": True})
    assert exported.status_code == 200 and exported.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        expected = {"ai_raw_annotations.jsonl", "human_annotations_long.jsonl", "human_annotations_wide.jsonl",
                    "field_decisions.jsonl", "change_logs.jsonl", "adjudications.jsonl", "gold_annotations.jsonl",
                    "assignments.csv", "agreement_input.csv", "annotation_metrics.json", "export_manifest.json"}
        assert set(archive.namelist()) == expected
        manifest = json.loads(archive.read("export_manifest.json"))
        assert manifest["dataset_version"] == "2026.07-demo" and len(manifest["files"]) == 10


def test_new_dataset_version_does_not_overwrite_old_and_manager_can_create_blind_assignment(client: TestClient, research_import):
    manifest_path = ROOT / "project_templates/research_football/clean/codeflow_project.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_version"] = "2026.08-demo"
    replacements = {"clean/codeflow_project.json": json.dumps(manifest, ensure_ascii=False).encode()}
    package = research_package("research_football", replacements)
    media_root = str(ROOT / "project_templates/research_football/media")
    imported = client.post("/api/dataset-packages/import", data={"media_root": media_root}, files={"package_file": ("v2.zip", package, "application/zip")})
    assert imported.status_code == 201 and imported.json()["dataset_version_id"] != research_import["dataset_version_id"]
    versions = client.get(f"/api/projects/{research_import['project_id']}/dataset-versions").json()
    assert {row["dataset_version"] for row in versions} == {"2026.07-demo", "2026.08-demo"}
    manager = {"X-User-ID": "manager", "X-User-Role": "research_manager"}
    created = client.post(f"/api/projects/{research_import['project_id']}/assignments", headers=manager, json={
        "dataset_version_id": imported.json()["dataset_version_id"], "sample_ids": ["V001"],
        "coder_ids": ["blind_coder"], "stage": "blind_control", "experiment_group": "video-only",
        "blind": True, "evidence_config": {"video": True, "frames": False, "title": False, "comments": False, "metadata": False, "ai_suggestion": False},
    })
    assert created.status_code == 201 and created.json()["count"] == 1
    assignment_id = created.json()["created"][0]
    blind_headers = {"X-User-ID": "blind_coder", "X-User-Role": "coder"}
    detail = client.get(f"/api/assignments/{assignment_id}", headers=blind_headers).json()
    sample = client.get(f"/api/samples/{detail['sample_record_id']}?assignment_id={assignment_id}", headers=blind_headers).json()
    assert detail["ai_raw_annotation"] is None and "title" not in sample["data"] and "account" not in sample["data"]
    assert client.get(f"/api/samples/{detail['sample_record_id']}/comments?assignment_id={assignment_id}", headers=blind_headers).status_code == 403


def test_250_sample_multitable_scale_import_and_pagination(client: TestClient):
    content = build_scale_package(sample_count=250, comments_per_sample=20, frames_per_sample=3)
    files = {"package_file": ("scale-250.zip", content, "application/zip")}
    started = time.perf_counter()
    preflight = client.post("/api/dataset-packages/preflight", files=files)
    assert preflight.status_code == 200 and preflight.json()["valid"], preflight.text
    assert preflight.json()["tables"] == {"samples": 250, "comments": 5000, "frames": 750, "assets": 250}
    imported = client.post("/api/dataset-packages/import", files=files)
    elapsed = time.perf_counter() - started
    assert imported.status_code == 201, imported.text
    assert elapsed < 30, f"250 条规模包预检与导入耗时 {elapsed:.2f}s"
    project_id = imported.json()["project_id"]
    headers = {"X-User-ID": "scale_coder_01", "X-User-Role": "coder"}
    first_page = client.get(f"/api/projects/{project_id}/samples?page=1&page_size=100", headers=headers).json()
    third_page = client.get(f"/api/projects/{project_id}/samples?page=3&page_size=100", headers=headers).json()
    assert first_page["total"] == 250 and first_page["status_counts"] == {"pending": 250}
    assert len(first_page["items"]) == 100 and len(third_page["items"]) == 50
    first = first_page["items"][0]
    comments = client.get(f"/api/samples/{first['sample_record_id']}/comments?assignment_id={first['assignment_id']}", headers=headers).json()
    frames = client.get(f"/api/samples/{first['sample_record_id']}/frames?assignment_id={first['assignment_id']}", headers=headers).json()
    assert len(comments) == 20 and [row["rank_by_like"] for row in comments] == list(range(1, 21))
    assert len(frames) == 3 and [row["time_seconds"] for row in frames] == [10.0, 20.0, 30.0]
