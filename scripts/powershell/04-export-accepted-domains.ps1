[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$OutputPath,
    [switch]$IncludeInternalRelay
)

$ErrorActionPreference = 'Stop'
$domains = Get-AcceptedDomain | Where-Object {
    $_.DomainType -eq 'Authoritative' -or ($IncludeInternalRelay -and $_.DomainType -eq 'InternalRelay')
} | Sort-Object DomainName

$domains.DomainName.ToString() | Set-Content -Path $OutputPath -Encoding utf8NoBOM
Write-Host "ACCEPTED_DOMAINS_EXPORTED count=$($domains.Count) path=$OutputPath"
