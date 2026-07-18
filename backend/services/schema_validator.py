from typing import Any

from fastapi import HTTPException


SUPPORTED_TYPES = {"short_text", "long_text", "single_select", "multi_select", "boolean", "number", "scale"}


def validate_schema(schema: dict[str, Any]) -> None:
    if not schema.get("version") or not isinstance(schema.get("fields"), list):
        raise HTTPException(422, "Schema 必须包含 version 和 fields")
    seen: set[str] = set()
    for field in schema["fields"]:
        field_id = field.get("id")
        if not field_id or field_id in seen:
            raise HTTPException(422, "Schema 字段 id 不能为空或重复")
        seen.add(field_id)
        if field.get("type") not in SUPPORTED_TYPES:
            raise HTTPException(422, f"不支持的字段类型：{field.get('type')}")


def validate_annotation(schema: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in schema["fields"]:
        field_id = field["id"]
        value = data.get(field_id)
        empty = value is None or value == "" or value == []
        if field.get("required") and empty:
            raise HTTPException(422, f"“{field.get('label', field_id)}”为必填项")
        if empty:
            normalized[field_id] = None if value != [] else []
            continue
        field_type = field["type"]
        options = {item["value"] for item in field.get("options", [])}
        if field_type == "single_select" and value not in options:
            raise HTTPException(422, f"字段 {field_id} 的选项无效")
        if field_type == "multi_select" and (not isinstance(value, list) or not set(value).issubset(options)):
            raise HTTPException(422, f"字段 {field_id} 的选项无效")
        if field_type == "boolean" and not isinstance(value, bool):
            raise HTTPException(422, f"字段 {field_id} 必须为布尔值")
        if field_type in {"number", "scale"} and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise HTTPException(422, f"字段 {field_id} 必须为数字")
        normalized[field_id] = value
    return normalized

