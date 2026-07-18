# CodeFlow

CodeFlow 是一个面向研究编码工作的通用 Web 工具。当前版本以足球短视频传播点为预置案例，但材料类型、编码字段和选项均由项目 Schema 驱动，系统底层不写死研究主题。

## 当前交付

- 预置 1 个研究项目与 10 条 mock/text 模拟材料
- Schema 驱动的动态表单，支持短文本、长文本、单选、多选、布尔、数字与量表
- 自动保存和手动保存草稿，刷新后从数据库恢复
- 必填及选项校验，提交后原始结果锁定
- 连续任务导航、进度统计、完整结果查看
- 包含编码员、提交时间、耗时、Schema 与代码本版本的 JSONL/CSV 导出
- FastAPI + SQLite + SQLAlchemy 后端与 React + TypeScript + Vite 前端
- Docker Compose 一键运行

## Docker 运行（推荐）

```bash
docker compose up --build
```

浏览器打开 <http://localhost:3000>。SQLite 数据保存在 Docker 持久化卷中。

## 本地开发

需要 Python 3.11+ 与 Node.js 20+。

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements-dev.txt
.venv/Scripts/python -m uvicorn backend.main:app --reload
```

另开终端：

```bash
cd frontend
npm install
npm run dev
```

前端地址为 <http://localhost:5173>，API 文档为 <http://localhost:8000/docs>。

## 验证

```bash
.venv/Scripts/python -m pytest
cd frontend
npm run lint
npm test
npm run build
```

## 目录

- `backend/`：数据库模型、REST API、Schema 校验与导出
- `frontend/`：项目、编码工作台与结果页面
- `project_templates/football/`：预置项目、Schema 和模拟材料
- `tests/`：核心闭环 API 测试
- `scripts/`：数据库初始化与种子数据脚本

## 设计边界

本仓库实现开发计划的 Sprint 1。视频播放、登录与复杂权限、多人分歧仲裁、多阶段流程和代码本在线编辑属于后续迭代，不在当前版本内。

