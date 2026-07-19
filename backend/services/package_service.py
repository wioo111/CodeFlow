from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import HTTPException
from jsonschema import SchemaError, validators


SUPPORTED_TYPES = {
    "string", "long_text", "number", "integer", "boolean", "enum", "multi_enum",
    "string_array", "object", "object_array", "time_point", "time_span",
    "asset_reference", "record_reference", "computed_readonly", "array", "null",
}


@dataclass
class ParsedPackage:
    manifest: dict[str, Any]
    schemas: dict[str, dict[str, Any]]
    tables: dict[str, list[dict[str, Any]]]
    table_specs: list[dict[str, Any]]
    digest: str
    dataset_version: str
    view: dict[str, Any]
    codebook: dict[str, Any]
    report: dict[str, Any]


def _safe_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise HTTPException(422, f"归档包含不安全路径：{name}")
    return str(path)


def _json(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"{label} 不是合法 UTF-8 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(422, f"{label} 顶层必须是对象")
    return value


def _jsonl(content: bytes, filename: str, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        errors.append({"file": filename, "line": 1, "field": None, "message": "文件必须使用 UTF-8"})
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("每行必须是 JSON 对象")
            rows.append(value)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append({"file": filename, "line": line_number, "field": None, "message": f"JSONL 解析失败：{exc}"})
    return rows


def _schema_types(schema: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for field in schema.get("fields", []):
        if isinstance(field, dict) and field.get("type"):
            result.add(str(field["type"]))
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("x-codeflow-type") or node.get("type")
            if isinstance(value, str):
                result.add(value)
            elif isinstance(value, list):
                result.update(str(item) for item in value)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(schema)
    return result


def _relative_path_errors(value: Any, trail: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{trail}.{key}" if trail else key
            key_lower = key.lower()
            if isinstance(child, str) and (key_lower == "path" or key_lower.endswith("_path") or key_lower in {"relative_path", "uri"}):
                normalized = child.replace("\\", "/")
                posix = PurePosixPath(normalized)
                if posix.is_absolute() or ".." in posix.parts or os.path.isabs(child):
                    found.append((path, child))
            else:
                found.extend(_relative_path_errors(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_relative_path_errors(child, f"{trail}.{index}"))
    return found


def parse_dataset_package(content: bytes, filename: str, media_root: str | None = None) -> ParsedPackage:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise HTTPException(422, "数据包必须是有效 ZIP 归档") from exc
    if sum(item.file_size for item in archive.infolist()) > 512 * 1024 * 1024:
        raise HTTPException(413, "解压后数据包不能超过 512 MB")
    files: dict[str, bytes] = {}
    for item in archive.infolist():
        if item.is_dir():
            continue
        safe = _safe_name(item.filename)
        files[safe] = archive.read(item)
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8")); digest.update(b"\0"); digest.update(files[name]); digest.update(b"\0")
    candidates = [name for name in files if name == "codeflow_project.json" or name.endswith("/codeflow_project.json")]
    if len(candidates) != 1:
        raise HTTPException(422, "数据包必须且只能包含一个 codeflow_project.json")
    manifest_name = candidates[0]
    base = str(PurePosixPath(manifest_name).parent)
    if base == ".":
        base = ""

    def locate(reference: str) -> str:
        safe = _safe_name(reference)
        candidates = [str(PurePosixPath(base) / safe) if base else safe, safe]
        for candidate in candidates:
            if candidate in files:
                return candidate
        return candidates[0]

    manifest = _json(files[manifest_name], manifest_name)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for field in ("project_id", "name", "primary_table", "primary_key", "tables"):
        if not manifest.get(field):
            errors.append({"file": manifest_name, "line": None, "field": field, "message": "项目描述缺少必填字段"})
    specs = manifest.get("tables") if isinstance(manifest.get("tables"), list) else []
    tables: dict[str, list[dict[str, Any]]] = {}
    schemas: dict[str, dict[str, Any]] = {}
    primary_keys: dict[str, set[str]] = {}
    for spec in specs:
        if not isinstance(spec, dict) or not spec.get("name") or not spec.get("file") or not spec.get("schema"):
            errors.append({"file": manifest_name, "line": None, "field": "tables", "message": "表声明缺少 name/file/schema"})
            continue
        table_name = str(spec["name"])
        data_name, schema_name = locate(str(spec["file"])), locate(str(spec["schema"]))
        for required in (data_name, schema_name):
            if required not in files:
                errors.append({"file": required, "line": None, "table": table_name, "field": None, "message": "声明文件不存在"})
        if data_name not in files or schema_name not in files:
            continue
        schema = _json(files[schema_name], schema_name)
        unsupported = sorted(_schema_types(schema) - SUPPORTED_TYPES)
        if unsupported:
            errors.append({"file": schema_name, "line": None, "table": table_name, "field": None, "message": f"不支持的字段类型：{', '.join(unsupported)}"})
        rows = _jsonl(files[data_name], data_name, errors)
        if "properties" in schema or "$schema" in schema:
            try:
                validator_class = validators.validator_for(schema)
                validator_class.check_schema(schema)
                validator = validator_class(schema)
                for line_number, row in enumerate(rows, 1):
                    for issue in sorted(validator.iter_errors(row), key=lambda item: list(item.path)):
                        field_path = ".".join(str(part) for part in issue.path) or "$"
                        errors.append({"file": data_name, "line": line_number, "table": table_name,
                                       "field": field_path, "message": f"Schema 校验失败：{issue.message}"})
            except SchemaError as exc:
                errors.append({"file": schema_name, "line": None, "table": table_name,
                               "field": ".".join(str(part) for part in exc.path) or "$",
                               "message": f"Schema 本身无效：{exc.message}"})
        pk = str(spec.get("primary_key") or (manifest.get("primary_key") if table_name == manifest.get("primary_table") else ""))
        if pk:
            seen: set[str] = set()
            for line_number, row in enumerate(rows, 1):
                value = row.get(pk)
                if value in (None, ""):
                    errors.append({"file": data_name, "line": line_number, "table": table_name, "field": pk, "message": "主键缺失"})
                elif str(value) in seen:
                    errors.append({"file": data_name, "line": line_number, "table": table_name, "field": pk, "message": f"主键重复：{value}"})
                else:
                    seen.add(str(value))
            primary_keys[table_name] = seen
        for line_number, row in enumerate(rows, 1):
            for field_path, unsafe in _relative_path_errors(row):
                errors.append({"file": data_name, "line": line_number, "table": table_name, "field": field_path, "message": f"媒体路径越界或为绝对路径：{unsafe}"})
        tables[table_name], schemas[table_name] = rows, schema

    primary_table = str(manifest.get("primary_table", ""))
    sample_ids = primary_keys.get(primary_table, set())
    for spec in specs:
        if not isinstance(spec, dict) or not spec.get("foreign_key") or spec.get("name") not in tables:
            continue
        table_name, fk = str(spec["name"]), str(spec["foreign_key"])
        for line_number, row in enumerate(tables[table_name], 1):
            if str(row.get(fk, "")) not in sample_ids:
                errors.append({"file": str(spec["file"]), "line": line_number, "table": table_name, "field": fk, "sample": row.get(fk), "message": "外键无法关联主表"})

    for config_key in ("annotation_schema", "review_schema"):
        reference = manifest.get(config_key)
        if isinstance(reference, str):
            resolved = locate(reference)
            if resolved not in files:
                errors.append({"file": resolved, "line": None, "field": config_key, "message": "配置 Schema 不存在"})
            else:
                schema = _json(files[resolved], resolved)
                unsupported = sorted(_schema_types(schema) - SUPPORTED_TYPES)
                if unsupported:
                    errors.append({"file": resolved, "line": None, "field": config_key, "message": f"不支持的字段类型：{', '.join(unsupported)}"})
                schemas[f"__{config_key}__"] = schema
        elif isinstance(reference, dict):
            schemas[f"__{config_key}__"] = reference

    media_path: str | None = None
    if media_root:
        root = Path(media_root).expanduser().resolve()
        if not root.is_dir():
            errors.append({"file": None, "line": None, "field": "media_root", "message": "媒体根目录不存在或不是目录"})
        else:
            media_path = str(root)
            for table_name, rows in tables.items():
                for line_number, row in enumerate(rows, 1):
                    for field_path, relative in _all_media_paths(row):
                        target = (root / Path(relative.replace("/", os.sep))).resolve()
                        if root != target and root not in target.parents:
                            errors.append({"file": table_name, "line": line_number, "table": table_name, "field": field_path, "message": "媒体路径逃逸授权目录"})
                        elif not target.exists():
                            warnings.append({"table": table_name, "line": line_number, "field": field_path, "message": f"媒体文件暂不可用：{relative}"})

    versions = manifest.get("versions", {}) if isinstance(manifest.get("versions"), dict) else {}
    dataset_version = str(manifest.get("dataset_version") or versions.get("dataset_version") or "v1")
    view, codebook = {}, {}
    for key, destination in (("view", "view"), ("view_config", "view"), ("codebook", "codebook")):
        reference = manifest.get(key)
        if isinstance(reference, str):
            resolved = locate(reference)
            if resolved in files:
                value = _json(files[resolved], resolved)
                if destination == "view": view = value
                else: codebook = value
            else:
                errors.append({"file": resolved, "line": None, "field": key, "message": "配置文件不存在"})
        elif isinstance(reference, dict):
            if destination == "view": view = reference
            else: codebook = reference

    report = {
        "valid": not errors, "errors": errors, "warnings": warnings,
        "project_id": manifest.get("project_id"), "dataset_version": dataset_version,
        "digest": digest.hexdigest(), "tables": {name: len(rows) for name, rows in tables.items()},
        "sample_count": len(tables.get(primary_table, [])), "media_root_bound": bool(media_path),
    }
    return ParsedPackage(manifest, schemas, tables, specs, digest.hexdigest(), dataset_version, view, codebook, report)


def _all_media_paths(value: Any, trail: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{trail}.{key}" if trail else key
            if isinstance(child, str) and (key.lower() == "path" or key.lower().endswith("_path") or key.lower() == "relative_path"):
                found.append((path, child))
            else:
                found.extend(_all_media_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_all_media_paths(child, f"{trail}.{index}"))
    return found
