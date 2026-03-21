# Repository Guidelines

## 项目结构与模块组织
- `backend/app/` 是 FastAPI 后端；`api/` 放接口，`services/` 放转换流程，`utils/` 放通用工具，`models/` 放数据结构。
- `backend/tests/` 存放后端回归测试，覆盖 API、转换模式、公式预处理、Word/LibreOffice 路由与 fallback。
- `frontend/src/` 是 Vue 3 + Vite 前端，主要目录包括 `components/`、`views/`、`stores/`、`services/`。
- `scripts/` 放启动、冒烟、下载和清理脚本；`start_all.py` 是主入口，`cleanup_repo.py` 用于仓库清理。
- 运行产物常见于 `output_pdfs/`、`backend/output_pdfs/`、`backend/temp_uploads/`、`.paddlex/`、`.paddle_models/`，不要提交。

## 构建、测试与开发命令
- `python start_all.py`：启动前后端并检查依赖、Paddle 环境与模型状态。
- `cd backend && .\venv\Scripts\python.exe -m pytest -q`：运行后端测试。测试必须从 `backend/` 目录执行，否则会找不到 `app` 包。
- `cd backend && .\venv\Scripts\activate && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`：只启动后端。
- `cd frontend && npm run dev`：启动前端开发服务；`npm run build`：构建生产包。
- `python .\scripts\test_ppstructure_conversion_v3.py --device cpu`：验证 Paddle 结构化链路。
- `python .\scripts\test_word_to_pdf_formula_fix.py --input <绝对路径>`：验证 Word -> PDF 公式导出与路由。
- `python .\scripts\cleanup_repo.py --dry-run`：预览可清理项；加 `--aggressive` 会额外删除虚拟环境、`node_modules` 和 Paddle 缓存。

## 代码风格与命名约定
- Python 使用 4 空格缩进，模块和函数使用 `snake_case`，类名使用 `PascalCase`。
- Vue 组件文件名使用 `PascalCase`，新增组件优先保持现有 Vue 3 SFC 风格并使用 `<script setup>`。
- 转换编排逻辑放 `backend/app/services/`，纯工具函数放 `backend/app/utils/`。
- 仓库未强制统一格式化工具；提交前保持与周边代码风格一致，注释只保留必要说明。

## 测试与维护要求
- 后端测试基于 `pytest` / `pytest-asyncio`，文件命名统一为 `backend/tests/test_*.py`。
- 修改路由、转换模式、公式处理、广告清理或 fallback 逻辑时，必须补回归测试。
- `Word -> PDF` 当前支持 `auto`、`libreoffice`、`word` 三种模式；`auto` 对公式高风险文档优先走 Word，失败时回退 LibreOffice。
- 不要让 LibreOffice fallback 复用仅为 Word 预处理生成的 `formula_safe.docx`；回退时必须使用原始或清理后的源文件。
- 修改转换能力、脚本入口或运维命令时，同步更新 `README.md`。

## 提交与 Pull Request 规范
- 历史提交以简短主题为主，如 `fix:pdf to word`、`fix:依赖版本`、简洁中文说明；保持单一目的和祈使语气。
- PR 需说明影响的是 `Word -> PDF` 还是 `PDF -> Word`，列出依赖前提、验证命令和结果。
- 涉及前端请附截图；涉及公式、表格、版面修复请附输入样例和输出说明。

## 安全与配置提示
- 从 `.env.example` 复制本地配置到 `.env`，不要提交敏感信息。
- 不要提交客户文档、生成 PDF、模型缓存、上传文件和临时调试产物。
- 调试 Word 导出前先确认 `/api/capabilities` 中 `word_com_available`，并优先检查输出目录是否为绝对路径。
