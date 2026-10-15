[CmdletBinding()]
param(
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

if ($Python -ne '') {
    $target = $Python
} elseif (Test-Path -LiteralPath $venvPython) {
    $target = $venvPython
} else {
    throw "Isolated environment not found. Run scripts\setup_env.ps1 first, or pass -Python <path>."
}

Push-Location $repoRoot
try {
    Write-Output "[1/4] validate_research_data"
    & $target 'scripts/validate_research_data.py'
    if ($LASTEXITCODE -ne 0) { throw "validate_research_data failed." }

    Write-Output "[2/4] validate_process_records"
    & $target 'scripts/validate_process_records.py'
    if ($LASTEXITCODE -ne 0) { throw "validate_process_records failed." }

    Write-Output "[3/4] validate_stage2_content"
    & $target 'scripts/validate_stage2_content.py'
    if ($LASTEXITCODE -ne 0) { throw "validate_stage2_content failed." }

    Write-Output "[4/4] unit tests"
    & $target '-m' 'unittest' 'discover' '-s' 'tests' '-p' 'test_*.py' '-q'
    if ($LASTEXITCODE -ne 0) { throw "unit tests failed." }
} finally {
    Pop-Location
}

Write-Output "All checks passed."
