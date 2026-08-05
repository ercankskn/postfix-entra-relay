# Geçiş ve Rollback

## Faz 0 - Hazırlık

- Günlük hacim ve peak rate ölçülür.
- Accepted domain listesi çıkarılır.
- External SendAs envanteri tamamlanır.
- HVE billing ve OAuth hazırdır.
- External token refresh testi başarılıdır.
- Backup/rollback dizini oluşturulur.

## Faz 1 - HVE helper pilotu

Postfix'e map eklemeden helper doğrudan test edilir. Bir iç mailbox'a HVE hesabı görünür From ile mail ulaşmalıdır.

## Faz 2 - Tek recipient pilotu

`transport_hve` içine yalnız pilot recipient yazılır:

```text
pilot@example.com hvepipe:
```

İç gönderim ve archive etkisi gözlenir.

## Faz 3 - Domain pilotu

Bir düşük riskli accepted domain HVE map'e alınır. Dış yol değişmez.

## Faz 4 - Tüm authoritative domainler

Accepted-domain dosyası review edilerek map üretilir. `postmap -q` ile tüm iç/dış örnekleri test edilir.

## Faz 5 - Gözlem

En az 30-60 dakika `status=deferred`, `status=bounced`, `HVE_SEND_ERROR/TEMPFAIL`, `SendAsDenied`, Queue büyümesi ve token log sızıntısı izlenir.

## Hızlı HVE rollback

```bash

cp /etc/postfix/transport_hve /etc/postfix/transport_hve.rollback-copy
: > /etc/postfix/transport_hve
postmap /etc/postfix/transport_hve
postfix check
systemctl reload postfix

```

Böylece tüm recipientler varsayılan external SMTP route'a düşer. İç hacim normal SMTP AUTH limitlerine geri döneceği için Queue dikkatle izlenmelidir.

## Eski map'e dönüş

```bash

cp /var/backups/postfix-entra-relay/<STAMP>/transport_hve /etc/postfix/transport_hve
postmap /etc/postfix/transport_hve
systemctl reload postfix

```

## main.cf / master.cf rollback

```bash

cp /var/backups/postfix-entra-relay/<STAMP>/main.cf /etc/postfix/main.cf
cp /var/backups/postfix-entra-relay/<STAMP>/master.cf /etc/postfix/master.cf
postfix check
systemctl restart postfix

```

Queue itemlarını silmeyin. Gerekirse map değişikliğinden sonra kontrollü olarak `postqueue -f` çalıştırın.
