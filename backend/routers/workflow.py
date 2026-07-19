from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    AIRawAnnotation, Adjudication, AnnotationAssignment, DataRecord, DatasetVersion,
    GoldAnnotation, HumanAnnotation, ModelRun, Project, ResearchChangeLog,
)
from backend.routers.research import MANAGER_ROLES, assignment_for, current_identity
from backend.services.diff_service import differences
from backend.services.schema_validator import validate_record


router = APIRouter(tags=["annotation workflow"])
DECISIONS = {"accept", "minor_edit", "major_edit", "delete", "supplement", "unverifiable", "hallucination", "key_detail_missing"}


class DraftUpdate(BaseModel):
    annotation: dict[str, Any] = Field(default_factory=dict)
    field_decisions: dict[str, str] = Field(default_factory=dict)
    evidence_spans: list[dict[str, Any]] = Field(default_factory=list)
    active_seconds: float = Field(0, ge=0)
    reason: str = ""


class ModelRunImport(BaseModel):
    project_id: int
    name: str
    model_version: str = "unknown"
    prompt_version: str = "unknown"
    input_modalities: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    annotations: list[dict[str, Any]] = Field(min_length=1)


class AdjudicationResolution(BaseModel):
    resolution: dict[str, Any]
    rationale: str = Field(min_length=1)


class GoldFreezeRequest(BaseModel):
    gold_version: str = Field(min_length=1, max_length=80)


class AssignmentCreate(BaseModel):
    dataset_version_id: int
    sample_ids: list[str] = Field(default_factory=list)
    coder_ids: list[str] = Field(min_length=1)
    stage: str = "pilot_independent_review"
    experiment_group: str = "default"
    blind: bool = False
    evidence_config: dict[str, bool] = Field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_role(identity: tuple[str, str], roles: set[str]) -> None:
    if identity[1] not in roles:
        raise HTTPException(403, "当前角色无权执行此操作")


def _span_errors(spans: list[dict[str, Any]], duration: float | None) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    primary_count = 0
    for index, span in enumerate(spans):
        if span.get("unlocatable"):
            continue
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            errors.append({"path": f"evidence_spans.{index}", "message": "区间必须包含数字 start/end", "code": "type"})
        elif start < 0 or start >= end:
            errors.append({"path": f"evidence_spans.{index}", "message": "开始时间必须非负且小于结束时间", "code": "time_span"})
        elif duration is not None and end > duration:
            errors.append({"path": f"evidence_spans.{index}.end", "message": f"结束时间不能超过视频时长 {duration}", "code": "duration"})
        primary_count += int(bool(span.get("primary")))
    if primary_count > 1:
        errors.append({"path": "evidence_spans", "message": "最多只能指定一个主区间", "code": "primary"})
    return errors


