[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$AdminUpn
)

$ErrorActionPreference = 'Stop'
Import-Module ExchangeOnlineManagement -ErrorAction Stop
Import-Module Microsoft.Graph.Authentication -ErrorAction Stop

Connect-ExchangeOnline -UserPrincipalName $AdminUpn -ShowBanner:$false
Connect-MgGraph -Scopes @(
    'Application.ReadWrite.All',
    'Directory.ReadWrite.All',
    'Mail.Send'
) -NoWelcome

Write-Host 'MICROSOFT_365_CONNECTIONS_OK'
