[CmdletBinding()]
param(
    [string]$PostgresBin = $env:DEAL_SCANNER_POSTGRES_BIN,
    [switch]$FullSuite
)

$ErrorActionPreference = 'Stop'

if (-not $PostgresBin) {
    $postgres = Get-Command postgres -ErrorAction SilentlyContinue
    if ($postgres) {
        $PostgresBin = Split-Path -Parent $postgres.Source
    }
}

if (-not $PostgresBin -or -not (Test-Path -LiteralPath (Join-Path $PostgresBin 'initdb.exe'))) {
    throw 'PostgreSQL 17 wurde nicht gefunden. DEAL_SCANNER_POSTGRES_BIN muss auf dessen bin-Verzeichnis zeigen.'
}
$postgresVersion = & (Join-Path $PostgresBin 'postgres.exe') --version
if ($LASTEXITCODE -ne 0 -or $postgresVersion -notmatch '\s17\.') {
    throw "PostgreSQL 17 ist erforderlich; gefunden: $postgresVersion"
}

$uv = Get-Command uv -ErrorAction Stop
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$clusterRoot = Join-Path $temporaryRoot ("deal-scanner-pgtest-{0}" -f [guid]::NewGuid().ToString('N'))
$dataDirectory = Join-Path $clusterRoot 'data'
$logFile = Join-Path $clusterRoot 'postgres.log'
$previousUrl = $env:DEAL_SCANNER_TEST_POSTGRES_URL
$started = $false

$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()

function Invoke-PostgresCommand {
    param(
        [Parameter(Mandatory)] [string]$Executable,
        [Parameter(Mandatory)] [string[]]$Arguments
    )
    & (Join-Path $PostgresBin $Executable) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable wurde mit Exit-Code $LASTEXITCODE beendet."
    }
}

try {
    New-Item -ItemType Directory -Path $clusterRoot | Out-Null
    Invoke-PostgresCommand -Executable initdb.exe -Arguments @(
        '-D', $dataDirectory, '-U', 'postgres', '-A', 'trust', '--encoding', 'UTF8', '--locale', 'C'
    )
    Invoke-PostgresCommand -Executable pg_ctl.exe -Arguments @(
        '-D', $dataDirectory, '-l', $logFile, '-o', "-h 127.0.0.1 -p $port", 'start', '-w'
    )
    $started = $true
    Invoke-PostgresCommand -Executable createdb.exe -Arguments @(
        '-h', '127.0.0.1', '-p', [string]$port, '-U', 'postgres', 'deal_scanner_test'
    )

    $env:DEAL_SCANNER_TEST_POSTGRES_URL = "postgresql://postgres@127.0.0.1:$port/deal_scanner_test"
    $pytestArguments = if ($FullSuite) {
        @('run', 'pytest', '-m', 'not live', '-ra')
    } else {
        @('run', 'pytest', 'tests/test_postgres_rls.py', '-ra')
    }
    & $uv.Source @pytestArguments
    if ($LASTEXITCODE -ne 0) {
        throw "pytest wurde mit Exit-Code $LASTEXITCODE beendet."
    }
}
finally {
    if ($started) {
        & (Join-Path $PostgresBin 'pg_ctl.exe') -D $dataDirectory stop -m fast -w
    }
    $env:DEAL_SCANNER_TEST_POSTGRES_URL = $previousUrl

    $resolvedCluster = [IO.Path]::GetFullPath($clusterRoot)
    if ($resolvedCluster.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedCluster).StartsWith('deal-scanner-pgtest-', [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $resolvedCluster -Recurse -Force -ErrorAction SilentlyContinue
    }
}
