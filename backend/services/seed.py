import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Assignment, Coder, Material, Project


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "project_templates" / "football"


def seed_database(db: Session) -> None:
    if db.scalar(select(Project.id).limit(1)):
        return
    project_info = json.loads((TEMPLATE_DIR / "project.json").read_text(encoding="utf-8"))
    schema = json.loads((TEMPLATE_DIR / "schema_v0.1.json").read_text(encoding="utf-8"))
    materials = json.loads((TEMPLATE_DIR / "mock_materials.json").read_text(encoding="utf-8"))
    project = Project(**project_info, schema_version=schema["version"], schema_data=schema)
    coder = Coder(name="演示编码员", role="coder", status="active")
    db.add_all([project, coder])
    db.flush()
    for item in materials:
        material = Material(project_id=project.id, **item)
        db.add(material)
        db.flush()
        db.add(Assignment(project_id=project.id, material_id=material.id, coder_id=coder.id))
    db.commit()

