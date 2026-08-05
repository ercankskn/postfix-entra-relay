# Postfix Entra Relay — Uçtan Uca Kurulum Rehberi

Bu rehber sıfırdan üretim kurulumunu tek sırada verir. Ayrıntılı gerekçeler için ilgili bölüm linklerine gidin.

## Hedef mimari

```text
Uygulamalar ve cihazlar
        |
        v
Postfix (restricted relay)
        |
        +-- recipient accepted-domain ise --> HVE OAuth --> iç kullanıcı
        |
        +-- recipient dış domain ise ------> smtp.office365.com OAuth
                                               |
                                               +-- original From + SendAs
```

## A. Hazırlık checklist

- [ ] Ubuntu sunucu hazır, saat senkronize.
- [ ] Uygulama/cihaz kaynak CIDR listesi hazır.
- [ ] HVE address, external relay mailbox, archive ve alert adresleri belirlendi.
- [ ] HVE billing policy tenant'ta görünüyor.
- [ ] External relay mailbox lisanslı.
- [ ] Accepted domain listesi gözden geçirildi.
- [ ] SendAs sender CSV hazır.
- [ ] Değişiklik ve rollback penceresi onaylı.

## B. Microsoft 365 bağlantısı

Windows PowerShell 7 üzerinde:

```powershell

Install-Module ExchangeOnlineManagement -Scope CurrentUser
Install-Module Microsoft.Graph -Scope CurrentUser

.\scripts\powershell\00-connect.ps1 `
  -AdminUpn admin@example.onmicrosoft.com

```

## C. HVE hesabı ve billing

```powershell

Get-BillingPolicy -ResourceType HVE

.\scripts\powershell\01-create-hve-account.ps1 `
  -HveAddress hve-relay@example.com `
  -DisplayName "Postfix Entra HVE Relay" `
  -ReplyTo relay@example.com `
  -BillingPolicyId "<BILLING_POLICY_GUID>"

```

`BillingPolicyStatus` değeri `BillingPolicyValid` olmadan devam etmeyin.

## D. HVE OAuth app

```powershell

.\scripts\powershell\02-create-hve-oauth-app.ps1 `
  -HveAddress hve-relay@example.com `
  -DisplayName "Postfix Entra Relay - HVE OAuth"

```

Çıktıdaki `TenantId`, `ClientId`, `ServicePrincipalObjectId` ve `ClientSecret` değerlerini secret manager'a kaydedin. Client secret yalnız bir kez görünür.

## E. External OAuth app ve mailbox

```powershell

.\scripts\powershell\03-create-external-oauth-app.ps1 `
  -DisplayName "Postfix Entra Relay - External SMTP" `
  -RelayMailbox relay@example.com

```

Client ID ve tenant ID değerini not edin.

## F. Accepted domain ve SendAs

```powershell

.\scripts\powershell\04-export-accepted-domains.ps1 `
  -OutputPath .\accepted-domains.txt

.\scripts\powershell\05-grant-sendas-from-csv.ps1 `
  -CsvPath .\sendas.csv `
  -RelayMailbox relay@example.com

# Optional: export an existing trustee's explicit SendAs inventory.
.\scripts\powershell\05a-export-sendas-trustee.ps1 `
  -Trustee relay@example.com `
  -OutputPath .\sendas-export.csv

```

Dosyaları Linux sunucuya güvenli aktarın.

## G. Linux bootstrap

Repo sunucuda `/opt/postfix-entra-relay` altında olsun:

```bash

cd /opt/postfix-entra-relay
sudo ./scripts/linux/bootstrap-ubuntu.sh
sudo ./scripts/linux/install-hve-components.sh

```

## H. HVE config

```bash

sudoedit /etc/postfix-entra-relay/hve-oauth.json

```

Örnek:

```json
{
  "tenant_id": "<TENANT_ID>",
  "client_id": "<HVE_APP_CLIENT_ID>",
  "client_secret": "<HVE_APP_CLIENT_SECRET>",
  "auth_user": "hve-relay@example.com",
  "display_name": "Application Mail Service",
  "reply_to": "relay@example.com",
  "smtp_server": "smtp.hve.mx.microsoft",
  "smtp_port": 587,
  "scope": "https://outlook.office.com/.default",
  "token_refresh_margin_seconds": 1200,
  "bulk_to_threshold": 50,
  "bulk_alert_recipient": "alerts@example.com"
}
```

```bash

chown root:postfix-entra-hve /etc/postfix-entra-relay/hve-oauth.json
chmod 0640 /etc/postfix-entra-relay/hve-oauth.json

sudo -u postfix-entra-hve \
  /usr/local/sbin/postfix-entra-hve-submit \
  --recipient test@example.com \
  --test-config

```

## I. External sasl-xoauth2

```bash

sudo install -o root -g postfix -m 0640 \
  config/postfix/sasl-xoauth2.conf.example \
  /etc/sasl-xoauth2.conf

sudoedit /etc/sasl-xoauth2.conf

sudo install -d -o postfix -g postfix -m 0700 \
  /var/spool/postfix/etc/postfix-oauth

sudo sasl-xoauth2-tool get-token outlook \
  /var/spool/postfix/etc/postfix-oauth/relay@example.com \
  --client-id=<EXTERNAL_CLIENT_ID> \
  --tenant=<TENANT_ID> \
  --use-device-flow

sudo chown postfix:postfix \
  /var/spool/postfix/etc/postfix-oauth/relay@example.com
sudo chmod 0600 \
  /var/spool/postfix/etc/postfix-oauth/relay@example.com

```

