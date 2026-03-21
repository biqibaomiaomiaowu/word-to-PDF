# Word / PDF Local Converter

本项目提供本地运行的双向转换服务：

- `Word -> PDF`：支持 `auto`、`libreoffice`、`word` 三种模式。`auto` 会根据文档中的公式风险在 Word 和 LibreOffice 之间路由。
- `PDF -> Word`：支持 `auto`、`pdf2docx`、`paddle` 三种模式，包含结构化识别与质量回退。

主后端为 `FastAPI`，前端为 `Vue 3 + Vite`。项目默认不依赖云端 API，模型、缓存和运行产物均保存在本地目录。

## 当前状态

当前仓库的有效转换链路如下：

### Word -> PDF

- `auto`：先分析 DOC/DOCX 中的公式风险。普通文档优先走 `LibreOffice`，高风险公式文档优先走 `Microsoft Word`。
- `word`：强制使用 `Word COM`。若 `pywin32` 导出失败，服务会自动重试 `PowerShell COM`。
- `libreoffice`：强制使用 `LibreOffice`。
- 公式预处理：Word 路径会先对 AxMath 等高风险对象做预处理，降低公式乱码概率。
- fallback 约束：`auto` 模式下若 Word 导出失败，会回退到 LibreOffice，但使用的是原始或清理后的源文件，不会复用仅为 Word 准备的临时 `formula_safe.docx`。

### PDF -> Word

- 标准引擎：`pdf2docx`
- 结构化引擎：`PPStructureV3`，主 runner 为 `backend/app/services/run_paddle_structure_v4.py`
- 自动路由：`auto` 会先分析 PDF，再决定使用 `pdf2docx` 或 `paddle`
- 质量回退：如果 Paddle 结果被判定为 `poor` 或 `failed`，系统会自动回退到 `pdf2docx`
- 公式支持：可选启用 `PP-FormulaNet_plus-L`，当前已支持将部分识别结果写为 Word OMML，而不是全部转图片

说明：当前链路已经可以稳定跑通本地转换，但公式、复杂版面、多栏顺序和目录样式仍在持续优化，不应理解为“出版级完全保真”。

## 目录说明

- `backend/`：FastAPI 后端
- `frontend/`：Vue 3 前端
- `scripts/start_all_bootstrap_v2.py`：一键启动的主实现
- `scripts/download_ppstructure_models.ps1`：Paddle 模型下载脚本
- `scripts/test_ppstructure_conversion_v3.py`：Paddle 结构化链路测试脚本
- `scripts/test_word_to_pdf_formula_fix.py`：Word -> PDF 公式导出冒烟脚本
- `scripts/cleanup_repo.py`：清理缓存、日志、输出文件和历史杂物
- `check_paddle_env.py`：基础自检入口
- `check_paddle_env_v2.py`：完整能力自检脚本

## 环境要求

建议环境：

- Python `3.10+`
- Node.js `18+`
- LibreOffice 已安装并加入 `PATH`
- 如需高风险公式文档稳定导出 PDF，建议安装 Microsoft Word
- Windows 下如需 GPU 跑 Paddle，请确保 `paddlepaddle-gpu` 与本机 CUDA / cuDNN 版本匹配

先确认 LibreOffice 可用：

```powershell
soffice --version
```

## 一键启动

推荐直接在项目根目录运行：

```powershell
python start_all.py
```

该命令当前会自动处理：

- 创建并检查 `backend/venv`
- 安装后端依赖
- 检查前端 `node_modules`，缺失时执行 `npm install --legacy-peer-deps`
- 创建并检查 `.paddle_env`
- 安装缺失的 Paddle 相关 Python 依赖
- 检测 OCR 模型和结构化模型状态
- 在需要时询问是否下载 Paddle 模型
- 启动后端和前端服务

默认地址：

- 前端：`http://localhost:3000`
- 后端：`http://127.0.0.1:8000/api`

### 常用启动参数

```powershell
python start_all.py --paddle-models download
python start_all.py --paddle-models skip
python start_all.py --paddle-models download --paddle-device gpu:0
python start_all.py --paddle-models download --paddle-include-formula-models
python start_all.py --paddle-models skip --require-paddle
```

