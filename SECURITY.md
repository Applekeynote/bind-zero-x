# Security policy

The supported entry point is `Start.ps1` / `app/console_server.py`. Desktop access binds only to loopback. Wi-Fi access requires TLS, completed password + TOTP enrollment, and an expiring device session. Reverse proxy and Internet-facing deployment are outside this local deployment model. The original standalone research API requires its separate bearer token and must stay private.

Preserve exact-origin and CSRF validation, host checks, real peer-address checks, byte-counted input limits, bounded model signatures, TOTP replay prevention, authenticated static assets, fail-closed evidence verification, and session revocation. Demo images are never independent measurement evidence or physical-action authorization.

Operator accounts require password/TOTP. Judges explicitly use a separate generated password without TOTP and a one-hour session with 15-minute idle expiry. Both roles have principal-bound sessions. Judges may use the demo/packing workflow and their own synthetic sessions; they cannot list, open, export, advance or retrieve frames from another principal's sessions. Captured-frame analysis and global evidence audit remain operator-only. Judge login text is private and excluded from source/release packaging. Offline provisioning must never reset an active account. Legacy unused invitations are invalidated during conversion; no judge enrollment endpoint remains. Account revocation/expiry must invalidate existing sessions, and revoke-other-devices must stay principal-scoped. Unmapped sessions fail closed. Preserve the legacy operator credential row when migrating schema.

Photo-textured rendering must not fabricate unseen image evidence, calibrated dimensions, rope strength, physical confirmation or action authorization. Additional captures and measured dimensions remain unverified operator inputs. Keep external rendering dependencies pinned, verified and locally served.

Do not commit runtime data, captures, real GT, credentials, private keys, local environment files, or account-specific cloud evidence. Source publication and release packaging use `scripts/release-files.json`; newly added files require explicit review before adding to that allowlist. Never turn source packaging into a recursive workspace export. Test fixtures must use disposable secrets.

Report suspected vulnerabilities through GitHub's private vulnerability reporting when enabled, or privately contact the repository owner. Avoid putting credentials or live exploit data in public issues.
