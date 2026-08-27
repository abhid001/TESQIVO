# Security Policy

## Supported versions

Until the 1.0 release, only the `main` branch receives security fixes.

## Reporting a vulnerability

**Do not open a public issue for security reports.**

Email the maintainers at `security@tesqivo.example` (replace with the real address
before public release) with:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- affected version / commit,
- any suggested remediation.

You will receive an acknowledgement within 3 business days. We aim to provide a
remediation plan within 10 business days and to coordinate disclosure with you.

## Disclosure process

1. Report received and acknowledged.
2. Maintainers confirm and assess severity (CVSS).
3. Fix developed on a private branch; regression test added.
4. Release published; advisory issued crediting the reporter (unless anonymity is
   requested).
5. Public disclosure no earlier than 7 days after the fixed release, or by mutual
   agreement.

## Scope notes for Phase 1

- Local authentication only; sessions are server-side, HttpOnly, `SameSite=Lax`
  with a CSRF double-submit token.
- Passwords hashed with Argon2id.
- No secrets, tokens, or stack traces are emitted in production responses or logs.
- Dependency and image scanning run in CI before release (increment 12).