def _duration(sample: DataRecord) -> float | None:
    for key in ("duration_seconds", "video_duration", "duration"):
        value = sample.clean_data.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _assignment_view(db: Session, assignment: AnnotationAssignment, identity: tuple[str, str]) -> dict[str, Any]:
    sample = db.get(DataRecord, assignment.sample_record_id)
    dataset = db.get(DatasetVersion, assignment.dataset_version_id)
    human = db.scalar(select(HumanAnnotation).where(HumanAnnotation.assignment_id == assignment.id))
    ai = None
    if (assignment.evidence_config or {}).get("ai_suggestion", False) and not assignment.blind:
        ai = db.scalar(select(AIRawAnnotation).where(AIRawAnnotation.sample_record_id == sample.id).order_by(AIRawAnnotation.id.desc()))
    logs = db.scalars(select(ResearchChangeLog).where(ResearchChangeLog.assignment_id == assignment.id).order_by(ResearchChangeLog.id.desc())).all()
    return {
        "id": assignment.id, "project_id": assignment.project_id, "dataset_version_id": assignment.dataset_version_id,
        "sample_record_id": sample.id, "sample_id": sample.record_key, "coder_id": assignment.coder_id,
        "stage": assignment.stage, "experiment_group": assignment.experiment_group, "blind": assignment.blind,
        "evidence_config": assignment.evidence_config, "status": assignment.status,
        "started_at": assignment.started_at, "first_saved_at": assignment.first_saved_at,
        "submitted_at": assignment.submitted_at, "active_seconds": assignment.active_seconds,
        "human_annotation": {
            "current_data": human.current_data, "submitted_data": human.submitted_data,
            "field_decisions": human.field_decisions, "evidence_spans": human.evidence_spans,
            "versions": human.versions, "locked": human.locked,
        },
        "ai_raw_annotation": None if not ai else {
            "id": ai.id, "model_run_id": ai.model_run_id, "raw_output": ai.raw_output,
            "parse_status": ai.parse_status, "validation_errors": ai.validation_errors, "immutable": ai.immutable,
        },
        "annotation_schema": dataset.schemas.get("__resolved_annotation_schema__", db.get(Project, assignment.project_id).schema_data),
        "view_config": dataset.view_config or db.get(Project, assignment.project_id).view_config,
        "codebook": dataset.codebook, "versions": dataset.versions,
        "change_logs": [{
            "id": log.id, "field_path": log.field_path, "old_value": log.old_value,
            "new_value": log.new_value, "change_type": log.change_type, "operator": log.operator,
            "stage": log.stage, "reason": log.reason, "versions": log.versions, "changed_at": log.changed_at,
        } for log in logs],
    }


