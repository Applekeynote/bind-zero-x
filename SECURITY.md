# Security policy

The supported entry point is `Start.ps1` / `app/console_server.py`. Desktop access binds only to loopback. Wi-Fi access requires TLS, completed password + TOTP enrollment, and an expiring device session. Reverse proxy and Internet-facing deployment are outside this local deployment model. The original standalone research API requires its separate bearer token and must stay private.

Preserve exact-origin and CSRF validation, host checks, real peer-address checks, byte-counted input limits, bounded model signatures, TOTP replay prevention, authenticated static assets, fail-closed evidence verification, and session revocation. Demo images are never independent measurement evidence or physical-action authorization.

Do not commit runtime data, captures, real GT, credentials, private keys, local environment files, or account-specific cloud evidence. Source publication and release packaging use `scripts/release-files.json`; newly added files require explicit review before adding to that allowlist. Never turn source packaging into a recursive workspace export. Test fixtures must use disposable secrets.

Report suspected vulnerabilities through GitHub's private vulnerability reporting when enabled, or privately contact the repository owner. Avoid putting credentials or live exploit data in public issues.
