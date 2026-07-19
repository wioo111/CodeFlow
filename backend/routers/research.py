from __future__ import annotations

import mimetypes
import os
import copy
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AnnotationAssignment, DataRecord, DataTable, DatasetVersion, Project


router = APIRouter(tags=["research data"])
MANAGER_ROLES = {"admin", "research_manager", "adjudicator"}


def current_identity(
    x_user_id: str = Header("local_reviewer"), x_user_role: str = Header("coder"),
) -> tuple[str, str]:
    return x_user_id, x_user_role


def assignment_for(
    db: Session, assignment_id: int | None, sample_record_id: int, identity: tuple[str, str],
) -> AnnotationAssignment:
    user, role = identity
    query = select(AnnotationAssignment).where(AnnotationAssignment.sample_record_id == sample_record_id)
    if assignment_id is not None:
        query = query.where(AnnotationAssignment.id == assignment_id)
    elif role not in MANAGER_ROLES:
        query = query.where(AnnotationAssignment.coder_id == user)
    assignment = db.scalar(query.order_by(AnnotationAssignment.id))
    if not assignment:
        raise HTTPException(404, "未找到可访问的标注任务")
    if role not in MANAGER_ROLES and assignment.coder_id != user:
        raise HTTPException(403, "独立复核期间不能访问其他标注员任务")
    return assignment


def _visibility(assignment: AnnotationAssignment, key: str) -> bool:
    return bool((assignment.evidence_config or {}).get(key, False))