@router.get("/assignments/next")
def next_assignment(
    project_id: int | None = None, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    user, role = identity
    query = select(AnnotationAssignment).where(AnnotationAssignment.status.in_(["pending", "in_progress"]))
    if project_id: query = query.where(AnnotationAssignment.project_id == project_id)
    if role not in MANAGER_ROLES: query = query.where(AnnotationAssignment.coder_id == user)
    assignment = db.scalar(query.order_by(AnnotationAssignment.status.desc(), AnnotationAssignment.id))
    if not assignment: raise HTTPException(404, "没有待处理任务")
    if not assignment.started_at:
        assignment.started_at, assignment.status = _now(), "in_progress"; db.commit()
    return _assignment_view(db, assignment, identity)


@router.post("/projects/{project_id}/assignments", status_code=201)
def create_assignments(
    project_id: int, payload: AssignmentCreate,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    _require_role(identity, {"admin", "research_manager"})
    dataset = db.get(DatasetVersion, payload.dataset_version_id)
    if not dataset or dataset.project_id != project_id: raise HTTPException(404, "数据版本不存在")
    primary_table = str(dataset.project_config["primary_table"])
    query = select(DataRecord).where(DataRecord.dataset_version_id == dataset.id, DataRecord.table_name == primary_table)
    if payload.sample_ids: query = query.where(DataRecord.record_key.in_(payload.sample_ids))
    samples = db.scalars(query.order_by(DataRecord.id)).all()
    if payload.sample_ids and len(samples) != len(set(payload.sample_ids)): raise HTTPException(422, "部分 sample_id 不存在")
    created, existing = [], []
    evidence = payload.evidence_config or {"video": True, "frames": True, "title": True, "comments": True, "metadata": True, "ai_suggestion": not payload.blind}
    if payload.blind: evidence["ai_suggestion"] = False
    for sample in samples:
        for coder_id in payload.coder_ids:
            found = db.scalar(select(AnnotationAssignment).where(
                AnnotationAssignment.sample_record_id == sample.id, AnnotationAssignment.coder_id == coder_id,
                AnnotationAssignment.stage == payload.stage, AnnotationAssignment.experiment_group == payload.experiment_group,
            ))
            if found: existing.append(found.id); continue
            assignment = AnnotationAssignment(
                project_id=project_id, dataset_version_id=dataset.id, sample_record_id=sample.id,
                coder_id=coder_id, stage=payload.stage, experiment_group=payload.experiment_group,
                blind=payload.blind, evidence_config=copy.deepcopy(evidence),
            )
            db.add(assignment); db.flush()
            db.add(HumanAnnotation(assignment_id=assignment.id, current_data={}, versions=copy.deepcopy(dataset.versions)))
            created.append(assignment.id)
    db.commit()
    return {"created": created, "existing": existing, "count": len(created)}


@router.get("/assignments/{assignment_id}")
def get_assignment(
    assignment_id: int, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    assignment = db.get(AnnotationAssignment, assignment_id)
    if not assignment: raise HTTPException(404, "标注任务不存在")
    assignment_for(db, assignment.id, assignment.sample_record_id, identity)
    return _assignment_view(db, assignment, identity)


def _save_draft(db: Session, assignment: AnnotationAssignment, payload: DraftUpdate) -> tuple[HumanAnnotation, list[dict[str, str]]]:
    human = db.scalar(select(HumanAnnotation).where(HumanAnnotation.assignment_id == assignment.id))
    if not human: raise HTTPException(500, "标注记录缺失")
    if human.locked: raise HTTPException(409, "结果已提交锁定，需要管理员重开")
    invalid_decisions = sorted(set(payload.field_decisions.values()) - DECISIONS)
    if invalid_decisions: raise HTTPException(422, f"不支持的字段决策：{', '.join(invalid_decisions)}")
    sample = db.get(DataRecord, assignment.sample_record_id)
    project = db.get(Project, assignment.project_id)
    errors = validate_record(project.schema_data, payload.annotation) + _span_errors(payload.evidence_spans, _duration(sample))
    for change in differences(human.current_data or {}, payload.annotation):
        db.add(ResearchChangeLog(
            assignment_id=assignment.id, operator=assignment.coder_id, stage=assignment.stage,
            field_path=change["field_path"], old_value=change["old_value"], new_value=change["new_value"],
            change_type=payload.field_decisions.get(change["field_path"], "edit"), reason=payload.reason,
            versions=copy.deepcopy(human.versions),
        ))
    if human.evidence_spans != payload.evidence_spans:
        db.add(ResearchChangeLog(
            assignment_id=assignment.id, operator=assignment.coder_id, stage=assignment.stage,
            field_path="evidence_spans", old_value=human.evidence_spans, new_value=payload.evidence_spans,
            change_type=payload.field_decisions.get("evidence_spans", "edit"), reason=payload.reason,
            versions={**human.versions, "video_duration_version": str(_duration(sample) or "unknown")},
        ))
    human.current_data = copy.deepcopy(payload.annotation)
    human.field_decisions = copy.deepcopy(payload.field_decisions)
    human.evidence_spans = copy.deepcopy(payload.evidence_spans)
    assignment.active_seconds += payload.active_seconds
    assignment.status = "in_progress"
    assignment.started_at = assignment.started_at or _now()
    assignment.first_saved_at = assignment.first_saved_at or _now()
    db.commit()
    return human, errors


@router.patch("/assignments/{assignment_id}/draft")
def update_draft(
    assignment_id: int, payload: DraftUpdate, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    assignment = db.get(AnnotationAssignment, assignment_id)
    if not assignment: raise HTTPException(404, "标注任务不存在")
    assignment_for(db, assignment.id, assignment.sample_record_id, identity)
    human, errors = _save_draft(db, assignment, payload)
    return {"status": assignment.status, "locked": human.locked, "validation_errors": errors, "saved_at": human.updated_at}


@router.post("/assignments/{assignment_id}/submit")
def submit_assignment(
    assignment_id: int, payload: DraftUpdate, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    assignment = db.get(AnnotationAssignment, assignment_id)
    if not assignment: raise HTTPException(404, "标注任务不存在")
    assignment_for(db, assignment.id, assignment.sample_record_id, identity)
    human = db.scalar(select(HumanAnnotation).where(HumanAnnotation.assignment_id == assignment.id))
    if human.locked:
        return {"status": "submitted", "locked": True, "submitted_at": assignment.submitted_at, "idempotent": True}
    human, errors = _save_draft(db, assignment, payload)
    if errors: raise HTTPException(422, {"message": "提交前完整性检查失败", "errors": errors})
    human.submitted_data = copy.deepcopy(human.current_data); human.locked = True
    assignment.status, assignment.submitted_at = "submitted", _now()
    db.commit()
    return {"status": assignment.status, "locked": True, "submitted_at": assignment.submitted_at, "idempotent": False}


@router.post("/assignments/{assignment_id}/reopen")
def reopen_assignment(
    assignment_id: int, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    _require_role(identity, {"admin", "research_manager"})
    assignment = db.get(AnnotationAssignment, assignment_id)
    if not assignment: raise HTTPException(404, "标注任务不存在")
    human = db.scalar(select(HumanAnnotation).where(HumanAnnotation.assignment_id == assignment.id))
    human.locked = False; assignment.status = "in_progress"; db.commit()
    return {"status": assignment.status, "locked": False}


@router.post("/model-runs/import", status_code=201)
def import_model_run(payload: ModelRunImport, db: Session = Depends(get_db)):
    project = db.get(Project, payload.project_id)
    if not project: raise HTTPException(404, "项目不存在")
    encoded = json.dumps(payload.annotations, ensure_ascii=False, sort_keys=True).encode()
    run = ModelRun(
        project_id=project.id, name=payload.name, model_version=payload.model_version,
        prompt_version=payload.prompt_version, input_modalities=payload.input_modalities,
        parameters=payload.parameters, output_digest=hashlib.sha256(encoded).hexdigest(),
    )
    db.add(run); db.flush()
    imported = 0
    for index, item in enumerate(payload.annotations, 1):
        sample_id = item.get("sample_id")
        output = item.get("annotation") or item.get("raw_output")
        if not sample_id or not isinstance(output, dict):
            db.rollback(); raise HTTPException(422, f"第 {index} 条 AI 结果缺少 sample_id 或 annotation")
        candidates = db.scalars(select(DataRecord).join(
            DatasetVersion, DatasetVersion.id == DataRecord.dataset_version_id,
        ).where(
            DatasetVersion.project_id == project.id, DataRecord.record_key == str(sample_id),
        ).order_by(DataRecord.id.desc())).all()
        sample = next((candidate for candidate in candidates if candidate.table_name == db.get(
            DatasetVersion, candidate.dataset_version_id,
        ).project_config["primary_table"]), None)
        if not sample:
            db.rollback(); raise HTTPException(422, f"AI 结果引用不存在样本：{sample_id}")
        validation_errors = validate_record(project.schema_data, output)
        db.add(AIRawAnnotation(
            sample_record_id=sample.id, model_run_id=run.id, raw_output=copy.deepcopy(output),
            parse_status="invalid" if validation_errors else "valid", validation_errors=validation_errors,
        ))
        imported += 1
    db.commit()
    return {"model_run_id": run.id, "imported": imported, "digest": run.output_digest}


@router.post("/projects/{project_id}/adjudications/prepare", status_code=201)
def prepare_adjudications(
    project_id: int, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    _require_role(identity, {"admin", "research_manager", "adjudicator"})
    assignments = db.scalars(select(AnnotationAssignment).where(
        AnnotationAssignment.project_id == project_id, AnnotationAssignment.status == "submitted",
    ).order_by(AnnotationAssignment.sample_record_id, AnnotationAssignment.id)).all()
    grouped: dict[int, list[AnnotationAssignment]] = {}
    for item in assignments: grouped.setdefault(item.sample_record_id, []).append(item)
    created: list[int] = []
    for sample_id, group in grouped.items():
        if len(group) < 2: continue
        existing = db.scalar(select(Adjudication).where(Adjudication.project_id == project_id, Adjudication.sample_record_id == sample_id))
        if existing: continue
        annotations = [db.scalar(select(HumanAnnotation).where(HumanAnnotation.assignment_id == item.id)).submitted_data for item in group]
        all_changes: dict[str, list[Any]] = {}
        for index in range(1, len(annotations)):
            for change in differences(annotations[0] or {}, annotations[index] or {}):
                all_changes.setdefault(change["field_path"], [change["old_value"]]).append(change["new_value"])
        adjudication = Adjudication(
            project_id=project_id, dataset_version_id=group[0].dataset_version_id, sample_record_id=sample_id,
            assignment_ids=[item.id for item in group], differences=all_changes,
        )
        db.add(adjudication); db.flush(); created.append(adjudication.id)
    db.commit()
    return {"created": created, "count": len(created)}


@router.get("/adjudications/{adjudication_id}")
def get_adjudication(
    adjudication_id: int, identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    _require_role(identity, {"admin", "research_manager", "adjudicator", "viewer"})
    item = db.get(Adjudication, adjudication_id)
    if not item: raise HTTPException(404, "仲裁任务不存在")
    human_rows = []
    for assignment_id in item.assignment_ids:
        assignment = db.get(AnnotationAssignment, assignment_id)
        human = db.scalar(select(HumanAnnotation).where(HumanAnnotation.assignment_id == assignment_id))
        human_rows.append({"assignment_id": assignment_id, "coder_id": assignment.coder_id, "annotation": human.submitted_data, "evidence_spans": human.evidence_spans})
    ai = db.scalar(select(AIRawAnnotation).where(AIRawAnnotation.sample_record_id == item.sample_record_id).order_by(AIRawAnnotation.id.desc()))
    return {"id": item.id, "sample_record_id": item.sample_record_id, "status": item.status, "differences": item.differences,
            "human_annotations": human_rows, "ai_raw_annotation": ai.raw_output if ai else None,
            "resolution": item.resolution, "rationale": item.rationale}


@router.post("/adjudications/{adjudication_id}/resolve")
def resolve_adjudication(
    adjudication_id: int, payload: AdjudicationResolution,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    _require_role(identity, {"admin", "research_manager", "adjudicator"})
    item = db.get(Adjudication, adjudication_id)
    if not item: raise HTTPException(404, "仲裁任务不存在")
    item.resolution = copy.deepcopy(payload.resolution); item.rationale = payload.rationale
    item.adjudicator_id = identity[0]; item.status = "resolved"; item.resolved_at = _now(); db.commit()
    return {"id": item.id, "status": item.status, "resolved_at": item.resolved_at}


@router.post("/gold/{project_id}/freeze", status_code=201)
def freeze_gold(
    project_id: int, payload: GoldFreezeRequest,
    identity: tuple[str, str] = Depends(current_identity), db: Session = Depends(get_db),
):
    _require_role(identity, {"admin", "research_manager"})
    resolved = db.scalars(select(Adjudication).where(Adjudication.project_id == project_id, Adjudication.status == "resolved")).all()
    if not resolved: raise HTTPException(422, "没有已确认的仲裁结果可冻结")
    if db.scalar(select(GoldAnnotation.id).where(GoldAnnotation.project_id == project_id, GoldAnnotation.gold_version == payload.gold_version)):
        raise HTTPException(409, "Gold 版本已存在且不可覆盖")
    for item in resolved:
        db.add(GoldAnnotation(
            project_id=project_id, dataset_version_id=item.dataset_version_id, sample_record_id=item.sample_record_id,
            gold_version=payload.gold_version, annotation_data=copy.deepcopy(item.resolution),
            source_adjudication_id=item.id, frozen_by=identity[0],
        ))
    db.commit()
    return {"gold_version": payload.gold_version, "frozen": len(resolved)}


@router.get("/metrics/annotation-quality")
def annotation_quality(project_id: int, db: Session = Depends(get_db)):
    assignments = db.scalars(select(AnnotationAssignment).where(AnnotationAssignment.project_id == project_id)).all()
    ids = [item.id for item in assignments]
    humans = db.scalars(select(HumanAnnotation).where(HumanAnnotation.assignment_id.in_(ids))).all() if ids else []
    counts = {key: 0 for key in sorted(DECISIONS)}
    total = 0
    for human in humans:
        for decision in (human.field_decisions or {}).values():
            if decision in counts: counts[decision] += 1; total += 1
    return {"project_id": project_id, "field_decisions": counts,
            "rates": {key: (value / total if total else 0) for key, value in counts.items()},
            "assignments": len(assignments), "submitted": sum(item.status == "submitted" for item in assignments)}
