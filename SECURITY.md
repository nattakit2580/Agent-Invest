# Security Policy

## Reporting a vulnerability

Do not open a public issue containing credentials, tokens, customer data, or an
unpatched exploit. Contact the repository owner privately and include the
affected version, reproduction steps, impact, and a suggested mitigation when
available.

## Operational requirements

- Set strong, unique values for `ADMIN_PASSWORD`,
  `TELEGRAM_WEBHOOK_SECRET_TOKEN`, and `TELEGRAM_ADMIN_TOKEN` when those
  features are enabled.
- Keep `CORS_ALLOW_ORIGINS` restricted to exact trusted frontend origins.
- Never commit `.env` files. Docker build contexts explicitly exclude them.
- Review Dependabot pull requests and keep CI passing before deployment.
- Treat generated investment analysis as informational, not financial advice.

## Public repository audit

The latest redacted audit of public Git history, metadata exposure, scanner
false positives, and remaining actions is in `docs/PUBLIC_SECURITY_AUDIT.md`.
Do not publish raw scanner reports or complete detected values.

## Supported version

Security fixes are applied to the latest commit on the default branch.
