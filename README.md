# CodeFlow

CodeFlow 是 Schema 驱动的多模态研究标注与审校平台。它整体导入由清洗流水线生成的标准数据包，以样本为中心联动视频、抽帧、评论与元数据，并严格分离只读清洗数据、AI 原始预编码、每位标注员的人工结果、仲裁和冻结 Gold。

核心实现不包含足球字段、P1—P7、平台账号或固定样本数量。`project_templates/research_football` 和 `project_templates/research_inventory` 使用同一套数据内核验证足球与非足球多表项目。

## 当前可用能力

- 上传 ZIP 后自动读取唯一的 `codeflow_project.json`，无需逐表手工导入
- 导入前定位到文件、行、表、字段与样本的预检报告
- JSONL、主键、外键、Schema 类型、媒体相对路径和版本摘要校验
- 基于 `project_id + dataset_version + SHA-256` 的幂等导入；新版本不覆盖旧版本
- `samples/comments/frames/assets` 及未来任意关联表的通用 JSON 数据内核
- 项目级媒体根目录绑定、路径逃逸防护、受控媒体接口和 HTTP Range 视频播放
- 三栏样本工作台、视频快捷键、抽帧跳转、评论/元数据/Codebook/日志抽屉
- 多个 evidence span、主区间、0.1 秒微调、区间循环和无法定位标记
- Schema/View 驱动人工表单、自动保存、刷新恢复、提交校验和锁定/重开
- AI 原始结果不可修改；人工结果、字段决策和字段级追加日志单独保存
- coder/manager/adjudicator/admin/viewer 角色预留，后端强制证据可见性和独立结果隔离
- 可配置阶段、实验组、盲标 Assignment，支持多人独立提交、仲裁和 Gold 新版本冻结
- 标准研究 ZIP 导出：AI、人工长/宽表、字段决策、日志、仲裁、Gold、Assignment、一致性输入、指标与摘要

## 快速启动

本地开发需要 Python 3.11+ 和 Node.js 20+：

```powershell
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements-dev.txt
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
cd frontend
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>，API 文档位于 <http://127.0.0.1:8000/docs>。

Docker：

```powershell
$env:CODEFLOW_MEDIA_ROOT='D:\research\media'
docker compose up --build
```

容器内导入时将媒体根目录填写为 `/media`。该目录只读挂载，绝对路径不会写回研究数据。

## 演示数据包

运行：

```powershell
.\scripts\build_demo_packages.ps1
```

然后在“导入项目 → 标准多表数据包”选择：

- 足球包：`project_templates/research_football/research_football-demo.zip`
- 足球媒体根：`project_templates/research_football/media`
- 非足球包：`project_templates/research_inventory/research_inventory-demo.zip`

足球演示包包含两个 8 秒本地 MP4 和三张抽帧图，用于验证真实 Range 播放与时间跳转。它不是目标研究的 250 条真实清洗数据。

## 验证

```powershell
.venv\Scripts\python -m pytest -q
cd frontend
npm run lint
npm test
npm run build
```

浏览器端到端脚本（使用隔离的本地浏览器，不读取用户浏览器资料）：

```powershell
node scripts/e2e_research.mjs
```

详细协议与工作流见：

- [数据包协议](docs/dataset-package-protocol.md)
- [研究工作流与安全](docs/research-workflow.md)
- [验收状态](docs/acceptance-report.md)

## 数据库升级

研究内核采用只新增表的兼容升级：应用启动时由 SQLAlchemy 创建不存在的表，旧版 `Project/Batch/Record` 数据仍可读取。升级前应备份 SQLite 文件；回退旧代码时保留新增表即可，不影响旧表。若要彻底回滚，应先导出研究 ZIP，再删除研究专用表，禁止直接覆盖现有数据库。

## 后续能力

当前交付聚焦短视频 Pilot 的稳定数据与标注内核。完整比赛的分段加载、缩放时间轴、波形/镜头层、候选片段发现、排序和剪辑属于 Phase 6，不在本轮最低交付范围内。
