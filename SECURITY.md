# Security Policy

## Public repository rule

Never commit live customer or tenant material. This includes:

- Entra tenant IDs, application IDs and service-principal object IDs
- client secrets, access tokens and refresh tokens
- `/etc/sasl-xoauth2.conf` with production values
- sasl-xoauth2 token files and Postfix lookup databases
- real mailbox or SendAs inventories
- public/private IP allowlists
- mail logs, NDR exports, message bodies or attachments
- TLS private keys, PFX files and password files

The repository intentionally contains only placeholders such as `<TENANT_ID>` and addresses under `example.com`.

## Required file permissions

Recommended production permissions:

```text
/etc/postfix-entra-relay/hve-oauth.json      root:postfix-entra-hve 0640
/var/lib/postfix-entra-relay/                postfix-entra-hve:postfix-entra-hve 0750
/etc/sasl-xoauth2.conf                       root:postfix 0640
Postfix OAuth token directory                postfix:postfix 0700
Dashboard environment file                   root:postfix-entra-dashboard 0640
```

## OAuth logging

Do not enable full sasl-xoauth2 tracing in steady state. Access and refresh tokens may be written to syslog. Recommended settings:

```json
{
  "always_log_to_syslog": "no",
  "log_full_trace_on_failure": "no",
  "log_to_syslog_on_failure": "yes"
}
```

If a token ever appears in a log, treat it as exposed: stop verbose logging, revoke/re-authorize the session, rotate the application secret where applicable, and protect/delete copied logs according to policy.

## Identity controls

- Keep Security Defaults or an equivalent Conditional Access baseline enabled.
- Use OAuth; do not keep Basic SMTP enabled merely to support this project.
- Use separate identities and apps for external SMTP and HVE.
- Scope external SendAs explicitly. Exchange Online does not provide a safe wildcard SendAs model for this use case.
- Use short-lived client secrets or certificates and rotate them before expiry.

## Network controls

- Restrict inbound relay access with `mynetworks`, host firewall rules, authenticated submission, or a dedicated VLAN/VPN.
- Never expose an unauthenticated open relay to the Internet.
- Bind the dashboard to localhost and publish it through a TLS reverse proxy with authentication.

## Reporting a vulnerability

Use a private security advisory on the Git hosting platform. Do not post tokens, customer addresses or full mail logs in a public issue.
