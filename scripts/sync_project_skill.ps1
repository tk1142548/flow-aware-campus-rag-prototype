[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }),
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$source = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'skills\advance-campus-rag-research')).Path
$skillsRoot = [System.IO.Path]::GetFullPath((Join-Path $CodexHome 'skills'))
$target = [System.IO.Path]::GetFullPath((Join-Path $skillsRoot 'advance-campus-rag-research'))
$requiredPrefix = $skillsRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar

if (-not $target.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use target outside the Codex skills directory: $target"
}

$sourceFiles = Get-ChildItem -LiteralPath $source -Recurse -File

function Get-SourceRelativePath {
    param([string]$FullName)

    $sourcePrefix = $source.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $FullName.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to copy a file outside the repository skill source: $FullName"
    }
    return $FullName.Substring($sourcePrefix.Length)
}

if ($Check) {
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw "Installed skill does not exist: $target"
    }

    foreach ($file in $sourceFiles) {
        $relative = Get-SourceRelativePath -FullName $file.FullName
        $installed = Join-Path $target $relative
        if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
            throw "Installed skill is missing: $relative"
        }
        if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash) {
            throw "Installed skill differs from repository source: $relative"
        }
    }

    Write-Output "Skill mirror matches repository source: $target"
    exit 0
}

New-Item -ItemType Directory -Force -Path $target | Out-Null

foreach ($file in $sourceFiles) {
    $relative = Get-SourceRelativePath -FullName $file.FullName
    $destination = Join-Path $target $relative
    $destinationDirectory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
}

$marker = Join-Path $target '.repository-source'
Set-Content -LiteralPath $marker -Encoding UTF8 -Value $source

Write-Output "Synced project skill from repository source."
Write-Output "Source: $source"
Write-Output "Target: $target"
