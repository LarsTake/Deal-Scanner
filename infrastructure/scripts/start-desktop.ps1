[CmdletBinding()]
param([switch]$LocalServer)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$desktopExecutable = Join-Path $env:LOCALAPPDATA 'Deal Scanner\deal-scanner-desktop.exe'
if (-not (Test-Path -LiteralPath $desktopExecutable)) {
    throw 'Die Windows-App ist noch nicht installiert.'
}

$toolPaths = @(
    (Join-Path $repositoryRoot '.data\tools\pnpm'),
    (Join-Path $env:USERPROFILE '.local\bin'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Ollama')
)
$env:Path = ($toolPaths -join ';') + ';' + $env:Path

# The desktop app owns its worker so its Start/Stop and image toggle remain authoritative.
if ($LocalServer) {
    & (Join-Path $PSScriptRoot 'start-local.ps1') -NoBrowser -SkipWorker
}
Start-Process -FilePath $desktopExecutable
