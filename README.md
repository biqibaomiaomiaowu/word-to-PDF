# 本地 Word 转 PDF 转换系统

这是一个完全本地运行、不依赖云端 API 的 Word 转 PDF 转换工具。后端采用 Python FastAPI 驱动 LibreOffice Headless 实现稳定的本地转换，前端采用 Vue 3 + Vite 构建现代化交互界面。

## 核心特性

- **完全本地化处理**: 保护隐私，不依赖任何第三方云端转换服务。
- **现代化架构**: 前端使用 Vue 3 (Composition API) + TailwindCSS；后端使用 FastAPI 异步处理。
- **并发与队列控制**: 后端基于 `asyncio.Queue` 和 `asyncio.Semaphore` 进行受控的转换任务排队，防止并发调用 LibreOffice 导致内存崩溃。
- **自动清理机制**: 转换完成的文件支持后端定时清理机制，避免磁盘占用无限扩大。
- **可观测与鲁棒性**: 包含完善的文件验证、超时处理、LibreOffice 异常捕获机制与任务记录持久化。

## 项目结构

```text
.
├── backend/                  # FastAPI 后端服务
│   ├── app/
│   │   ├── api/              # API 路由层
│   │   ├── core/             # 核心配置管理 (pydantic-settings) & 异常处理
│   │   ├── models/           # Pydantic Schemas
│   │   ├── services/         # 业务逻辑服务层 (LibreOffice子进程, 任务队列, 定时清理)
│   │   └── utils/            # 工具类 (文件校验)
│   ├── tests/                # 单元和 API 测试
│   └── requirements.txt      # 后端依赖
├── frontend/                 # Vue 3 前端应用
│   ├── src/
│   │   ├── components/       # 基础 UI 组件 (上传、任务状态、历史列表)
│   │   ├── services/         # API 请求层 (Axios 封装)
│   │   ├── stores/           # 状态管理 (Pinia + LocalStorage)
│   │   ├── views/            # 页面视图 (HomeView)
│   │   └── ...
│   ├── package.json          # 前端依赖
│   └── vite.config.js        # Vite 构建与代理配置
├── scripts/                  # 运行启动脚本
├── docs/                     # 额外文档
└── .env.example              # 环境变量配置参考
```

## 技术选型与参考实现对比

### 参考了哪些开源思路
本项目在设计时参考了 GitHub 上部分基于 `FastAPI` 封装 LibreOffice 的项目以及常见的文档格式转换前后端分离项目。吸收了它们利用 `subprocess` 异步挂起子进程等待回调的思路，并借鉴了任务状态机模型。

### 本项目相对参考实现做了哪些工程化增强
1. **队列与受控并发**: 许多开源脚本直接用 FastAPI 处理请求并拉起 LibreOffice，这会导致高并发时资源抢占。本项目实现了一个基于内存的 `TaskManager`，使用 `asyncio.Semaphore` 限制最大并发转换数，超出的请求会自动排队。
2. **生命周期与自清理**: 增加了后台自动清理服务（定时扫描 `temp_uploads` 和 `output_pdfs` 中超时的任务），确保服务器磁盘可用性。
3. **前端工程化**: 前端不只停留于“一个 HTML 文件套 Axios”，而是采用了真正的 Vite + Vue 3 标准工程，支持历史记录持久化存储并优雅地处理任务轮询逻辑。

## 环境要求

1. **Python**: 3.9+
2. **Node.js**: 16+
3. **LibreOffice**: 必须在运行后端的服务器（或本地机器）上安装。
   - **Ubuntu/Debian**: `sudo apt install libreoffice`
   - **CentOS/RHEL**: `sudo yum install libreoffice`
   - **macOS**: `brew install --cask libreoffice` (确保 `libreoffice` 在系统 PATH 中)
   - **Windows**: 安装 LibreOffice，并将安装目录下的 `program` 文件夹添加到系统环境变量 `PATH` 中。

## 本地启动指南

### 1. 配置环境变量

复制并修改环境变量配置：
```bash
cp .env.example .env
```
可以根据需要编辑 `.env` 文件中的配置参数（如最大文件大小、超时时间、端口等）。

### 2. 手动分步启动

**启动后端：**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
后端 API 文档将在: `http://localhost:8000/api/openapi.json`

**启动前端：**
```bash
cd frontend
npm install
npm run dev
```
前端应用将在: `http://localhost:3000`

### 3. 使用快捷脚本启动 (推荐)

项目内提供了一个便捷的启动脚本，可以一键启动前后端（依赖预先配置好的虚拟环境）：

```bash
bash scripts/start_dev.sh
```

### 4. 生产环境部署
1. 前端可使用 `npm run build` 生成静态文件，通过 Nginx 部署。
2. 后端应使用 Gunicorn 配合 Uvicorn workers 运行：
   `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`
3. 请确保为 Nginx 配置好针对 `/api` 路径到后端服务（如 `8000` 端口）的代理。

## 后续优化方向

- **分布式队列扩展**: 目前任务队列为基于内存的 `asyncio.Queue`。如需横向扩展，可以轻松将其替换为 Redis + Celery 架构。
- **长连接进度推送**: 目前前端采用轮询获取进度。若需求更高实时性，可以基于现有的 `FastAPI Websockets` 实现双向推送。
- **更多格式支持**: 后端基于 LibreOffice，原生支持将 `.rtf`, `.odt`, `.ppt` 等转为 PDF。可根据业务场景只需修改前端和后端的后缀名/MIME 校验规则即可扩充。
