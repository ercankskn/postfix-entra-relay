[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$HveAddress,
    [Parameter(Mandatory)][string]$RelayMailbox,
    [Parameter(Mandatory)][string]$HveServicePrincipalObjectId
)

$ErrorActionPreference = 'Stop'
$hve = Get-HveAccount -Identity $HveAddress
$mailbox = Get-EXOMailbox -Identity $RelayMailbox -Properties SmtpClientAuthenticationDisabled
$allowed = @($hve.AllowedApplications) -contains $HveServicePrincipalObjectId

[pscustomobject]@{
    HveAddress = $HveAddress
    BillingPolicyStatus = $hve.BillingPolicyStatus
    HveAppAllowed = $allowed
    RelayMailbox = $RelayMailbox
    SmtpClientAuthenticationDisabled = $mailbox.SmtpClientAuthenticationDisabled
    Ready = ($hve.BillingPolicyStatus -eq 'BillingPolicyValid' -and $allowed -and -not $mailbox.SmtpClientAuthenticationDisabled)
} | Format-List