参数说明：

- `--paddle-models ask|download|skip`：缺模型时是询问、直接下载还是跳过
- `--paddle-device cpu|gpu:0`：初始化或下载模型时使用的设备
- `--paddle-include-formula-models`：额外下载 `PP-FormulaNet_plus-L`，并安装 `latex2mathml` / `lxml`
- `--require-paddle`：如果 Paddle 不可用则直接退出，不继续启动服务
- `--disable-ad-removal`：禁用前端默认的广告清理开关

## 手动准备 Paddle 环境

### 1. 先做基础自检

```powershell
python check_paddle_env.py
```

如果你要检查结构化 API 和模型是否完整：

```powershell
python check_paddle_env_v2.py --deep
```

关键字段：

- `OCR models ready`
- `Structure API available`
- `Structure models ready`
- `Structure pipeline available`

### 2. 下载结构化模型

仅下载结构化主链路所需模型：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_ppstructure_models.ps1 -Device cpu
```

如果还要启用公式模型：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_ppstructure_models.ps1 -Device cpu -IncludeFormula
```

下载脚本当前特性：

- 会优先使用 `BOS -> ModelScope -> AIStudio`
- 会清理中断下载留下的残缺模型目录
- 会把缓存和临时目录固定到仓库本地
- 在 `-IncludeFormula` 时自动安装公式转 OMML 所需依赖

## 手动启动

### 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 后端测试

注意：后端测试必须从 `backend/` 目录执行，否则会因为 `app` 包路径导致导入失败。

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q
```

如果只想跑 Word -> PDF 定向回归：

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_word_com.py tests/test_task_manager_word_to_pdf.py -q
```

### 前端

