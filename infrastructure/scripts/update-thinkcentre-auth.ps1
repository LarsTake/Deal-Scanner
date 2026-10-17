[CmdletBinding()]
param(
    [Parameter(Mandatory)] [uri]$ServerUrl,
    [switch]$IncludeWeb
)

$ErrorActionPreference = 'Stop'
Get-Command docker -ErrorAction Stop | Out-Null

# Use the existing deployment, including its current Compose overrides and volumes.
$containers = @(& docker ps --filter 'label=com.docker.compose.service=api' --format '{{.ID}}')
if ($LASTEXITCODE -ne 0 -or $containers.Count -ne 1) {
    throw 'Genau einen laufenden Scanner-API-Container erwartet. Bitte Docker auf dem ThinkCentre pruefen.'
}
$container = @((& docker inspect $containers[0]) | ConvertFrom-Json)[0]
$labels = $container.Config.Labels
$root = $labels.'com.docker.compose.project.working_dir'
$files = @($labels.'com.docker.compose.project.config_files' -split ',')
if (-not $root -or -not $files.Count -or -not (Test-Path -LiteralPath $root)) {
    throw 'Das urspruengliche Compose-Projektverzeichnis ist auf diesem Windows-Host nicht verfuegbar.'
}
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Compose-Datei fehlt: $file" }
}

Push-Location $root
try {
    $sourceFile = Join-Path $root 'apps\server-api\src\deal_scanner_api\main.py'
    if (-not (Test-Path -LiteralPath $sourceFile)) { throw 'API-Quellcode im Compose-Projekt nicht gefunden.' }
    & git pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'Git-Aktualisierung fehlgeschlagen. Vorhandene lokale Aenderungen wurden nicht verworfen.' }
    if (-not (Select-String -LiteralPath $sourceFile -Pattern '/api/v1/client-config' -SimpleMatch -Quiet)) {
        throw 'Der ausgecheckte Server-Code enthaelt den Konfigurationsendpunkt noch nicht.'
    }

    # Public connection data remains on the server; never print the .env or keys.
    $envPath = Join-Path $root '.env'
    $envText = [IO.File]::ReadAllText($envPath)
    foreach ($name in @('DEAL_SCANNER_SUPABASE_URL', 'DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY')) {
        $match = [regex]::Match($envText, '(?m)^' + [regex]::Escape($name) + '[ \t]*=[ \t]*([^\r\n]*)')
        if (-not $match.Success -or -not $match.Groups[1].Value.Trim().Trim('"', "'")) {
            throw "$name fehlt in der zentralen Server-.env. Einmal dort hinterlegen; auf den Endgeraeten ist kein Schluessel erforderlich."
        }
    }

    $cors = [regex]::Match($envText, '(?m)^DEAL_SCANNER_CORS_ORIGINS=([^\r\n]*)')
    if ($cors.Success -and $cors.Groups[1].Value -notmatch '(^|,)http://tauri\.localhost(,|$)') {
        $backupDir = Join-Path $root '.backups'
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Copy-Item -LiteralPath $envPath -Destination (Join-Path $backupDir ('env-before-desktop-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt'))
        $replacement = 'DEAL_SCANNER_CORS_ORIGINS=' + $cors.Groups[1].Value.Trim().Trim('"', "'") + ',http://tauri.localhost,tauri://localhost'
        $envText = $envText.Remove($cors.Index, $cors.Length).Insert($cors.Index, $replacement)
        [IO.File]::WriteAllText($envPath, $envText, (New-Object Text.UTF8Encoding($false)))
    }

    $composeArgs = @('compose')
    foreach ($file in $files) { $composeArgs += @('-f', $file) }
    & docker @composeArgs config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose-Konfiguration ungueltig.' }
    $services = @('api')
    if ($IncludeWeb) {
        $availableServices = @(& docker @composeArgs config --services)
        if ($LASTEXITCODE -ne 0 -or 'web' -notin $availableServices) {
            throw 'IncludeWeb erwartet einen Web-Service im selben Compose-Projekt.'
        }
        $services += 'web'
    }
    foreach ($service in $services) {
        Write-Host "Baue $service (nacheinander, bestehende Container laufen weiter)..."
        & docker @composeArgs --parallel 1 build $service
        if ($LASTEXITCODE -ne 0) {
            throw "Build von $service fehlgeschlagen; kein Container wurde durch dieses Update ersetzt. Bei RPC/EOF zuerst Docker Desktop und 'docker info' pruefen, dann erneut starten."
        }
    }
    & docker @composeArgs up -d --no-deps @services
    if ($LASTEXITCODE -ne 0) { throw 'API konnte nicht aktualisiert werden.' }

    $endpoint = $ServerUrl.AbsoluteUri.TrimEnd('/') + '/api/v1/client-config'
    $response = $null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $endpoint -Headers @{ Origin = 'http://tauri.localhost' } -UseBasicParsing -TimeoutSec 3
            break
        } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $response) { throw 'Die aktualisierte API antwortet noch nicht ueber die WLAN-Adresse.' }
    $public = $response.Content | ConvertFrom-Json
    if ($public.authMode -ne 'supabase' -or -not $public.supabaseUrl -or -not $public.supabasePublishableKey) {
        throw 'Der Server gibt noch keine vollstaendige oeffentliche Supabase-Konfiguration frei. Auth-Modus und oeffentlichen Publishable-/Anon-Key in der Server-.env pruefen.'
    }
    if ($response.Headers['Access-Control-Allow-Origin'] -ne 'http://tauri.localhost') {
        throw 'Der Konfigurationsendpunkt funktioniert, aber die Desktop-Herkunft ist noch nicht per CORS freigegeben.'
    }
    Write-Host 'OK: WLAN-API, automatische Supabase-Konfiguration und Desktop-Zugriff funktionieren.' -ForegroundColor Green
    Write-Host 'Die Windows-App kann jetzt ohne manuelle Supabase-URL oder Schluessel verbunden werden.'
} finally {
    Pop-Location
}
