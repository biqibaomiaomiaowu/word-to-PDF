[CmdletBinding()]
param(
    [ValidateSet("cpu", "gpu:0")]
    [string]$Device = "cpu",

    [bool]$CleanInterrupted = $true,

    [switch]$IncludeFormula
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-ValidModelDir {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Container)) {
        return $false
    }

    return (Test-Path (Join-Path $Path "inference.json")) -or (Test-Path (Join-Path $Path "inference.yml"))
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".paddle_env\Scripts\python.exe"
$checkScript = Join-Path $repoRoot "check_paddle_env_v2.py"
$tempRoot = Join-Path $repoRoot ".cache"
$tempPy = Join-Path $tempRoot "ppstructure_download.py"
$tempDir = if ($env:OS -eq "Windows_NT") {
    Join-Path $env:windir "Temp"
} else {
    Join-Path $tempRoot "tmp"
}

if (-not (Test-Path $pythonExe)) {
    throw "Missing Python runtime: $pythonExe"
}

$dirs = @(
    (Join-Path $tempRoot "hf"),
    (Join-Path $tempRoot "modelscope"),
    (Join-Path $tempRoot "home"),
    (Join-Path $tempRoot "home\\AppData\\Roaming"),
    (Join-Path $tempRoot "home\\AppData\\Local"),
    (Join-Path $repoRoot ".paddlex"),
    (Join-Path $repoRoot ".paddle_models"),
    (Join-Path $repoRoot ".paddle_inference")
)

if ($CleanInterrupted) {
    $cleanupTargets = @(
        (Join-Path $repoRoot ".paddlex\temp"),
        (Join-Path $repoRoot ".paddlex\locks"),
        (Join-Path $tempRoot "hf"),
        (Join-Path $tempRoot "modelscope")
    )

    $structureModels = @(
        "PP-DocLayout_plus-L",
        "PP-Chart2Table",
        "PP-OCRv5_server_det",
        "PP-OCRv5_server_rec",
        "PP-LCNet_x1_0_table_cls",
        "SLANeXt_wired",
        "SLANet_plus",
        "RT-DETR-L_wired_table_cell_det",
        "RT-DETR-L_wireless_table_cell_det"
    )
    if ($IncludeFormula) {
        $structureModels += "PP-FormulaNet_plus-L"
    }

    foreach ($target in $cleanupTargets) {
        if (Test-Path $target) {
            Remove-Item -Recurse -Force $target
        }
    }

    foreach ($modelName in $structureModels) {
        $modelDir = Join-Path $repoRoot ".paddlex\official_models\$modelName"
        if ((Test-Path $modelDir) -and -not (Test-ValidModelDir -Path $modelDir)) {
            Remove-Item -Recurse -Force $modelDir
        }
    }
}

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$env:PADDLE_HOME = Join-Path $repoRoot ".paddle_models"
$env:PADDLE_PDX_CACHE_HOME = Join-Path $repoRoot ".paddlex"
$env:PADDLE_INFERENCE_MODEL_DIR = Join-Path $repoRoot ".paddle_inference"
$env:USERPROFILE = Join-Path $tempRoot "home"
$env:HOME = Join-Path $tempRoot "home"
$env:APPDATA = Join-Path $tempRoot "home\\AppData\\Roaming"
$env:LOCALAPPDATA = Join-Path $tempRoot "home\\AppData\\Local"
$env:TEMP = $tempDir
$env:TMP = $tempDir
$env:HF_HOME = Join-Path $tempRoot "hf"
$env:MODELSCOPE_CACHE = Join-Path $tempRoot "modelscope"
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

if ($IncludeFormula) {
    Write-Host "Installing formula conversion dependencies..." -ForegroundColor Cyan
    & $pythonExe -m pip install latex2mathml lxml
}

$formulaModelLine = if ($IncludeFormula) { "    formula_recognition_model_name='PP-FormulaNet_plus-L'," } else { $null }
$formulaToggleLine = if ($IncludeFormula) { "    use_formula_recognition=True," } else { "    use_formula_recognition=False," }

$pySource = @(
    "from paddleocr import PPStructureV3",
    "",
    "engine = PPStructureV3(",
    "    device='$Device',",
    "    layout_detection_model_name='PP-DocLayout_plus-L',",
    "    chart_recognition_model_name='PP-Chart2Table',",
    "    text_detection_model_name='PP-OCRv5_server_det',",
    "    text_recognition_model_name='PP-OCRv5_server_rec',",
    "    table_classification_model_name='PP-LCNet_x1_0_table_cls',",
    "    wired_table_structure_recognition_model_name='SLANeXt_wired',",
    "    wireless_table_structure_recognition_model_name='SLANet_plus',",
    "    wired_table_cells_detection_model_name='RT-DETR-L_wired_table_cell_det',",
    "    wireless_table_cells_detection_model_name='RT-DETR-L_wireless_table_cell_det',",
    $formulaModelLine,
    "    use_doc_orientation_classify=False,",
    "    use_doc_unwarping=False,",
    "    use_textline_orientation=False,",
    "    use_table_recognition=True,",
    $formulaToggleLine,
    "    use_chart_recognition=False,",
    "    use_seal_recognition=False,",
    "    use_region_detection=False,",
    ")",
    "",
    "print('PPStructureV3 init ok')"
)

$pySource | Set-Content -Path $tempPy -Encoding UTF8

$sources = @("BOS", "ModelScope", "AIStudio")
$success = $false
$errors = @()

Write-Host ""
Write-Host "Repo root: $repoRoot"
Write-Host "Python: $pythonExe"
Write-Host "Device: $Device"
Write-Host "Cache: $env:PADDLE_PDX_CACHE_HOME"
Write-Host "Clean interrupted state: $CleanInterrupted"
Write-Host "Include formula model: $IncludeFormula"
Write-Host ""

foreach ($source in $sources) {
    $env:PADDLE_PDX_MODEL_SOURCE = $source
    Write-Host "=== Trying model source: $source ===" -ForegroundColor Cyan

    try {
        & $pythonExe $tempPy
        if ($LASTEXITCODE -eq 0) {
            $success = $true
            break
        }

        $errors += "[$source] python exit code: $LASTEXITCODE"
    }
    catch {
        $errors += "[$source] $($_.Exception.Message)"
    }

    Write-Host ""
}

Write-Host ""
Write-Host "=== Deep capability check ===" -ForegroundColor Cyan
& python $checkScript --deep

if (-not $success) {
    Write-Host ""
    Write-Host "Model download/init did not complete successfully." -ForegroundColor Yellow
    if ($errors.Count -gt 0) {
        Write-Host "Errors:"
        foreach ($err in $errors) {
            Write-Host "  $err"
        }
    }
    exit 1
}

Write-Host ""
Write-Host "PPStructureV3 model initialization finished." -ForegroundColor Green
Write-Host "If deep check still reports missing models, rerun once or switch network." -ForegroundColor Yellow
