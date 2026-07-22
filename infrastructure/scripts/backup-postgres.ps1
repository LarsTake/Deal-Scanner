[CmdletBinding()]
param(
    [string]$DatabaseUrl = $env:DEAL_SCANNER_SUPABASE_DB_URL,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\..\.backups')
)

$ErrorActionPreference = 'Stop'

if (-not $DatabaseUrl -or -not $DatabaseUrl.StartsWith('postgresql://', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'DEAL_SCANNER_SUPABASE_DB_URL muss eine PostgreSQL-Verbindungs-URL enthalten.'
}

$pgDump = Get-Command pg_dump -ErrorAction Stop
$pgRestore = Get-Command pg_restore -ErrorAction Stop
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $resolvedOutput "deal-scanner-$timestamp.dump"
$connection = [Uri]$DatabaseUrl
$credentials = $connection.UserInfo.Split(':', 2)
if ($credentials.Count -lt 1 -or -not $credentials[0] -or $connection.AbsolutePath -eq '/') {
    throw 'Die PostgreSQL-Verbindungs-URL muss Benutzer und Datenbank enthalten.'
}
$connectionEnvironment = @{
    PGHOST = $connection.Host
    PGPORT = if ($connection.IsDefaultPort) { '5432' } else { [string]$connection.Port }
    PGUSER = [Uri]::UnescapeDataString($credentials[0])
    PGPASSWORD = if ($credentials.Count -eq 2) { [Uri]::UnescapeDataString($credentials[1]) } else { '' }
    PGDATABASE = [Uri]::UnescapeDataString($connection.AbsolutePath.TrimStart('/'))
}
foreach ($pair in $connection.Query.TrimStart('?').Split('&', [StringSplitOptions]::RemoveEmptyEntries)) {
    $parts = $pair.Split('=', 2)
    if ([Uri]::UnescapeDataString($parts[0]) -eq 'sslmode' -and $parts.Count -eq 2) {
        $connectionEnvironment.PGSSLMODE = [Uri]::UnescapeDataString($parts[1])
    }
}
$previousEnvironment = @{}
foreach ($name in $connectionEnvironment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    # Libpq connection variables keep credentials out of process arguments and shell history.
    foreach ($entry in $connectionEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    & $pgDump.Source --format=custom --compress=9 --no-owner --no-privileges --file $backupPath
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump wurde mit Exit-Code $LASTEXITCODE beendet."
    }
    & $pgRestore.Source --list $backupPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Die erzeugte Sicherung konnte nicht als PostgreSQL-Custom-Archiv gelesen werden.'
    }
}
catch {
    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }
    throw
}
finally {
    foreach ($entry in $previousEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
}

Get-Item -LiteralPath $backupPath
