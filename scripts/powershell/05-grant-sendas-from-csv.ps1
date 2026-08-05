[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$CsvPath,
    [Parameter(Mandatory)][string]$RelayMailbox
)

$ErrorActionPreference = 'Stop'
$rows = Import-Csv -Path $CsvPath
foreach ($row in $rows) {
    $sender = [string]$row.Sender
    if ([string]::IsNullOrWhiteSpace($sender)) { continue }

    $recipient = Get-Recipient -Identity $sender -ErrorAction Stop
    $already = Get-RecipientPermission -Identity $recipient.Identity -Trustee $RelayMailbox -ErrorAction SilentlyContinue |
        Where-Object { $_.AccessRights -contains 'SendAs' -and -not $_.IsInherited }

    if (-not $already -and $PSCmdlet.ShouldProcess($sender, "Grant SendAs to $RelayMailbox")) {
        Add-RecipientPermission -Identity $recipient.Identity -Trustee $RelayMailbox -AccessRights SendAs -Confirm:$false
    }
}
Write-Host 'SENDAS_IMPORT_COMPLETE'
