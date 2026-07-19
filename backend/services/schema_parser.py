from typing import Any

from fastapi import HTTPException


SUPPORTED_TYPES = {"string", "long_text", "number", "boolean", "enum", "multi_enum", "string_array", "object", "object_array"}


def child_fields(field: dict[str, Any]) -> list[dict[str, Any]]:
    properties = field.get("properties") or field.get("fields") or []
    if isinstance(properties, dict):
        return [{"key": key, **value} for key, value in properties.items()]
    if field.get("type") == "object_array" and isinstance(field.get("items"), dict):
        item = field["items"]
        properties = item.get("properties") or item.get("fields") or []
        if isinstance(properties, dict):
            return [{"key": key, **value} for key, value in properties.items()]
    return properties if isinstance(properties, list) else []


def validate_schema_config(schema: dict[str, Any]) -> None:
    if not schema.get("schema_id") or not schema.get("version") or not isinstance(schema.get("fields"), list):
        raise HTTPException(422, "Schema 必须包含 schema_id、version 和 fields")
    seen: set[str] = set()

    def walk(fields: list[dict[str, Any]], prefix: str = ""):
        for field in fields:
            key = field.get("key")
            path = f"{prefix}.{key}" if prefix else key
            if not key or path in seen:
                raise HTTPException(422, f"Schema 字段 key 为空或重复：{path}")
            seen.add(path)
            if field.get("type") not in SUPPORTED_TYPES:
                raise HTTPException(422, f"不支持的字段类型：{field.get('type')}")
            if field.get("type") in {"enum", "multi_enum"} and not field.get("options"):
                raise HTTPException(422, f"枚举字段缺少 options：{path}")
            if field.get("type") in {"object", "object_array"}:
                walk(child_fields(field), path)

    walk(schema["fields"])
    primary_key = schema.get("primary_key")
    if not primary_key:
        raise HTTPException(422, "Schema 必须声明 primary_key")
    if primary_key not in {field["key"] for field in schema["fields"]}:
        raise HTTPException(422, "primary_key 必须引用顶层字段")


def field_map(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def walk(fields: list[dict[str, Any]], prefix: str = ""):
        for field in fields:
            path = f"{prefix}.{field['key']}" if prefix else field["key"]
            result[path] = field
            if field["type"] in {"object", "object_array"}:
                walk(child_fields(field), path)

    walk(schema.get("fields", []))
    return result


def get_path(data: dict[str, Any], path: str, default=None):
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
