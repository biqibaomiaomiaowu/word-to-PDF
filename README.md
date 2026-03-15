# 本地 Word 转 PDF & PDF 转 Word 转换系统

这是一个完全本地运行、不依赖云端 API 的文档转换工具，支持 Word 转 PDF 以及 PDF 转 Word 双向转换。后端采用 Python FastAPI 驱动 LibreOffice Headless 实现稳定的本地转换，前端采用 Vue 3 + Vite 构建现代化交互界面。

### 2. PDF 转 Word (多模式架构)

考虑到 PDF 排版的复杂性，本系统在 PDF 转 Word 时支持三种转换模式，用户可在前端界面自由选择：

*   **模式一：自动选择（推荐）**
    *   系统在转换前快速扫描 PDF 的前几页和末几页，计算文本密度、图片数量、表格线段（矢量图形）密度以及数学符号密度（`pdf_route_selector.py`）。
    *   若判定为普通文档则走标准文本引擎；若判定为“低文本+高图片”、“高频数学符号”、“密集表格线”等复杂文档，则自动路由至复杂版面引擎。
*   **模式二：标准文本引擎 (`pdf2docx`)**
    *   **适用场景**：绝大多数标准文档、论文、报告、纯文本居多的文件。
    *   **特点**：转换速度快，排版还原度高，生成的 Word 文档易于二次编辑。
*   **模式三：复杂版面/OCR 引擎 (`PaddleOCR PP-Structure`)**
    *   **适用场景**：包含大量公式、扫描件、复杂表格、碎片化排版的教育类试卷等材料。
    *   **特点**：利用 OCR 和版面分析技术，能强力还原极度复杂的版面格式，解决乱码和排版错位问题。
    *   **降级说明**：如果当前系统未配置 Paddle 环境，该选项在前端会自动禁用或提示不可用。如通过接口强行指定，将返回明确的错误。在使用该引擎时，若转换结果质量极差，系统具备内部兜底（Fallback）机制，会尝试回退到标准文本引擎处理。

### 3. 智能广告去除

用户可以在前端界面通过开关控制是否启用广告去除。

*   **Word 转 PDF**：支持预清理（修改底层 XML）与后处理（修复生成的 PDF）。主要检测并删除文档末尾（最后一页或页脚附近）注入的教育机构广告（如二维码、推广图片和微信号）。
*   **PDF 转 Word**：针对带有尾页广告的 PDF，支持预转换分析阶段智能剔除广告页。若前端支持该特性则显示选项。

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

1. **Python**: 3.9+ (推荐 3.12)
2. **Node.js**: 16+
3. **LibreOffice**: 必须在运行后端的服务器（或本地机器）上安装。
   - **Ubuntu/Debian**: `sudo apt install libreoffice`
   - **CentOS/RHEL**: `sudo yum install libreoffice`
   - **macOS**: `brew install --cask libreoffice` (确保 `libreoffice` 在系统 PATH 中)
   - **Windows**: 安装 LibreOffice，并将安装目录下的 `program` 文件夹添加到系统环境变量 `PATH` 中。

### 可选: 独立复杂版面引擎环境 (Paddle)

主项目**默认不强依赖 Paddle**。即使没有 Paddle，系统也能完美运行标准文本引擎 (`pdf2docx`) 进行转换。

如果你需要处理极度复杂、公式密集、排版碎片化的教辅资料，可以配置独立的 `.paddle_env` 环境来开启复杂版面引擎选项：

1. 在**项目根目录**下（与 `backend` 同级）创建虚拟环境：
   `python -m venv .paddle_env`
2. 激活该独立环境：
   - Windows: `.paddle_env\Scripts\activate`
   - Linux/Mac: `source .paddle_env/bin/activate`
3. 在独立环境中安装轻量级 Paddle 相关依赖（以 Windows 下 RTX 4060 8GB 为例，具体版本请参考 Paddle 官网）：
   `pip install paddlepaddle-gpu paddleocr python-docx PyMuPDF opencv-python-headless`
4. 启动系统后，主后端会自动探测项目根目录下是否存在 `.paddle_env` 且能否成功引入 Paddle。如果探测成功，前端将允许用户选择“复杂版面引擎 (Paddle)”。如果转换失败或质量极差，系统具备内部降级兜底（Fallback）机制，会尝试回退到标准文本引擎。

## 本地启动指南

### 1. 配置环境变量

复制并修改环境变量配置：
```bash
cp .env.example .env
```
可以根据需要编辑 `.env` 文件中的配置参数（如最大文件大小、超时时间、端口等）。

### 2. 手动分步启动 (Linux/macOS)

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

### 3. 手动分步启动 (Windows)

**启动后端：**
```cmd
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 
```

**启动前端：**
```cmd
cd frontend
npm install
npm run dev
```

### 4. 使用快捷脚本启动 (推荐)

项目内提供了便捷的启动脚本，可以一键启动前后端（依赖预先配置好的虚拟环境）：

**Linux/macOS:**
```bash
bash scripts/start_dev.sh
```

**Windows:**
直接双击运行 `scripts\start_dev.bat` 文件，或在命令行执行：
```cmd
scripts\start_dev.bat
```

### 5. 生产环境部署
1. 前端可使用 `npm run build` 生成静态文件，通过 Nginx 部署。
2. 后端应使用 Gunicorn 配合 Uvicorn workers 运行：
   `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`
3. 请确保为 Nginx 配置好针对 `/api` 路径到后端服务（如 `8000` 端口）的代理。

## 后续优化方向

- **分布式队列扩展**: 目前任务队列为基于内存的 `asyncio.Queue`。如需横向扩展，可以轻松将其替换为 Redis + Celery 架构。
- **长连接进度推送**: 目前前端采用轮询获取进度。若需求更高实时性，可以基于现有的 `FastAPI Websockets` 实现双向推送。
- **更多格式支持**: 后端基于 LibreOffice，原生支持将 `.rtf`, `.odt`, `.ppt` 等转为 PDF。可根据业务场景只需修改前端和后端的后缀名/MIME 校验规则即可扩充。
