# Postfix Entra Relay — Deployment Guide

This guide deploys a restricted Postfix relay that routes Microsoft 365 accepted-domain recipients through High Volume Email (HVE) and all other recipients through Exchange Online SMTP AUTH with OAuth.

## 1. Prerequisites

- Ubuntu Server 24.04 LTS or a compatible Debian derivative
- Postfix 3.8 or later
- Python 3.11 or later
- Outbound TCP 443 and 587
- Exact application and device source networks
- A licensed Exchange Online relay mailbox
- An HVE account with `BillingPolicyValid`
- ExchangeOnlineManagement and Microsoft Graph PowerShell modules

## 2. Microsoft 365 preparation

Connect with PowerShell:

```powershell
.\scripts\powershell\00-connect.ps1 `
  -AdminUpn admin@example.onmicrosoft.com
```

Create or configure the HVE account:

```powershell
.\scripts\powershell\01-create-hve-account.ps1 `
  -HveAddress hve-relay@example.com `
  -DisplayName "Postfix Entra HVE Relay" `
  -ReplyTo relay@example.com `
  -BillingPolicyId "<BILLING_POLICY_GUID>"
```

Create the HVE OAuth application and store the returned secret outside Git:

```powershell
.\scripts\powershell\02-create-hve-oauth-app.ps1 `
  -HveAddress hve-relay@example.com
```

Create the delegated OAuth application used by the external SMTP route:

```powershell
.\scripts\powershell\03-create-external-oauth-app.ps1 `
  -RelayMailbox relay@example.com
```

Export accepted domains and grant explicit SendAs permissions:

```powershell
.\scripts\powershell\04-export-accepted-domains.ps1 `
  -OutputPath .\accepted-domains.txt

.\scripts\powershell\05-grant-sendas-from-csv.ps1 `
  -CsvPath .\sendas.csv `
  -RelayMailbox relay@example.com
```

## 3. Linux installation

Copy the repository to `/opt/postfix-entra-relay`, then run:

```bash
cd /opt/postfix-entra-relay
sudo ./scripts/linux/bootstrap-ubuntu.sh
sudo ./scripts/linux/install-hve-components.sh
```

Install and secure the HVE configuration:

```bash
sudo install -o root -g postfix-entra-hve -m 0640 \
  config/hve/hve-oauth.json.example \
  /etc/postfix-entra-relay/hve-oauth.json

sudoedit /etc/postfix-entra-relay/hve-oauth.json
```

Validate it without sending a message:

```bash
sudo -u postfix-entra-hve \
  /usr/local/sbin/postfix-entra-hve-submit \
  --recipient user@example.com \
  --test-config
```

## 4. External OAuth route

Install and configure the `sasl-xoauth2` plugin for Postfix. Keep the delegated refresh token in the Postfix chroot with owner `postfix`, mode `0600`.

Example `/etc/postfix/sasl_passwd`:

```text
[smtp.office365.com]:587 relay@example.com:/etc/postfix-oauth/relay@example.com
```

Build the map and protect both files:

```bash
sudo postmap /etc/postfix/sasl_passwd
sudo chmod 0600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
```

## 5. Recipient routing

Install the accepted-domain list and generate the HVE transport map:

```bash
sudo install -o root -g root -m 0644 accepted-domains.txt \
  /etc/postfix-entra-relay/accepted-domains.txt

sudo ./scripts/linux/generate-transport-map.sh \
  /etc/postfix-entra-relay/accepted-domains.txt \
  /etc/postfix/transport_hve
```

Copy and edit the non-secret relay environment, then configure Postfix:

```bash
sudo install -o root -g root -m 0640 \
  config/relay.env.example \
  /etc/postfix-entra-relay/relay.env

sudoedit /etc/postfix-entra-relay/relay.env
sudo ./scripts/linux/configure-postfix.sh \
  /etc/postfix-entra-relay/relay.env
```

## 6. Validation

Review the active routing configuration:

```bash
postconf -n | grep -E \
  '^(relayhost|transport_maps|always_bcc|smtp_sasl|smtp_destination|hvepipe)'

grep -A3 -B1 '^hvepipe' /etc/postfix/master.cf
```

Run repository and installation checks:

```bash
make test
make secret-scan
sudo ./scripts/linux/validate-installation.sh
sudo ./scripts/linux/flow-check.sh 15
```

Expected behavior:

- Accepted-domain recipients use `hvepipe`.
- External recipients use `smtp.office365.com:587`.
- Mixed-recipient messages are split by Postfix transport maps.
- HVE copies show the HVE identity and preserve the original sender in `X-Postfix-Entra-*` headers.
- External copies preserve the original visible sender and require explicit SendAs.
- The Postfix queue remains empty or at its normal operating level.

## 7. Optional dashboard

After mail flow is stable:

```bash
sudo ./scripts/linux/install-dashboard.sh
```

The application listens only on `127.0.0.1:8765`. Publish it through an authenticated TLS reverse proxy using the example under `dashboard/nginx/`.

## 8. Rollback

To return accepted-domain traffic to the default external relay, empty `/etc/postfix/transport_hve`, rebuild the map, and reload Postfix:

```bash
sudo truncate -s 0 /etc/postfix/transport_hve
sudo postmap /etc/postfix/transport_hve
sudo postfix reload
```

Monitor the queue carefully because Exchange Online SMTP AUTH limits apply after rollback.
