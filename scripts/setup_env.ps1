[CmdletBinding()]
param(
    [string]$BasePython = 'python'
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPath = Join-Path $repoRoot '.venv'

if (Test-Path -LiteralPath $venvPath) {
    Write-Output "Reusing existing environment at $venvPath"
} else {
    Write-Output "Creating isolated environment at $venvPath"
    & $BasePython '-m' 'venv' $venvPath
    if ($LASTEXITCODE -ne 0) { throw "python -m venv failed. Check that '$BasePython' is Python 3.11+." }
}

$python = Join-Path $venvPath 'Scripts\python.exe'

& $python '-m' 'pip' 'install' '--upgrade' 'pip'
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

& $python '-m' 'pip' 'install' '-r' (Join-Path $repoRoot 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw "dependency install failed." }

& $python '-c' "import numpy, sklearn, rank_bm25, faiss, httpx, jsonschema, pypdf, fastapi; print('dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "dependency import check failed." }

Write-Output "Environment ready: $python"
