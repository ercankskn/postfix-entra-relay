# Contributing

1. Fork the repository and create a focused branch.
2. Do not include customer-specific values, logs, screenshots or credentials.
3. Run `./tests/run.sh` and `./scripts/linux/secret-scan.sh .` before opening a pull request.
4. Update documentation and `CHANGELOG.md` for behavior changes.
5. Keep changes compatible with the documented split-routing model.

Bug reports should include redacted Postfix configuration, software versions, exact SMTP status codes and sanitized log lines.
