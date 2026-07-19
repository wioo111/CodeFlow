from typing import Any


MISSING = object()


def flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict): result.update(flatten(value, path))
            else: result[path] = value
        return result
    return {prefix: data}


def differences(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    left, right = flatten(old), flatten(new)
    result = []
    for path in sorted(set(left) | set(right)):
        old_value, new_value = left.get(path, MISSING), right.get(path, MISSING)
        if old_value != new_value:
            result.append({"field_path": path, "old_value": None if old_value is MISSING else old_value, "new_value": None if new_value is MISSING else new_value})
    return result

