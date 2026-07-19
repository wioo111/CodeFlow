from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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

