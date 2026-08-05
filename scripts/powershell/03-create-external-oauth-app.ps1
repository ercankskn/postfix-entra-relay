[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RelayMailbox,
    [string]$DisplayName = 'Postfix Entra Relay - External SMTP'
)

$ErrorActionPreference = 'Stop'
$ExchangeResourceId = '00000002-0000-0ff1-ce00-000000000000'

$app = New-MgApplication -DisplayName $DisplayName -IsFallbackPublicClient -PublicClient @{
    RedirectUris = @('http://localhost')
}
$servicePrincipal = New-MgServicePrincipal -AppId $app.AppId
$exchangeSp = Get-MgServicePrincipal -Filter "appId eq '$ExchangeResourceId'"
$smtpScope = $exchangeSp.Oauth2PermissionScopes | Where-Object { $_.Value -eq 'SMTP.Send' } | Select-Object -First 1
if (-not $smtpScope) { throw 'SMTP.Send delegated permission was not found.' }

Update-MgApplication -ApplicationId $app.Id -RequiredResourceAccess @(
    @{
        ResourceAppId = $ExchangeResourceId
        ResourceAccess = @(@{ Id = $smtpScope.Id; Type = 'Scope' })
    }
)

Set-CASMailbox -Identity $RelayMailbox -SmtpClientAuthenticationDisabled $false

[pscustomobject]@{
    TenantId = (Get-MgContext).TenantId
    ClientId = $app.AppId
    ServicePrincipalObjectId = $servicePrincipal.Id
    RelayMailbox = $RelayMailbox
    DelegatedScope = 'https://outlook.office.com/SMTP.Send offline_access'
} | Format-List
