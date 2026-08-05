# Postfix Entra Relay

A production-oriented reference implementation for split-routing application and device email through Microsoft 365:

- Microsoft 365 internal recipients are delivered through **High Volume Email (HVE)** using OAuth client credentials.
- External recipients are delivered through `smtp.office365.com` using a licensed relay mailbox, delegated OAuth, and explicit SendAs permissions.
- Postfix chooses the transport per recipient, so one message can be split into internal and external deliveries.

The repository includes sanitized examples, PowerShell automation, a hardened HVE pipe helper, daily sender-origin reporting, validation tooling, and an optional responsive dashboard.

Start with the [English deployment guide](docs/en/deployment-guide.md), the [Turkish deployment guide](docs/tr/DEPLOYMENT_GUIDE.md), or the [security guide](SECURITY.md).

No real tenant identifiers, credentials, tokens, domains, addresses, certificates, or production logs are included.
