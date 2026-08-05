# Architecture Summary

Postfix Entra Relay accepts application and device email and chooses the Microsoft 365 delivery path per recipient:

- Authoritative accepted-domain recipients are passed to a Python `pipe(8)` helper and submitted to `smtp.hve.mx.microsoft:587` with OAuth client credentials.
- Non-matching recipients use Postfix's normal SMTP client and `smtp.office365.com:587` with a licensed relay mailbox and delegated OAuth.
- External messages preserve the original visible From and therefore require explicit Exchange Online SendAs permissions.
- Internal HVE messages use the HVE account as envelope and MIME From; the original sender is retained in custom headers.

The HVE helper provides token caching, a 20-minute refresh margin, retry for `5.7.142/5.7.143`, and temporary-failure exit codes so Postfix queues transient failures instead of bouncing them.

See the [English deployment guide](deployment-guide.md) or the [Turkish deployment guide](../tr/DEPLOYMENT_GUIDE.md) for implementation details.
