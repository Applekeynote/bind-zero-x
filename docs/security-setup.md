# Desktop and Wi-Fi access

Run `Start.ps1` and open `http://127.0.0.1:8765/` on the PC. Choose a password of 14–128 characters, select **Link authenticator**, scan the QR with a TOTP authenticator, then select **Activate MFA** with its six-digit code. Keep both devices' automatic date/time enabled. Setup is available only from the PC's loopback interface and closes permanently after successful enrollment.

A code can succeed once. Wait for the next 30-second code before signing in again. Sessions expire after 15 minutes of inactivity or eight hours total; a restart signs out all devices. **Sign out other devices** revokes all other sessions. Passwords use scrypt; Windows protects TOTP secrets and encrypted certificate passwords with the current account's DPAPI. Unix uses a local 0600 encryption key. Keep the runtime directory accessible only to the operator account.

Create a local certificate for the PC's current private Wi-Fi IPv4 address:

```powershell
.\.venv5\Scripts\python.exe scripts\setup_tls.py --ip YOUR_PRIVATE_IPV4
.\Start.ps1 -Mobile -MobileIP YOUR_PRIVATE_IPV4
```

The desktop listener stays on `127.0.0.1:8765`. Operator phones use `https://YOUR_PRIVATE_IPV4:8766/` with a password and fresh authenticator code. Judges use `/judge` with their separate password. Mobile startup refuses to bind until both MFA and matching, valid TLS files exist. Forwarded headers are not trusted. No reusable access link or password appears in the phone URL.

Install the **public** `runtime/tls/ca-cert.cer` on the phone using its certificate settings and enable trust for that local CA. Compare its SHA256 fingerprint with `runtime/tls/certificate-info.json` using a direct transfer from this PC. Android certificate settings and iOS certificate/profile settings differ by OS version; iOS also requires enabling full trust under Certificate Trust Settings. Do not bypass browser certificate errors. Never transfer `*-key.pem`, `*-pass.protected`, or authentication databases. Allow inbound TCP 8766 only on the intended private network. No firewall rules or device trust stores are modified by the application.

The CA is limited to this private IP, loopback and localhost, expires in one year, and issues a 90-day server certificate. If the IP changes or a certificate expires, stop mobile mode, securely archive the old runtime TLS directory, create a new certificate set, and install the replacement public CA on your devices. Password/TOTP recovery is an operator-maintained local process; no remote reset endpoint exists.

Operator devices share the operator workspace. Judges now have their own principal-bound demo sessions. Physical measurements and independent GT remain separate from demo content.

## Password-only judge access

With the server stopped, run `.\.venv5\Scripts\python.exe scripts\create_judge_account.py --username judge --days 30 --base-url https://YOUR_PRIVATE_IPV4:8766`. The private `runtime/security/judge-login.txt` contains a copyable login URL, username and generated 32-character password. Give it directly to the judge; keep it outside public source and release packages. The `/judge` page asks only for this password. No QR enrollment or authenticator code is required for judges, as explicitly requested by the operator. Operator login at `/` retains its password and fresh TOTP code.

The account expires after 30 days by default (configurable 1–90 days). Judge sessions last at most one hour and expire after 15 minutes without activity. Use a separate browser profile when the operator is already signed in. Wi-Fi access still requires valid HTTPS and a trusted local CA; this exception changes the judge's login factors only.

The command converts a pending unused invitation into a password account, invalidates the invitation and removes its old generated handout. It refuses to reset an active or revoked account or overwrite an existing login text. To revoke a judge and all their sessions, stop the server and run the command with `--revoke`. These offline commands intentionally revoke current sessions when loading the authentication store, so restart afterward.

Judges can inspect demo images, segment photos, use the packing player and create their own synthetic observations. Private operator sessions, captured-frame workflows and the global evidence audit are denied by the server. Passwords use scrypt; account records stay local. The handout contains the password only because a copyable text handout was explicitly requested.
