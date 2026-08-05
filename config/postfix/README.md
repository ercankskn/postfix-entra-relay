# Postfix configuration samples

These files are **merge samples**, not a complete mail-server policy. Keep the distribution defaults that are still required by your environment.

Order matters:

```text
transport_maps = hash:/etc/postfix/transport_hve, hash:/etc/postfix/transport
```

The HVE map must be queried first. A matching recipient domain is sent to `hvepipe:`; a non-match falls back to the normal `relayhost` (`smtp.office365.com`).

After editing map files:

```bash
postmap /etc/postfix/transport_hve
postmap /etc/postfix/transport
postmap /etc/postfix/sasl_passwd
postfix check
systemctl reload postfix
```
