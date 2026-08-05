[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$HveAddress,
    [string]$DisplayName = 'Postfix Entra Relay - HVE OAuth',
    [int]$SecretValidityDays = 180
)

$ErrorActionPreference = 'Stop'
$GraphResourceId = '00000003-0000-0000-c000-000000000000'
$ExchangeResourceId = '00000002-0000-0ff1-ce00-000000000000'

$app = New-MgApplication -DisplayName $DisplayName
$servicePrincipal = New-MgServicePrincipal -AppId $app.AppId
$password = Add-MgApplicationPassword -ApplicationId $app.Id -PasswordCredential @{
    displayName = 'Postfix Entra HVE client secret'
    endDateTime = (Get-Date).ToUniversalTime().AddDays($SecretValidityDays)
}

$exchangeSp = Get-MgServicePrincipal -Filter "appId eq '$ExchangeResourceId'"
$mailSendRole = $exchangeSp.AppRoles | Where-Object { $_.Value -eq 'Mail.Send' -and $_.AllowedMemberTypes -contains 'Application' } | Select-Object -First 1
if (-not $mailSendRole) { throw 'Exchange Online Mail.Send application role was not found.' }

New-MgServicePrincipalAppRoleAssignment `
    -ServicePrincipalId $servicePrincipal.Id `
    -PrincipalId $servicePrincipal.Id `
    -ResourceId $exchangeSp.Id `
    -AppRoleId $mailSendRole.Id | Out-Null

Set-HveAccount -Identity $HveAddress -AllowedApplications @{Add=$servicePrincipal.Id}

[pscustomobject]@{
    TenantId = (Get-MgContext).TenantId
    ClientId = $app.AppId
    ServicePrincipalObjectId = $servicePrincipal.Id
    ClientSecret = $password.SecretText
    SecretExpires = $password.EndDateTime
    Note = 'Store ClientSecret now; it is returned only once.'
} | Format-List
