# CodeFlow 标准数据包协议

## 入口与目录

ZIP 中必须且只能有一个 `codeflow_project.json`。入口可位于根目录或 `clean/`；其余相对引用以入口所在目录为基准。

```text
clean/
├── codeflow_project.json
├── samples.jsonl
├── comments.jsonl
├── frames.jsonl
├── assets.jsonl
├── view.json
├── codebook.json
└── schemas/
    ├── sample_schema.json
    ├── comment_schema.json
    ├── frame_schema.json
    ├── asset_schema.json
    └── annotation_schema.json
```

## 项目描述

```json
{
  "protocol_version": "1.0",
  "project_id": "research_project",
  "name": "研究项目",
  "dataset_version": "2026.07",
  "primary_table": "samples",
  "primary_key": "sample_id",
  "annotation_schema": "schemas/annotation_schema.json",
  "view": "view.json",
  "codebook": "codebook.json",
  "versions": {
    "sample_schema_version": "1.0",
    "annotation_schema_version": "1.1",
    "view_version": "1.0",
    "codebook_version": "0.1",
    "prompt_version": "p1",
    "frame_set_version": "f1"
  },
  "tables": [
    {"name": "samples", "file": "samples.jsonl", "schema": "schemas/sample_schema.json", "primary_key": "sample_id"},
    {"name": "comments", "file": "comments.jsonl", "schema": "schemas/comment_schema.json", "primary_key": "comment_id", "foreign_key": "sample_id", "relation": "one_to_many"}
  ]
}
```

`tables` 没有固定名称限制。新增 `asr_segments`、`ocr_segments`、`football_context`、`candidate_segments` 或其他表不需要修改数据库模型。

## Schema 与 View

表 Schema 支持 JSON Schema；人工标注 Schema 也支持 CodeFlow 简化格式：

```json
{"schema_id":"example","version":"1.0","primary_key":"sample_id","fields":[{"key":"label","label":"标签","type":"enum","required":true,"options":[{"value":"a","label":"A"}]}]}
```

字段类型：`string`、`long_text`、`number`、`integer`、`boolean`、`enum`、`multi_enum`、`string_array`、`object`、`object_array`、`time_point`、`time_span`、`asset_reference`、`record_reference`、`computed_readonly`。

View 的 `form.sections[].fields` 决定表单分组，`workspace` 描述证据区布局；Codebook 只作为版本化配置读取，不写死类别。

## 预检与幂等性

预检检查：

- 唯一入口、必填配置与所有声明文件；
- UTF-8 与 JSON/JSONL 行级解析；
- 主键存在且唯一、外键指向主表；
- Schema 字段类型可支持；
- ZIP 条目和记录内媒体路径无绝对路径或 `..`；
- 媒体根目录存在，媒体缺失作为可定位警告；
- 相同项目、版本和包摘要是否已导入。

只有 `report.valid=true` 才能导入。整个导入在一个数据库事务内完成，失败会回滚。相同 `project_id + dataset_version + package_digest` 返回 `already_exists`；不同摘要或版本创建新的 `DatasetVersion`。

## 媒体路径

研究数据只存 `/` 分隔的相对路径。导入时绑定本机或容器内 `media_root`；CodeFlow 解析后再次验证目标仍在该根目录内。前端不能提交任意路径，只能请求由数据记录关联出的样本、帧或资产 ID。
