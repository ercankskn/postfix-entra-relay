[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$HveAddress,
    [Parameter(Mandatory)][string]$DisplayName,
    [Parameter(Mandatory)][string]$ReplyTo,
    [Parameter(Mandatory)][string]$BillingPolicyId
)

$ErrorActionPreference = 'Stop'
$existing = Get-MailUser -Identity $HveAddress -ErrorAction SilentlyContinue
if (-not $existing) {
    if ($PSCmdlet.ShouldProcess($HveAddress, 'Create HVE mail user')) {
        New-MailUser -HighVolumeMail -Name $DisplayName -MicrosoftOnlineServicesID $HveAddress
    }
}

if ($PSCmdlet.ShouldProcess($HveAddress, 'Set HVE properties')) {
    Set-MailUser -Identity $HveAddress -EmailAddresses @("SMTP:$HveAddress", "smtp:$ReplyTo")
    Set-HveAccount -Identity $HveAddress -BillingPolicyId $BillingPolicyId
}

Get-HveAccount -Identity $HveAddress | Format-List Identity,BillingPolicyStatus,AllowedApplications
