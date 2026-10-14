[CmdletBinding()]
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$frontend = Join-Path $repoRoot 'app\frontend'

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm not found on PATH. Install Node.js 22 or newer, then re-run."
}

Push-Location $frontend
try {
    if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    }
    if (-not $SkipBuild) {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
    }
    npm run start
} finally {
    Pop-Location
}
