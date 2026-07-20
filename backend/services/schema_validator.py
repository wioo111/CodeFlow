from typing import Any

from .schema_parser import child_fields, get_path


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def validate_record(schema: dict[str, Any], data: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def error(path: str, message: str, code: str):
        errors.append({"path": path, "message": message, "code": code})

    def validate_fields(fields: list[dict[str, Any]], container: Any, prefix: str = ""):
        if not isinstance(container, dict):
            error(prefix or "$", "应为对象", "type")
            return
        for field in fields:
            key = field["key"]
            path = f"{prefix}.{key}" if prefix else key
            value = container.get(key)
            required_when = field.get("required_when")
            required = bool(field.get("required"))
            if required_when:
                expected = required_when.get("equals", required_when.get("value"))
                required = required or get_path(data, required_when.get("field", "")) == expected
            if required and _empty(value):
                error(path, "必填字段不能为空", "required")
                continue
            if _empty(value):
                continue
            kind = field["type"]
            if kind in {"string", "long_text", "asset_reference", "record_reference", "computed_readonly"}:
                if not isinstance(value, str): error(path, "应为字符串", "type")
                elif field.get("min_length") is not None and len(value) < field["min_length"]: error(path, f"长度不能小于 {field['min_length']}", "min_length")
                elif field.get("max_length") is not None and len(value) > field["max_length"]: error(path, f"长度不能大于 {field['max_length']}", "max_length")
            elif kind in {"number", "integer", "time_point"}:
                if not isinstance(value, (int, float)) or isinstance(value, bool): error(path, "应为数字", "type")
                elif kind == "integer" and not isinstance(value, int): error(path, "应为整数", "type")
                elif field.get("min") is not None and value < field["min"]: error(path, f"不能小于 {field['min']}", "minimum")
                elif field.get("max") is not None and value > field["max"]: error(path, f"不能大于 {field['max']}", "maximum")
            elif kind == "boolean" and not isinstance(value, bool): error(path, "应为布尔值", "type")
            elif kind == "enum":
                allowed = {option["value"] for option in field.get("options", [])}
                if value not in allowed: error(path, "不在允许的枚举选项中", "enum")
            elif kind == "multi_enum":
                allowed = {option["value"] for option in field.get("options", [])}
                if not isinstance(value, list): error(path, "应为数组", "type")
                elif not set(value).issubset(allowed): error(path, "包含无效的枚举选项", "enum")
            elif kind == "string_array" and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)): error(path, "应为字符串数组", "type")
            elif kind == "object": validate_fields(child_fields(field), value, path)
            elif kind == "object_array":
                if not isinstance(value, list): error(path, "应为对象数组", "type")
                else:
                    for index, item in enumerate(value): validate_fields(child_fields(field), item, f"{path}.{index}")
            elif kind == "time_span":
                if not isinstance(value, dict): error(path, "时间区间应为对象", "type")
                else:
                    start, end = value.get("start"), value.get("end")
                    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)): error(path, "时间区间必须包含数字 start/end", "type")
                    elif start < 0 or start >= end: error(path, "开始时间必须非负且小于结束时间", "time_span")

    validate_fields(schema.get("fields", []), data)
    for rule in schema.get("rules", []):
        condition = rule.get("if", {})
        if get_path(data, condition.get("field", "")) == condition.get("equals"):
            for path in rule.get("then_required", []):
                if _empty(get_path(data, path)):
                    error(path, rule.get("message", "满足条件时此字段必填"), "conditional_required")
    for rule in schema.get("relations", []):
        if rule.get("type") == "less_than":
            left, right = get_path(data, rule["left"]), get_path(data, rule["right"])
            if left is not None and right is not None and left >= right:
                error(rule["left"], rule.get("message", f"必须小于 {rule['right']}"), "relation")
    return errors
