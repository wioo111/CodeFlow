from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    schema_id: Mapped[str] = mapped_column(String(120), index=True)
    schema_version: Mapped[str] = mapped_column(String(80))
    schema_data: Mapped[dict] = mapped_column(JSON)
    view_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    batches: Mapped[list["Batch"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    data_version: Mapped[str] = mapped_column(String(80), default="v1")
    source_filename: Mapped[str] = mapped_column(String(260))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="batches")
    records: Mapped[list["Record"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    record_key: Mapped[str] = mapped_column(String(240), index=True)
    original_data: Mapped[dict] = mapped_column(JSON)
    current_data: Mapped[dict] = mapped_column(JSON)
    validation_status: Mapped[str] = mapped_column(String(30), default="valid", index=True)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    batch: Mapped[Batch] = relationship(back_populates="records")
    change_logs: Mapped[list["ChangeLog"]] = relationship(back_populates="record", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("batch_id", "record_key"),)


class ChangeLog(Base):
    __tablename__ = "change_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"), index=True)
    field_path: Mapped[str] = mapped_column(String(300))
    old_value: Mapped[object] = mapped_column(JSON, nullable=True)
    new_value: Mapped[object] = mapped_column(JSON, nullable=True)
    operator: Mapped[str] = mapped_column(String(120), default="local_reviewer")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    record: Mapped[Record] = relationship(back_populates="change_logs")


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    format: Mapped[str] = mapped_column(String(20))
    filter_condition: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str] = mapped_column(String(260), default="download")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Versioned research-package kernel. Existing single-table models stay intact
# so projects made with the first MVP remain readable.
class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    external_project_id: Mapped[str] = mapped_column(String(160), index=True)
    dataset_version: Mapped[str] = mapped_column(String(80), index=True)
    package_digest: Mapped[str] = mapped_column(String(64), index=True)
    source_filename: Mapped[str] = mapped_column(String(260))
    project_config: Mapped[dict] = mapped_column(JSON)
    schemas: Mapped[dict] = mapped_column(JSON, default=dict)
    view_config: Mapped[dict] = mapped_column(JSON, default=dict)
    codebook: Mapped[dict] = mapped_column(JSON, default=dict)
    versions: Mapped[dict] = mapped_column(JSON, default=dict)
    media_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_report: Mapped[dict] = mapped_column(JSON, default=dict)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "dataset_version", "package_digest"),)


class DataTable(Base):
    __tablename__ = "data_tables"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    primary_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    foreign_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    relation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schema_data: Mapped[dict] = mapped_column(JSON, default=dict)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("dataset_version_id", "name"),)


class DataRecord(Base):
    __tablename__ = "data_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("data_tables.id"), index=True)
    table_name: Mapped[str] = mapped_column(String(120), index=True)
    record_key: Mapped[str] = mapped_column(String(240), index=True)
    sample_key: Mapped[str | None] = mapped_column(String(240), index=True, nullable=True)
    clean_data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("dataset_version_id", "table_name", "record_key"),)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    model_version: Mapped[str] = mapped_column(String(120), default="unknown")
    prompt_version: Mapped[str] = mapped_column(String(120), default="unknown")
    input_modalities: Mapped[dict] = mapped_column(JSON, default=dict)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    output_digest: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIRawAnnotation(Base):
    __tablename__ = "ai_raw_annotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_record_id: Mapped[int] = mapped_column(ForeignKey("data_records.id"), index=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id"), index=True)
    raw_output: Mapped[dict] = mapped_column(JSON)
    parse_status: Mapped[str] = mapped_column(String(40), default="valid")
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("sample_record_id", "model_run_id"),)


class AnnotationAssignment(Base):
    __tablename__ = "annotation_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    sample_record_id: Mapped[int] = mapped_column(ForeignKey("data_records.id"), index=True)
    coder_id: Mapped[str] = mapped_column(String(120), index=True)
    stage: Mapped[str] = mapped_column(String(80), default="pilot_independent_review", index=True)
    experiment_group: Mapped[str] = mapped_column(String(120), default="default")
    blind: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("sample_record_id", "coder_id", "stage", "experiment_group"),)


class HumanAnnotation(Base):
    __tablename__ = "human_annotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("annotation_assignments.id"), unique=True, index=True)
    ai_raw_annotation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_raw_annotations.id"), nullable=True)
    current_data: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    field_decisions: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_spans: Mapped[list] = mapped_column(JSON, default=list)
    versions: Mapped[dict] = mapped_column(JSON, default=dict)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResearchChangeLog(Base):
    __tablename__ = "research_change_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("annotation_assignments.id"), index=True)
    operator: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(80))
    field_path: Mapped[str] = mapped_column(String(300))
    old_value: Mapped[object] = mapped_column(JSON, nullable=True)
    new_value: Mapped[object] = mapped_column(JSON, nullable=True)
    change_type: Mapped[str] = mapped_column(String(40), default="edit")
    reason: Mapped[str] = mapped_column(Text, default="")
    versions: Mapped[dict] = mapped_column(JSON, default=dict)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Adjudication(Base):
    __tablename__ = "adjudications"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    sample_record_id: Mapped[int] = mapped_column(ForeignKey("data_records.id"), index=True)
    assignment_ids: Mapped[list] = mapped_column(JSON, default=list)
    differences: Mapped[dict] = mapped_column(JSON, default=dict)
    resolution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    adjudicator_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GoldAnnotation(Base):
    __tablename__ = "gold_annotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    sample_record_id: Mapped[int] = mapped_column(ForeignKey("data_records.id"), index=True)
    gold_version: Mapped[str] = mapped_column(String(80), index=True)
    annotation_data: Mapped[dict] = mapped_column(JSON)
    source_adjudication_id: Mapped[int | None] = mapped_column(ForeignKey("adjudications.id"), nullable=True)
    frozen_by: Mapped[str] = mapped_column(String(120))
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "sample_record_id", "gold_version"),)
