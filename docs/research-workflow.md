# 研究标注工作流与安全

## 数据层

| 层级 | 实体 | 可修改性 |
| --- | --- | --- |
| 清洗数据 | `DatasetVersion/DataTable/DataRecord.clean_data` | 导入后只读 |
| AI 原始结果 | `ModelRun/AIRawAnnotation.raw_output` | 只允许新增，API 无更新入口 |
| 个人结果 | `AnnotationAssignment/HumanAnnotation` | 提交前草稿可改，提交后锁定 |
| 仲裁结果 | `Adjudication.resolution` | 仲裁者主动确认，不覆盖个人结果 |
| Gold | `GoldAnnotation` | 按新版本冻结，不覆盖旧版本 |

所有人工变化追加到 `ResearchChangeLog`，保存操作人、时间、阶段、字段路径、前后值、修改类型、原因和版本快照。时间区间变化额外绑定视频时长版本。

## Assignment 与证据隔离

管理员可通过 `POST /api/projects/{id}/assignments` 指定样本、coder、阶段、实验组、盲标和证据配置。支持任意阶段名，内置流程建议使用 `calibration`、`pilot_independent_review`、`blind_control`、`adjudication`、`gold_freeze`、`benchmark_evaluation`。

证据配置示例：

```json
{"video":true,"frames":false,"title":false,"comments":false,"metadata":false,"ai_suggestion":false}
```

限制由后端执行：无评论权限时评论 API 返回 403；标题和元数据在样本 API 响应前删除；盲标不返回 AI 原始结果；coder 访问其他人的 assignment 返回 403。前端隐藏不是安全边界。

角色：`admin`、`research_manager`、`coder`、`adjudicator`、`viewer`。本地默认用户为 `local_reviewer/coder`，部署认证后可把身份映射到 `X-User-ID` 和 `X-User-Role`，生产环境应由可信反向代理覆盖并移除客户端同名头。

## 时间证据

工作台使用原生视频控件并支持空格播放/暂停、左右键 ±1 秒、抽帧点击跳转、拖动区间边界、数字微调、当前时间取点、多候选区间、主区间、循环和无法准确定位。后端拒绝负数、`start >= end`、多个主区间和超出样本视频时长的区间。

## 多人、仲裁和 Gold

同一样本可分配多位 coder。每人只能看到自己的草稿和提交结果；研究管理员运行 `POST /api/projects/{id}/adjudications/prepare` 后生成字段分歧。仲裁者从 AI 与所有个人结果中主动提交 resolution 和理由。Gold 冻结只接受已解决仲裁，重复版本返回冲突；修订必须使用新的 `gold_version`。

## 导出

`POST /api/exports` 返回 ZIP，包含：

`ai_raw_annotations.jsonl`、`human_annotations_long.jsonl`、`human_annotations_wide.jsonl`、`field_decisions.jsonl`、`change_logs.jsonl`、`adjudications.jsonl`、`gold_annotations.jsonl`、`assignments.csv`、`agreement_input.csv`、`annotation_metrics.json`、`export_manifest.json`。

Manifest 保存版本、生成时间、记录数和每个文件的 SHA-256，不输出媒体绝对路径。可选择匿名 coder ID。

## 活跃时长

前端只累计间隔不超过 30 秒的指针、键盘、输入和视频播放活动；静置页面不计入活跃时长。Assignment 另存打开、首次保存和提交时间，便于区分自然时长和实际工作时长。