`/etc/postfix/sasl_passwd`:

```text
[smtp.office365.com]:587 relay@example.com:/etc/postfix-oauth/relay@example.com
```

```bash

sudo postmap /etc/postfix/sasl_passwd
sudo chmod 0600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db

sudo sasl-xoauth2-tool test-config --config-file /etc/sasl-xoauth2.conf
sudo sasl-xoauth2-tool test-token-refresh \
  /var/spool/postfix/etc/postfix-oauth/relay@example.com \
  --config-file /etc/sasl-xoauth2.conf

```

## J. Accepted domain map

```bash

sudo install -o root -g root -m 0644 accepted-domains.txt \
  /etc/postfix-entra-relay/accepted-domains.txt

sudo ./scripts/linux/generate-transport-map.sh \
  /etc/postfix-entra-relay/accepted-domains.txt \
  /etc/postfix/transport_hve

```

## K. Relay environment ve Postfix

```bash

sudo install -o root -g root -m 0640 \
  config/relay.env.example \
  /etc/postfix-entra-relay/relay.env

sudoedit /etc/postfix-entra-relay/relay.env

sudo install -o root -g root -m 0644 \
  config/postfix/mynetworks.example \
  /etc/postfix/mynetworks.postfix-entra

sudoedit /etc/postfix/mynetworks.postfix-entra

sudo ./scripts/linux/configure-postfix.sh \
  /etc/postfix-entra-relay/relay.env

```

Config review:

```bash

postconf -n | grep -E \
  '^(relayhost|transport_maps|always_bcc|smtp_sasl|smtp_destination|hvepipe)'

grep -A2 -B1 '^hvepipe' /etc/postfix/master.cf

```

## L. HVE helper direct test

```bash

printf '%s\r\n' \
  'From: reportserver@example.com' \
  'To: user@example.com' \
  'Subject: helper test' \
  '' \
  'Test' \
| sudo -u postfix-entra-hve \
  /usr/local/sbin/postfix-entra-hve-submit \
    --recipient user@example.com \
    --queue-id MANUAL-001 \
    --original-sender reportserver@example.com

```

## M. Split test

```bash

MSGID="split-$(date +%s)@example.com"
cat <<'MAIL' | /usr/sbin/sendmail \
  -f reportserver@example.com \
  user@example.com \
  recipient@external.test
From: reportserver@example.com
To: user@example.com, recipient@external.test
Subject: Postfix Entra split test

Test
MAIL

sleep 10
mailq

```

Logda beklenen:

```text
internal recipient: relay=hvepipe status=sent
external recipient: relay=smtp.office365.com status=sent
queue: empty
```

İç mailbox'ta görünen sender HVE hesabıdır; dış mailbox'ta original sender görünür.

## N. Rapor ve timer

```bash

sudoedit /etc/postfix-entra-relay/report.json

sudo systemctl enable --now \
  postfix-entra-daily-origin-report.timer

sudo /usr/local/sbin/postfix-entra-daily-origin-report \
  --date "$(date -d yesterday +%F)" \
  --force

```

## O. Opsiyonel dashboard

Mail akışı doğrulandıktan sonra read-only dashboard kurulabilir:

```bash

sudo ./scripts/linux/install-dashboard.sh

sudoedit /etc/postfix-entra-relay/dashboard.env
sudo systemctl restart postfix-entra-metrics.service postfix-entra-dashboard.service

```

Gunicorn yalnız `127.0.0.1:8765` üzerinde dinler. Nginx TLS + authentication örneği `dashboard/nginx/` altındadır.

## P. Final doğrulama

```bash

sudo ./scripts/linux/validate-installation.sh
sudo ./scripts/linux/flow-check.sh 15
sudo ./scripts/linux/secret-scan.sh /opt/postfix-entra-relay

```

PowerShell:

```powershell

.\scripts\powershell\06-verify.ps1 `
  -HveAddress hve-relay@example.com `
  -RelayMailbox relay@example.com `
  -HveServicePrincipalObjectId "<SP_OBJECT_ID>"

```

## Q. Operasyon kabul kriterleri

- [ ] Queue boş veya normal seviyede.
- [ ] Son 15 dakikada HVE auth/token error yok.
- [ ] Dış SendAsDenied yok.
- [ ] `auth=Bearer`, `refresh=` veya `Client::SendToken` log sızıntısı yok.
- [ ] İç ve dış route doğru.
- [ ] Archive kopyası geliyor.
- [ ] Daily report timer aktif.
- [ ] Backup ve rollback yolu kayıtlı.

## R. Rollback

En hızlı HVE rollback, `transport_hve` mapini boşaltıp `postmap` ve reload yapmaktır. Tüm trafik dış SMTP AUTH yoluna döner; normal SMTP AUTH limitleri nedeniyle queue'yu izleyin. Ayrıntı: [14-gecis-rollback.md](14-gecis-rollback.md).
