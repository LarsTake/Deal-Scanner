#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ipaddress[]]$ServerAddresses,
    [Parameter(Mandatory)] [string]$HomeNetwork
)

$ErrorActionPreference = 'Stop'

# Optional: auf dem Server ausfuehren. Alle Programme/Ports im angegebenen Netz erlauben.
$addresses = @($ServerAddresses | ForEach-Object { $_.ToString() })
$networkParts = $HomeNetwork.Split('/')
$networkAddress = $null
$prefixLength = 0
if ($networkParts.Count -ne 2 -or
    -not [ipaddress]::TryParse($networkParts[0], [ref]$networkAddress) -or
    $networkAddress.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or
    -not [int]::TryParse($networkParts[1], [ref]$prefixLength) -or
    $prefixLength -lt 1 -or $prefixLength -gt 32) {
    throw 'HomeNetwork muss ein IPv4-Netz mit Praefix sein, z.B. 192.168.1.0/24.'
}

$presentAddresses = @(Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress)
if ($addresses | Where-Object { $_ -notin $presentAddresses }) {
    throw 'Mindestens eine Server-IP-Adresse ist auf diesem PC nicht vorhanden. Bitte Adressen und Server pruefen.'
}

foreach ($direction in @('Inbound', 'Outbound')) {
    $ruleName = "ThinkCentre-Heimnetz-$direction"
    Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule

    New-NetFirewallRule `
        -Name $ruleName `
        -DisplayName "ThinkCentre: LAN und WLAN - $direction" `
        -Direction $direction `
        -Action Allow `
        -Enabled True `
        -Profile Any `
        -Program Any `
        -Protocol Any `
        -LocalAddress $addresses `
        -RemoteAddress $HomeNetwork | Out-Null
}

Write-Host 'Freigaben fuer alle Programme und Ports im Heimnetz sind eingerichtet.' -ForegroundColor Green
Write-Host ('Serveradressen: ' + ($addresses -join ', ') + ' | Heimnetz: ' + $HomeNetwork)
Write-Host 'Die Firewall bleibt aktiviert. Docker-Portbindungen werden nicht veraendert.'