```powershell
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Word -> PDF 导出模式

后端当前支持三种模式：

- `auto`
- `libreoffice`
- `word`

当前 `auto` 模式的真实行为：

- 普通文档优先使用 `LibreOffice`
- 如果检测到 OMML、对象公式、页眉页脚中的公式风险或其他高风险数学内容，优先使用 `Word`
- 若 `Word COM` 不可用，自动改走 `LibreOffice`
- 若 Word 导出失败，且当前模式是 `auto`，会自动回退到 `LibreOffice`
- Word 路径使用的公式预处理文件只给 Word 使用，不会透传给 LibreOffice fallback

如果你要验证公式修复链路，推荐使用仓库内置冒烟脚本：

```powershell
.\backend\venv\Scripts\python.exe .\scripts\test_word_to_pdf_formula_fix.py --input "D:\绝对路径\sample.docx" --engines auto word libreoffice
```

脚本会输出：

- `word_com_available`
- `auto_decision.primary_engine`
- `formula_preprocessing.flattened_axmath_count`
- `results[].pdf_inspection.opensymbol_spans`
- `results[].pdf_inspection.top_fonts`

对公式乱码问题，优先关注：

- `/api/capabilities` 中 `word_com_available` 是否为 `true`
- 自定义调用时输出目录是否使用绝对路径
- 自动路由是否把高风险公式文档分配给了 `word`

## PDF -> Word 转换模式

后端当前支持三种模式：

- `auto`
- `pdf2docx`
- `paddle`

当前 `auto` 模式的真实行为：

- 如果分析器认为 PDF 更适合 `paddle`，但结构化模型未就绪，会自动改走 `pdf2docx`
- 如果 Paddle 转换异常失败，会自动尝试 `pdf2docx`
- 如果 Paddle 结果质量被判定为 `poor` 或 `failed`，会尝试回退并择优保留结果

## 公式支持状态

当前公式相关实现已经接入：

- 可选模型：`PP-FormulaNet_plus-L`
- 转换依赖：`latex2mathml`、`lxml`
- Word 公式输出：通过 `MathML -> OMML` 写入 DOCX

当前能力边界：

- 已支持一部分公式和内联 LaTeX 片段转成 Word 公式对象
- 不是所有数学内容都能稳定识别成 OMML
- 对复杂公式、跨行公式、混排区域仍需要继续优化

## 结构化转换测试

推荐用下面的脚本验证当前结构化链路：

```powershell
python .\scripts\test_ppstructure_conversion_v3.py --device gpu:0
```

如果想强制 CPU：

```powershell
python .\scripts\test_ppstructure_conversion_v3.py --device cpu
```

该脚本会输出：

- `final_device`
- `stats.xml_tables`
- `stats.xml_drawings`
- `stats.xml_omath`
- `stats.xml_omath_para`

含义：

- `xml_tables > 0`：DOCX 中出现真实表格对象
- `xml_drawings > 0`：DOCX 中出现绘图 / 图片锚点
- `xml_omath > 0`：DOCX 中出现 Word 公式对象

如果 GPU 跑崩，测试脚本和主转换链路都已支持自动回退到 CPU。

## API 概览

### 健康检查

```http
GET /api/health
```

### 能力探测

```http
GET /api/capabilities
```

会返回：

- `paddle_available`
- `paddle_structure_available`
- `paddle_missing_ocr_models`
- `paddle_missing_structure_models`
- `pdf2docx_available`
- `libreoffice_available`
- `word_com_available`
- `supported_converter_modes`
- `supported_word_to_pdf_engines`

### 提交转换

```http
POST /api/convert
```

关键表单字段：

- `file`
- `remove_ad`
- `conversion_type`
- `converter_mode`

### 查询任务

```http
GET /api/tasks/{task_id}
```

会返回：

- 当前状态
- 实际使用的引擎
- 自动路由原因
- 是否发生 fallback
- DOCX 质量评分与风险提示

### 下载结果

```http
GET /api/download/{task_id}
```

## 常见问题

### 1. `check_paddle_env.py` 通过了，但 `paddle_structure_available` 还是 `false`

说明基础 OCR 依赖没问题，但结构化模型还没齐。请运行：

```powershell
python check_paddle_env_v2.py --deep
```

然后根据缺失模型提示执行下载脚本。

### 2. `Word -> PDF` 公式文档还是走了 LibreOffice

优先检查：

- `/api/capabilities` 中 `word_com_available` 是否为 `true`
- 是否显式把 `converter_mode` 传成了 `libreoffice`
- 文档是否在预处理后仍被判定为低风险

需要复现时，优先使用：

```powershell
.\backend\venv\Scripts\python.exe .\scripts\test_word_to_pdf_formula_fix.py --input "D:\绝对路径\sample.docx" --engines auto
```

### 3. GPU 转换直接崩溃

当前代码已经对常见 native crash 做了 CPU 回退，但根因通常还是 GPU 环境不匹配。优先检查：

- `paddlepaddle-gpu` 版本
- CUDA 版本
- cuDNN 版本

如果你的机器上存在类似 `CUDNN 9.9 vs 9.5` 警告，优先修正环境，或者先用 CPU 稳定运行。

### 4. README 之外还有哪些维护脚本

- `scripts/cleanup_repo.py`
  - 当前推荐的仓库清理脚本，默认删除输出文件、日志、缓存和临时目录；`--aggressive` 会额外删除环境和模型缓存
- `scripts/delete_repo_junk.ps1`
  - 旧清理脚本，仅保留作历史参考
- `REPO_CLEANUP.md`
  - 记录清理状态和保留文件

## 仓库清理

先预览，再删除：

```powershell
python .\scripts\cleanup_repo.py --dry-run
python .\scripts\cleanup_repo.py
```

如果你明确要连环境一起清掉：

```powershell
python .\scripts\cleanup_repo.py --aggressive
```

## 当前建议的使用方式

如果你只是想把项目跑起来：

```powershell
python start_all.py --paddle-models download --paddle-include-formula-models
```

如果你要验证 Word -> PDF 公式修复：

```powershell
.\backend\venv\Scripts\python.exe .\scripts\test_word_to_pdf_formula_fix.py --input "D:\绝对路径\sample.docx" --engines auto word libreoffice
```

如果你要稳定交付复杂文档：

- 先检查 `/api/capabilities` 中 `word_com_available` 和 `paddle_structure_available`
- Word 文档优先确认自动路由是否把公式高风险样例分配给 `word`
- PDF 样例优先确认 `xml_tables` / `xml_drawings` / `xml_omath` 是否有效增长
- 对关键样例仍要人工抽检，不要把当前阶段理解成最终版面完全保真
