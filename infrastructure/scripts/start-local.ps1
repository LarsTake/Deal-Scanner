[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$NoBrowser,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$environmentFile = Join-Path $repositoryRoot '.env'
$runtimeDirectory = Join-Path $repositoryRoot '.data\runtime'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw 'Die Datei .env fehlt. In PowerShell: Copy-Item .env.example .env; in CMD: copy .env.example .env'
}

$uv = Get-Command uv -ErrorAction Stop
$pnpm = Get-Command pnpm.cmd -ErrorAction Stop
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null

Push-Location $repositoryRoot
try {
    if ($Install) {
        & $uv.Source --system-certs sync --all-packages --frozen
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync wurde mit Exit-Code $LASTEXITCODE beendet."
        }
        & $pnpm.Source install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) {
            throw "pnpm install wurde mit Exit-Code $LASTEXITCODE beendet."
        }
    }

    function Test-LocalPort {
        param([Parameter(Mandatory)] [int]$Port)
        return [bool](Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }

    function Test-ProcessCommand {
        param([Parameter(Mandatory)] [string]$Pattern)
        return [bool](
            Get-CimInstance Win32_Process |
                Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern } |
                Select-Object -First 1
        )
    }

    function Get-EnvironmentFileValue {
        param([Parameter(Mandatory)] [string]$Name)
        $prefix = "$Name="
        $line = Get-Content -LiteralPath $environmentFile |
            Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) } |
            Select-Object -Last 1
        if (-not $line) {
            return ''
        }
        return $line.Substring($prefix.Length).Trim()
    }

    function Start-LoggedProcess {
        param(
            [Parameter(Mandatory)] [string]$Name,
            [Parameter(Mandatory)] [string]$Executable,
            [Parameter(Mandatory)] [string[]]$Arguments
        )
        $stdout = Join-Path $runtimeDirectory "$Name-$timestamp.out.log"
        $stderr = Join-Path $runtimeDirectory "$Name-$timestamp.err.log"
        return Start-Process `
            -FilePath $Executable `
            -ArgumentList $Arguments `
            -WorkingDirectory $repositoryRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru
    }

    if ($Restart) {
        $portsToKill = @(8000, 4200)
        foreach ($port in $portsToKill) {
            $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            foreach ($conn in $connections) {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
        Get-CimInstance Win32_Process |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -and
                $_.CommandLine -match 'deal-scanner-(?:api|worker|scheduler)(?:\.exe)?'
            } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }

    $started = [ordered]@{}
    $ollamaModels = @(
        Get-EnvironmentFileValue -Name 'DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL'
        Get-EnvironmentFileValue -Name 'DEAL_SCANNER_OLLAMA_REASONING_MODEL'
        Get-EnvironmentFileValue -Name 'DEAL_SCANNER_OLLAMA_VISION_MODEL'
        Get-EnvironmentFileValue -Name 'DEAL_SCANNER_OLLAMA_EMBEDDING_MODEL'
        Get-EnvironmentFileValue -Name 'DEAL_SCANNER_OLLAMA_TEXT_MODEL'
    ) | Where-Object { $_ }
    $ollamaUrl = Get-EnvironmentFileValue -Name 'DEAL_SCANNER_OLLAMA_URL'
    if (
        $ollamaModels.Count -gt 0 -and
        $ollamaUrl -match '^http://(?:127\.0\.0\.1|localhost):(?<port>\d+)' -and
        -not (Test-LocalPort -Port ([int]$Matches.port))
    ) {
        $ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
        if ($ollama) {
            $started.ollama = (
                Start-LoggedProcess -Name 'ollama' -Executable $ollama.Source -Arguments @('serve')
            ).Id
        }
    }
    if (-not (Test-LocalPort -Port 8000)) {
        $started.api = (
            Start-LoggedProcess -Name 'api' -Executable $uv.Source -Arguments @(
                '--system-certs', 'run', '--package', 'deal-scanner-api', 'deal-scanner-api'
            )
        ).Id
    }
    if (-not (Test-ProcessCommand -Pattern 'deal-scanner-worker\.exe')) {
        $started.worker = (
            Start-LoggedProcess -Name 'worker' -Executable $uv.Source -Arguments @(
                '--system-certs', 'run', '--package', 'deal-scanner-worker', 'deal-scanner-worker'
            )
        ).Id
    }
    if (-not (Test-ProcessCommand -Pattern 'deal-scanner-scheduler\.exe')) {
        $started.scheduler = (
            Start-LoggedProcess -Name 'scheduler' -Executable $uv.Source -Arguments @(
                '--system-certs', 'run', '--package', 'deal-scanner-scheduler', 'deal-scanner-scheduler'
            )
        ).Id
    }
    if (-not (Test-LocalPort -Port 4200)) {
        $started.ui = (
            Start-LoggedProcess -Name 'ui' -Executable $pnpm.Source -Arguments @(
                '--filter', '@deal-scanner/desktop', 'start'
            )
        ).Id
    }

    $apiReady = $false
    $uiReady = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if (-not $apiReady) {
            try {
                $apiResponse = Invoke-WebRequest `
                    -Uri 'http://127.0.0.1:8000/api/v1/health/ready' `
                    -UseBasicParsing `
                    -TimeoutSec 1
                $apiReady = $apiResponse.StatusCode -eq 200
            }
            catch {
                $apiReady = $false
            }
        }
        if (-not $uiReady) {
            try {
                $uiResponse = Invoke-WebRequest `
                    -Uri 'http://127.0.0.1:4200/' `
                    -UseBasicParsing `
                    -TimeoutSec 1
                $uiReady = $uiResponse.StatusCode -eq 200
            }
            catch {
                $uiReady = $false
            }
        }
        if ($apiReady -and $uiReady) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $apiReady -or -not $uiReady) {
        throw "Lokaler Start unvollstaendig. API bereit: $apiReady; Oberflaeche bereit: $uiReady. Logs: $runtimeDirectory"
    }

    $status = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/system/status' -TimeoutSec 5
    Write-Host "Deal Scanner laeuft: http://127.0.0.1:4200/" -ForegroundColor Green
    Write-Host "API: http://127.0.0.1:8000/api/docs"
    Write-Host "System: $($status.status), Worker: $($status.components.worker.status), offene Jobs: $($status.openJobs)"
    Write-Host "Logs: $runtimeDirectory"
    if ($started.Count) {
        Write-Host "Neu gestartete Prozesse: $($started.Keys -join ', ')"
    }
    else {
        Write-Host 'Alle Prozesse liefen bereits.'
    }
    if (-not $NoBrowser) {
        Start-Process 'http://127.0.0.1:4200/'
    }
}
finally {
    Pop-Location
}
