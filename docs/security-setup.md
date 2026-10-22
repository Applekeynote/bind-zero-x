# Desktop and Wi-Fi access

Run `Start.ps1` and open `http://127.0.0.1:8765/` on the PC. Choose a password of 14–128 characters, select **Link authenticator**, scan the QR with a TOTP authenticator, then select **Activate MFA** with its six-digit code. Keep both devices' automatic date/time enabled. Setup is available only from the PC's loopback interface and closes permanently after successful enrollment.

A code can succeed once. Wait for the next 30-second code before signing in again. Sessions expire after 15 minutes of inactivity or eight hours total; a restart signs out all devices. **Sign out other devices** revokes all other sessions. Passwords use scrypt; Windows protects TOTP secrets and encrypted certificate passwords with the current account's DPAPI. Unix uses a local 0600 encryption key. Keep the runtime directory accessible only to the operator account.

Create a local certificate for the PC's current private Wi-Fi IPv4 address:

```powershell
.\.venv5\Scripts\python.exe scripts\setup_tls.py --ip YOUR_PRIVATE_IPV4
.\Start.ps1 -Mobile -MobileIP YOUR_PRIVATE_IPV4
```

The desktop listener stays on `127.0.0.1:8765`. Phones use `https://YOUR_PRIVATE_IPV4:8766/` and must sign in with the password and a fresh authenticator code. Mobile startup refuses to bind until both MFA and matching, valid TLS files exist. Forwarded headers are not trusted. No reusable access link or password appears in the phone URL.

Install the **public** `runtime/tls/ca-cert.cer` on the phone using its certificate settings and enable trust for that local CA. Compare its SHA256 fingerprint with `runtime/tls/certificate-info.json` using a direct transfer from this PC. Android certificate settings and iOS certificate/profile settings differ by OS version; iOS also requires enabling full trust under Certificate Trust Settings. Do not bypass browser certificate errors. Never transfer `*-key.pem`, `*-pass.protected`, or authentication databases. Allow inbound TCP 8766 only on the intended private network. No firewall rules or device trust stores are modified by the application.

The CA is limited to this private IP, loopback and localhost, expires in one year, and issues a 90-day server certificate. If the IP changes or a certificate expires, stop mobile mode, securely archive the old runtime TLS directory, create a new certificate set, and install the replacement public CA on your devices. Password/TOTP recovery is an operator-maintained local process; no remote reset endpoint exists.

The app provides one shared operator workspace. All authenticated devices can access its sessions and demo images. Physical measurements and independent GT remain separate from demo content.
