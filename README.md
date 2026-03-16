# Word / PDF Local Converter

本项目提供本地运行的双向转换服务：

- `Word -> PDF`：通过本机 `LibreOffice` 转换。
- `PDF -> Word`：支持标准文本引擎和 Paddle 结构化引擎。

当前主后端是 `FastAPI`，前端是 `Vue 3 + Vite`。项目默认不依赖云端 API，模型与缓存都放在仓库本地目录下。

## 当前状态

当前仓库的有效 PDF 转 Word 链路如下：

- 标准引擎：`pdf2docx`
- 结构化引擎：`PPStructureV3`，主 runner 为 `backend/app/services/run_paddle_structure_v4.py`
- 自动路由：`auto` 模式会先分析 PDF，再决定使用 `pdf2docx` 或 `paddle`
- 质量回退：如果 Paddle 结果被质量检测判为 `poor` 或 `failed`，系统会尝试回退到 `pdf2docx`
- 公式支持：可选启用 `PP-FormulaNet_plus-L`，当前已经支持把一部分识别到的公式写成 Word OMML，而不是强行转成图片

说明：Paddle 结构化链路已经脱离旧的 OCR-only 文本流方案，但公式、复杂图文顺序、目录样式等仍在持续优化，不应理解为“出版级还原”已经完成。

## 目录说明

- `backend/`：FastAPI 后端
- `frontend/`：Vue 3 前端
- `scripts/start_all_bootstrap_v2.py`：当前有效的一键启动脚本实现
- `scripts/download_ppstructure_models.ps1`：Paddle 模型下载脚本
- `scripts/test_ppstructure_conversion_v3.py`：结构化转换测试脚本
- `check_paddle_env.py`：简版自检入口
- `check_paddle_env_v2.py`：完整能力自检脚本

## 环境要求

建议环境：

- Python `3.10+`
- Node.js `18+`
- LibreOffice 已安装并加入 `PATH`
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

- `--paddle-models ask|download|skip`
  - 缺模型时是询问、直接下载还是跳过
- `--paddle-device cpu|gpu:0`
  - 初始化或下载模型时使用的设备
- `--paddle-include-formula-models`
  - 额外下载 `PP-FormulaNet_plus-L`，并安装 `latex2mathml` / `lxml`
- `--require-paddle`
  - 如果 Paddle 不可用则直接退出，不继续启动服务
- `--disable-ad-removal`
  - 禁用前端默认的广告清理开关

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

### 前端

```powershell
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## PDF -> Word 转换模式

后端当前支持三种模式：

- `auto`
  - 自动分析 PDF，优先使用合适的引擎
- `pdf2docx`
  - 标准文本型引擎，适合规则文档
- `paddle`
  - 复杂版面结构化引擎，适合表格、图片、公式较多的 PDF

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
- `supported_converter_modes`

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

### 2. GPU 转换直接崩溃

当前代码已经对常见 native crash 做了 CPU 回退，但根因通常还是 GPU 环境不匹配。优先检查：

- `paddlepaddle-gpu` 版本
- CUDA 版本
- cuDNN 版本

如果你的机器上有类似 `CUDNN 9.9 vs 9.5` 警告，优先修正环境，或者先用 CPU 稳定运行。

### 3. README 之外还有哪些维护脚本

- `scripts/delete_repo_junk.ps1`
  - 清理临时文件、旧实现和误生成目录
- `REPO_CLEANUP.md`
  - 记录当前仓库清理状态和保留文件

## 当前建议的使用方式

如果你只是想把项目跑起来：

```powershell
python start_all.py --paddle-models download --paddle-include-formula-models
```

如果你只想验证结构化引擎：

```powershell
python check_paddle_env_v2.py --deep
python .\scripts\test_ppstructure_conversion_v3.py --device gpu:0
```

如果你要稳定交付复杂 PDF：

- 先保证 `/api/capabilities` 中 `paddle_structure_available = true`
- 再用测试脚本确认 `xml_tables` / `xml_drawings` / `xml_omath` 有效增长
- 对关键样例仍要人工抽检，不要把当前阶段理解成最终版面完全保真
