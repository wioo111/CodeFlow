# CodeFlow

CodeFlow 是面向 AI 结构化输出的可视化审校、编辑与导出工具。它读取项目自己的 Schema、View 配置和 JSON/JSONL 数据，自动生成表格及表单；人工修改后实时校验、保留差异记录，并重新导出标准数据。

源码不包含足球字段或 P1—P7 等业务编码。`project_templates/football_cp` 只是一个可替换模板；`project_templates/inventory` 使用同一数据内核处理库存数据。

## MVP 能力

- 导入 Schema JSON、可选 View JSON、数据 JSON/JSONL
- 支持 `string`、`long_text`、`number`、`boolean`、`enum`、`multi_enum`、`string_array`、`object`、`object_array`
- Schema 驱动的 Ant Design 表格和 React Hook Form 表单
- 全文搜索、排序、审校/校验状态筛选、列配置、枚举单元格快速编辑和批量状态修改
- 必填、枚举、数值范围、字符串长度、条件必填和字段关系校验
- 原始数据、当前数据、字段级修改日志分开保存
- 未审校、审校中、已通过、已拒绝、需要复核五种状态
- 原始/当前 JSON 对照、嵌套数据编辑、错误路径定位
- 当前数据、原始数据和差异日志的 JSON、JSONL、扁平化 CSV 导出
- 导出记录携带 Schema ID/版本、数据版本和审校元数据

## Docker 运行

```bash
docker compose up --build
```

打开 <http://localhost:3000>。

## 本地开发

需要 Python 3.11+ 与 Node.js 20+。

```powershell
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements-dev.txt
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

另开终端：

```powershell
cd frontend
npm install
npm run dev
```

前端为 <http://localhost:5173>，API 文档为 <http://localhost:8000/docs>。

## 快速体验

在“导入项目”页面选择：

- Schema：`project_templates/football_cp/schema.json`
- View：`project_templates/football_cp/view.json`
- 数据：`project_templates/football_cp/example.jsonl`

也可换用 `project_templates/inventory/` 下的三份文件，验证非足球数据无需修改源码。

## 验证

```powershell
.venv\Scripts\python -m pytest -q
cd frontend
npm run lint
npm test
npm run build
```

后端测试覆盖导入、两层校验、嵌套编辑、原始值保护、字段级差异、状态筛选、批量审校、多格式导出、非足球 Schema 和主键冲突。

## 数据边界

当前 MVP 是本地单用户审校工具，不包含 AI 调用、视频播放、复杂权限、多人实时协同、任务分配或 Gold 仲裁。SQLite 可在需要多人在线使用时替换为 PostgreSQL，业务数据模型无需重写。
