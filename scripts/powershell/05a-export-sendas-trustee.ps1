[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Trustee,
    [Parameter(Mandatory)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$results = foreach ($recipient in Get-Recipient -ResultSize Unlimited) {
    $permission = Get-RecipientPermission -Identity $recipient.Identity -Trustee $Trustee -ErrorAction SilentlyContinue |
        Where-Object { $_.AccessRights -contains 'SendAs' -and -not $_.IsInherited }
    if ($permission) {
        [pscustomobject]@{
            Sender = $recipient.PrimarySmtpAddress.ToString()
            RecipientType = $recipient.RecipientTypeDetails
            Trustee = $Trustee
        }
    }
}
$results | Sort-Object Sender | Export-Csv -Path $OutputPath -NoTypeInformation -Encoding utf8BOM
Write-Host "SENDAS_EXPORTED count=$($results.Count) path=$OutputPath"
