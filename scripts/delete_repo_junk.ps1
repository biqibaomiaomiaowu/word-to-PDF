[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stageName = ([char]0x5F85).ToString() + ([char]0x5220)
$deletePrefix = ([char]0x5220).ToString()
$mappingFileName = ([char]0x6620).ToString() + ([char]0x5C04) + ".txt"
$stagingDir = Join-Path $repoRoot $stageName
$mappingPath = Join-Path $stagingDir $mappingFileName

function Add-Target {
    param(
        [System.Collections.Generic.HashSet[string]]$Set,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    $normalized = [System.IO.Path]::GetFullPath($Path)
    [void]$Set.Add($normalized)
}

$targets = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

if (Test-Path -LiteralPath $mappingPath) {
    foreach ($line in Get-Content -LiteralPath $mappingPath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line -split "`t", 2
        if ($parts.Count -lt 2) {
            continue
        }

        $tag = $parts[0].Trim()
        $sourceRel = $parts[1].Trim()

        Add-Target $targets (Join-Path $repoRoot $sourceRel)
        Add-Target $targets (Join-Path $stagingDir $tag)
    }
}

$explicitRelPaths = @(
    ".cache\ppstructure_download.py",
    ".cache\tmp",
    ".paddlex_tmp",
    "tmp_structure_test",
    "tmp_structure_out",
    "tmp_probe_pages",
    "temp_ppstructure_download.py",
    "dev_output.log",
    "frontend_dev.log",
    "npm_install.log",
    "start_all.log",
    "start_dev.log",
    "fake.pdf",
    "test.txt",
    "AppData",
    "Microsoft",
    "pip",
    "backend\pip",
    "scripts\start_all_bootstrap.py",
    "backend\app\services\run_paddle_structure_v3.py",
    "backend\app\services\run_paddle_ocr_v2.py"
)

foreach ($rel in $explicitRelPaths) {
    Add-Target $targets (Join-Path $repoRoot $rel)
}

Get-ChildItem -LiteralPath $repoRoot -File -Force |
    Where-Object { $_.Name -match '^[0-9A-Za-z_]{8}$' -or $_.Name -match ("^{0}\d+$" -f [regex]::Escape($deletePrefix)) } |
    ForEach-Object { Add-Target $targets $_.FullName }

if (Test-Path -LiteralPath $stagingDir) {
    Get-ChildItem -LiteralPath $stagingDir -Force |
        Where-Object { $_.Name -match ("^{0}\d+$" -f [regex]::Escape($deletePrefix)) } |
        ForEach-Object { Add-Target $targets $_.FullName }

    Add-Target $targets $mappingPath
    Add-Target $targets $stagingDir
}

$existingTargets = $targets |
    Where-Object { Test-Path -LiteralPath $_ } |
    Sort-Object Length -Descending

Write-Host "Repo root: $repoRoot"
Write-Host "Dry run: $DryRun"
Write-Host "Matched existing paths: $($existingTargets.Count)"

$deleted = New-Object System.Collections.Generic.List[string]
$failed = New-Object System.Collections.Generic.List[object]

foreach ($path in $existingTargets) {
    try {
        if ($DryRun) {
            Write-Host "[DRY] $path"
        }
        else {
            Remove-Item -LiteralPath $path -Recurse -Force
            $deleted.Add($path) | Out-Null
            Write-Host "[DEL] $path"
        }
    }
    catch {
        $failed.Add([pscustomobject]@{
            Path = $path
            Error = $_.Exception.Message
        }) | Out-Null
        Write-Warning ("Failed: {0} :: {1}" -f $path, $_.Exception.Message)
    }
}

if (-not $DryRun) {
    if (Test-Path -LiteralPath $mappingPath) {
        Remove-Item -LiteralPath $mappingPath -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path -LiteralPath $stagingDir) {
        $remaining = Get-ChildItem -LiteralPath $stagingDir -Force -ErrorAction SilentlyContinue
        if (-not $remaining) {
            Remove-Item -LiteralPath $stagingDir -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host ""
Write-Host "Summary"
Write-Host "-------"
Write-Host "Deleted: $($deleted.Count)"
Write-Host "Failed : $($failed.Count)"

if ($failed.Count -gt 0) {
    $failed | Format-Table -AutoSize
}
