[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$secretDirectory = Join-Path $projectRoot '.secrets'
$secretFile = Join-Path $secretDirectory 'service-password.txt'
New-Item -ItemType Directory -Force -Path $secretDirectory | Out-Null
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$grant = '*{0}:(OI)(CI)F' -f $identity.User.Value
& icacls.exe $secretDirectory /inheritance:r /grant:r $grant | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Ordnerberechtigungen konnten nicht gesetzt werden.' }
if (Test-Path -LiteralPath $secretFile) {
    throw 'Secret-Datei existiert bereits. Vor einem bewussten Passwortwechsel separat sichern/entfernen.'
}
$secret = Read-Host 'Passwort des Scanner-Auth-Benutzers (NICHT Datenbankpasswort)' -AsSecureString
$pointer = [IntPtr]::Zero
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    $passwordValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ([string]::IsNullOrEmpty($passwordValue)) { throw 'Passwort darf nicht leer sein.' }
    [IO.File]::WriteAllText($secretFile, $passwordValue, [Text.UTF8Encoding]::new($false))
}
finally {
    $passwordValue = $null
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $secret.Dispose()
}
Write-Host 'Passwort lokal gespeichert. Es wurde nicht ausgegeben. Datei nicht teilen oder hochladen.'
