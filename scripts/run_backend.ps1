[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Isolated environment not found at $python. Run scripts\setup_env.ps1 first."
}

Push-Location $repoRoot
try {
    $uvicornArgs = @('-m', 'uvicorn', 'app.backend.main:app', '--host', $BindHost, '--port', $Port)
    if ($Reload) { $uvicornArgs += '--reload' }
    & $python @uvicornArgs
} finally {
    Pop-Location
}