def _pop_path(data: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    current: Any = data
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(part)
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def sample_duration(sample: DataRecord | dict[str, Any]) -> float | None:
    data = sample.clean_data if isinstance(sample, DataRecord) else sample
    candidates = [
        data.get("duration_seconds"), data.get("video_duration"), data.get("duration"),
        (data.get("platform_metadata") or {}).get("duration_seconds") if isinstance(data.get("platform_metadata"), dict) else None,
        ((data.get("platform_metadata") or {}).get("duration_sources") or {}).get("local_video")
        if isinstance((data.get("platform_metadata") or {}).get("duration_sources"), dict) else None,
    ]
    for value in candidates:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _redact_sample(data: dict[str, Any], assignment: AnnotationAssignment, dataset: DatasetVersion) -> dict[str, Any]:
    result = copy.deepcopy(data)
    mapping = dataset.project_config.get("visibility_fields", {}) if isinstance(dataset.project_config, dict) else {}
    if not _visibility(assignment, "title"):
        for key in mapping.get("title", ["title", "caption", "description", "video_title", "platform_metadata.title"]):
            _pop_path(result, key)
    if not _visibility(assignment, "metadata"):
        for key in mapping.get("metadata", ["account", "author", "published_at", "like_count", "comment_count", "share_count", "metrics", "platform_metadata", "source"]):
            _pop_path(result, key)
    duration = sample_duration(data)
    if duration is not None:
        result["duration_seconds"] = duration
    return result


@router.get("/projects/{project_id}/dataset-versions")
def dataset_versions(project_id: int, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")
    rows = db.scalars(select(DatasetVersion).where(DatasetVersion.project_id == project_id).order_by(DatasetVersion.id.desc())).all()
    return [{
        "id": row.id, "dataset_version": row.dataset_version, "digest": row.package_digest,
        "source_filename": row.source_filename, "sample_count": row.sample_count,
        "versions": row.versions, "frozen": row.frozen, "created_at": row.created_at,
    } for row in rows]


@router.get("/projects/{project_id}/samples")
def project_samples(
    project_id: int, dataset_version_id: int | None = None, page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=250), status: str = "", sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    user, role = identity
    dataset = db.get(DatasetVersion, dataset_version_id) if dataset_version_id else db.scalar(
        select(DatasetVersion).where(DatasetVersion.project_id == project_id).order_by(DatasetVersion.id.desc())
    )
    if not dataset or dataset.project_id != project_id:
        raise HTTPException(404, "数据版本不存在")
    primary = str(dataset.project_config["primary_table"])
    query = select(DataRecord, AnnotationAssignment).join(
        AnnotationAssignment, AnnotationAssignment.sample_record_id == DataRecord.id,
    ).where(DataRecord.dataset_version_id == dataset.id, DataRecord.table_name == primary)
    if role not in MANAGER_ROLES:
        query = query.where(AnnotationAssignment.coder_id == user)
    query = query.order_by(DataRecord.record_key.desc() if sort_order == "desc" else DataRecord.record_key)
    rows = db.execute(query).all()
    status_counts: dict[str, int] = {}
    for _, assignment in rows:
        status_counts[assignment.status] = status_counts.get(assignment.status, 0) + 1
    if status:
        rows = [(record, assignment) for record, assignment in rows if assignment.status == status]
    total = len(rows)
    rows = rows[(page - 1) * page_size: page * page_size]
    return {"items": [{
        "sample_record_id": record.id, "sample_id": record.record_key,
        "assignment_id": assignment.id, "coder_id": assignment.coder_id,
        "stage": assignment.stage, "experiment_group": assignment.experiment_group,
        "blind": assignment.blind, "status": assignment.status,
        "sample": _redact_sample(record.clean_data, assignment, dataset),
    } for record, assignment in rows], "page": page, "page_size": page_size, "total": total,
        "status_counts": status_counts}


def _related(db: Session, sample: DataRecord, table_name: str) -> list[DataRecord]:
    return list(db.scalars(select(DataRecord).where(
        DataRecord.dataset_version_id == sample.dataset_version_id,
        DataRecord.table_name == table_name, DataRecord.sample_key == sample.record_key,
    ).order_by(DataRecord.id)))


@router.get("/samples/{sample_record_id}")
def get_sample(
    sample_record_id: int, assignment_id: int | None = None,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    sample = db.get(DataRecord, sample_record_id)
    if not sample:
        raise HTTPException(404, "样本不存在")
    assignment = assignment_for(db, assignment_id, sample.id, identity)
    dataset = db.get(DatasetVersion, sample.dataset_version_id)
    return {
        "sample_record_id": sample.id, "sample_id": sample.record_key,
        "dataset_version_id": dataset.id, "project_id": dataset.project_id,
        "data": _redact_sample(sample.clean_data, assignment, dataset),
        "assignment_id": assignment.id, "evidence_config": assignment.evidence_config,
        "versions": dataset.versions,
    }


@router.get("/samples/{sample_record_id}/comments")
def sample_comments(
    sample_record_id: int, assignment_id: int | None = None,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    sample = db.get(DataRecord, sample_record_id)
    if not sample: raise HTTPException(404, "样本不存在")
    assignment = assignment_for(db, assignment_id, sample.id, identity)
    if not _visibility(assignment, "comments"):
        raise HTTPException(403, "该实验组未授权访问评论")
    rows = _related(db, sample, "comments")
    normalized = []
    for record in rows:
        row = copy.deepcopy(record.clean_data)
        row.setdefault("comment_id", record.record_key)
        row.setdefault("comment_type", row.get("comment_kind", "unknown"))
        normalized.append(row)
    return sorted(normalized, key=lambda row: row.get("rank_by_like", 10**9))


@router.get("/samples/{sample_record_id}/frames")
def sample_frames(
    sample_record_id: int, assignment_id: int | None = None,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    sample = db.get(DataRecord, sample_record_id)
    if not sample: raise HTTPException(404, "样本不存在")
    assignment = assignment_for(db, assignment_id, sample.id, identity)
    if not _visibility(assignment, "frames"):
        raise HTTPException(403, "该实验组未授权访问抽帧")
    rows = _related(db, sample, "frames")
    normalized = []
    for record in rows:
        row = copy.deepcopy(record.clean_data)
        row.setdefault("frame_id", record.record_key)
        row.setdefault("path", row.get("relative_path") or row.get("frame_path"))
        normalized.append(row)
    return sorted(normalized, key=lambda row: float(row.get("time_seconds", 0)))


@router.get("/samples/{sample_record_id}/frames/{frame_id}/media")
def frame_media(
    sample_record_id: int, frame_id: str, assignment_id: int | None = None,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    sample = db.get(DataRecord, sample_record_id)
    if not sample: raise HTTPException(404, "样本不存在")
    assignment = assignment_for(db, assignment_id, sample.id, identity)
    if not _visibility(assignment, "frames"): raise HTTPException(403, "该实验组未授权访问抽帧")
    frame = next((row for row in _related(db, sample, "frames") if str(row.clean_data.get("frame_id") or row.record_key) == frame_id), None)
    if not frame: raise HTTPException(404, "抽帧不存在")
    dataset = db.get(DatasetVersion, sample.dataset_version_id)
    if not dataset.media_root: raise HTTPException(404, "项目尚未绑定媒体根目录")
    relative = frame.clean_data.get("path") or frame.clean_data.get("frame_path") or frame.clean_data.get("relative_path")
    root = Path(dataset.media_root).resolve(); target = (root / Path(str(relative).replace("/", os.sep))).resolve()
    if root != target and root not in target.parents: raise HTTPException(403, "媒体路径超出项目授权目录")
    if not target.is_file(): raise HTTPException(404, "抽帧文件不存在")
    return FileResponse(target, media_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream")


def _media_path(db: Session, sample: DataRecord, asset_id: str | None, kind: str) -> tuple[Path, DatasetVersion]:
    dataset = db.get(DatasetVersion, sample.dataset_version_id)
    if not dataset.media_root:
        raise HTTPException(404, "项目尚未绑定媒体根目录")
    candidates = [sample.clean_data]
    for record in _related(db, sample, "assets"):
        row = record.clean_data
        nested = row.get("assets") if isinstance(row, dict) else None
        if isinstance(nested, list):
            candidates.extend(item for item in nested if isinstance(item, dict))
        elif isinstance(row, dict):
            candidates.append(row)
    selected: dict[str, Any] | None = None
    if asset_id:
        selected = next((row for row in candidates if str(row.get("asset_id") or row.get("id")) == asset_id), None)
    else:
        selected = next((row for row in candidates if str(row.get("type") or row.get("asset_type") or "").lower() in {kind, "video"}), None)
        selected = selected or next((row for row in candidates if any(key in row for key in ("video_path", "media_path", "path", "relative_path"))), None)
    if not selected:
        raise HTTPException(404, "样本没有对应媒体资产")
    relative = selected.get(f"{kind}_path") or selected.get("video_path") or selected.get("media_path") or selected.get("relative_path") or selected.get("path")
    if not isinstance(relative, str):
        raise HTTPException(404, "资产没有媒体相对路径")
    root = Path(dataset.media_root).resolve()
    target = (root / Path(relative.replace("/", os.sep))).resolve()
    if root != target and root not in target.parents:
        raise HTTPException(403, "媒体路径超出项目授权目录")
    if not target.is_file():
        raise HTTPException(404, "媒体文件不存在")
    return target, dataset


def _range_response(path: Path, request: Request) -> Response:
    size = path.stat().st_size
    range_header = request.headers.get("range")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not range_header:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})
    try:
        unit, value = range_header.split("=", 1)
        if unit != "bytes" or "," in value: raise ValueError
        start_text, end_text = value.split("-", 1)
        start = int(start_text) if start_text else max(0, size - int(end_text))
        end = min(int(end_text) if end_text else size - 1, size - 1)
        if start < 0 or start > end: raise ValueError
    except ValueError:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    with path.open("rb") as handle:
        handle.seek(start); content = handle.read(end - start + 1)
    return Response(content, status_code=206, media_type=media_type, headers={
        "Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes",
        "Content-Length": str(len(content)),
    })


@router.get("/samples/{sample_record_id}/media/video")
def sample_video(
    sample_record_id: int, request: Request, assignment_id: int | None = None,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    sample = db.get(DataRecord, sample_record_id)
    if not sample: raise HTTPException(404, "样本不存在")
    assignment = assignment_for(db, assignment_id, sample.id, identity)
    if not _visibility(assignment, "video"): raise HTTPException(403, "该实验组未授权访问视频")
    path, _ = _media_path(db, sample, None, "video")
    return _range_response(path, request)


@router.get("/samples/{sample_record_id}/assets/{asset_id}")
def sample_asset(
    sample_record_id: int, asset_id: str, request: Request, assignment_id: int | None = None,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    sample = db.get(DataRecord, sample_record_id)
    if not sample: raise HTTPException(404, "样本不存在")
    assignment_for(db, assignment_id, sample.id, identity)
    path, _ = _media_path(db, sample, asset_id, "asset")
    return _range_response(path, request)
