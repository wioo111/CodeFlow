import copy
import json
from typing import Any

from fastapi import HTTPException


def parse_json_data(content: bytes, filename: str) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "数据文件必须使用 UTF-8 编码") from exc
    try:
        if filename.lower().endswith(".jsonl"):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            payload = json.loads(text)
            rows = payload if isinstance(payload, list) else [payload]
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列") from exc
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise HTTPException(422, "数据文件必须包含一个或多个 JSON 对象")
    return [copy.deepcopy(row) for row in rows]


def parse_config(content: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"{label} 不是合法 UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(422, f"{label} 顶层必须是对象")
    return payload

