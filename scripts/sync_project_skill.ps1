[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }),
    [string]$WorkBuddyHome = $(Join-Path $HOME '.workbuddy'),
    [switch]$Check,
    [switch]$SkipWorkBuddy
)

$ErrorActionPreference = 'Stop'

$SkillName = 'advance-campus-rag-research'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$source = (Resolve-Path -LiteralPath (Join-Path $repoRoot "skills\$SkillName")).Path
$sourceFiles = Get-ChildItem -LiteralPath $source -Recurse -File

function Get-SourceRelativePath {
    param([string]$FullName)

    $sourcePrefix = $source.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $FullName.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to copy a file outside the repository skill source: $FullName"
    }
    return $FullName.Substring($sourcePrefix.Length)
}

function Sync-ToRoot {
    param([string]$SkillsHome)

    $skillsRoot = [System.IO.Path]::GetFullPath((Join-Path $SkillsHome 'skills'))
    $target = [System.IO.Path]::GetFullPath((Join-Path $skillsRoot $SkillName))
    $requiredPrefix = $skillsRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar

    if (-not $target.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to use target outside the skills directory: $target"
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
        return
    }

    New-Item -ItemType Directory -Force -Path $target | Out-Null
    foreach ($file in $sourceFiles) {
        $relative = Get-SourceRelativePath -FullName $file.FullName
        $destination = Join-Path $target $relative
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
    Set-Content -LiteralPath (Join-Path $target '.repository-source') -Encoding UTF8 -Value $source
    Write-Output "Synced: $target"
}

Write-Output "Source: $source"
Sync-ToRoot -SkillsHome $CodexHome

if (-not $SkipWorkBuddy) {
    Sync-ToRoot -SkillsHome $WorkBuddyHome
}
