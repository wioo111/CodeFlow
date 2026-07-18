from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    schema_version: Mapped[str] = mapped_column(String(80))
    codebook_version: Mapped[str] = mapped_column(String(80), default="v0.1")
    status: Mapped[str] = mapped_column(String(30), default="active")
    schema_data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    material_type: Mapped[str] = mapped_column(String(40))
    material_data: Mapped[dict] = mapped_column(JSON)
    metadata_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Coder(Base):
    __tablename__ = "coders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), default="coder")
    status: Mapped[str] = mapped_column(String(30), default="active")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    coder_id: Mapped[int] = mapped_column(ForeignKey("coders.id"), index=True)
    stage: Mapped[str] = mapped_column(String(30), default="coding")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    material: Mapped[Material] = relationship()
    coder: Mapped[Coder] = relationship()
    annotation: Mapped["Annotation | None"] = relationship(back_populates="assignment", uselist=False)

    __table_args__ = (UniqueConstraint("material_id", "coder_id", "stage"),)


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(80))
    codebook_version: Mapped[str] = mapped_column(String(80))
    annotation_data: Mapped[dict] = mapped_column(JSON, default=dict)
    is_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    assignment: Mapped[Assignment] = relationship(back_populates="annotation")

