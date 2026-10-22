# BIND ZERO-X · Observation Quest

A retro pixel-style field workspace for cardboard photos and observations. The interface is in English and adapts to phone, tablet, and desktop screens.

## Quick flow

**MFA sign-in → New observation → Analyze → Record the next view → Review history/evidence → Export JSON**

1. Sign in with your password and the current authenticator code. An expired sign-in challenge is refreshed automatically.
2. Select **New observation**. Choose **Launch the demo** for synthetic inputs, or **Analyze paired frames** for two PNG frames, upper/lower ROI masks, and a calibration/model configuration.
3. OpenCV 5 measures relative layer motion. The research model updates possible worlds and selects the next observation.
4. Record that observation, or analyze a follow-up capture. The session and evidence trace are saved.
5. Reopen **History**, verify **Evidence**, and export the decision witness/trace as JSON.

The photo board displays the five demo photos; browsing a photo does not run motion analysis.

## Color, fold, stack and tie

Select a demo photo or add your own photo, then choose **Segment & guide**. OpenCV 5 uses HSV/Lab color evidence, edge markers and watershed to color visible cardboard surface regions. Select the pieces you want to bundle and choose **Flat sheet**, **Open / assembled box**, or **Not cardboard / duplicate face**. Use **Draw a missing region** for a missed or white cardboard surface.

Geometric crease evidence produces **Fold this box · candidate** callouts. It is a reviewable heuristic, not a trained box classifier or a calibrated probability; surfaces may merge or split and a single photo cannot establish depth, hidden pieces, or physical dimensions. Confirm the shapes before building the guide. The animated guide folds open boxes first, stacks and aligns sheets, routes paper twine in two directions, and demonstrates the two opposite crossings of a square knot. Adjust the suggested image-area order to actual sheet sizes with the order arrows. Each physical step requires your completion check. Play/pause, replay, back, mobile layouts, reduced motion, and JSON plan export are supported. The guide does not change the research physical-action authorization gate.

## Start

```powershell
.\Start.ps1
```

Open <http://127.0.0.1:8765/> and complete **Set up MFA**: choose a 14–128 character password, select **Link authenticator**, scan the QR, enter its six-digit code, then select **Activate MFA**. On another PC, install Python 3.12+ and run `.\Setup.ps1 -Python python` once first. The launcher prefers `.venv5`, with genuine OpenCV 5.0.0.

## Use on a phone

```powershell
.\Start.ps1 -Mobile
```

Complete desktop MFA first. Create a local HTTPS certificate with `.\.venv5\Scripts\python.exe scripts\setup_tls.py --ip YOUR_PRIVATE_IPV4`, then start mobile mode. Install the public `runtime/tls/ca-cert.cer` on your phone and trust that local CA. Open the HTTPS link shown by **Connect phone** on the same private Wi-Fi, then sign in with your password and a fresh authenticator code. See [the setup guide](docs/security-setup.md) for trust, expiry, and network setup.

The phone HTTPS port is 8766; desktop loopback stays at 8765. Mobile startup requires MFA and valid TLS. Sessions expire after 15 minutes idle or eight hours total, and a restart revokes them. Each authenticator code can succeed once; wait for the next code before another sign-in. No credential is included in a join URL.

## Explore the collection

- The five supplied cardboard photos are demo-only and included as original PNGs. Switch photos with the thumbnail strip and expand a frame for a closer look.
- **Add photo** opens the photo library or the phone camera. Selected images are previewed on that device. A photo preview stays in browser memory until the page is reloaded.
- **New observation → Analyze paired frames** accepts two PNG frames, upper/lower ROI masks, and a calibration/model JSON. Use **Configuration template** to prepare the configuration.
- **Launch the demo** runs synthetic optical flow, creates a persisted session, and lets you record the next observation.
- **History** reopens saved sessions. **Evidence** checks original PNGs, session MACs, and receipt integrity. The decision witness and trace can be exported as JSON.
- Photo details and observation measurements have separate views. Selecting a demo photo does not create motion measurements or ground-truth results.

## Files

| Path | Content |
| --- | --- |
| `app/console_server.py` | FastAPI console adapter and optional phone access |
| `app/static/` | English HTML/CSS/JS, pixel guides, custom font, photo collection |
| `app/static/photos/manifest.json` | SHA256 hashes and provenance of the five original photos |
| `bind-zero-x/` | v4.9 design archive and maintained research code |
| `runtime/` | Local sessions, PNG archive, integrity keys, execution evidence |
| `data/physical/` | Physical data collection and independent measurements |
| `SECURITY.md` | Security boundaries and publication policy |
| `docs/security-setup.md` | MFA enrollment and private Wi-Fi HTTPS setup |
| `docs/physical-data.md` | Physical data collection procedure |

Runtime files, integrity keys, environments, and physical datasets are excluded from the source release. The source release includes the five photos supplied for this interface. The release manifest contains current source hashes; manifests in the original design archive describe historical versions.

## Verification

```powershell
.\.venv5\Scripts\python.exe scripts\verify.py
```

Run the command above for the current core, console, and authentication regression results. Browser checks cover English navigation, photo switching/import, narrow layouts, observation save, history restore, and evidence inspection.

The supplied still photos are demo material. Paired capture analysis still uses the original calibration, ROI, evidence, and approval contracts. Earlier AWS evidence uses synthetic inputs in Tokyo CloudShell. Account-specific AWS evidence remains local and is excluded from the public source repository.
