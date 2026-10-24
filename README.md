# BIND ZERO-X · Observation Quest

A retro pixel-style field workspace for cardboard photos and observations. The interface is in English and adapts to phone, tablet, and desktop screens.

## Quick flow

**MFA sign-in → New observation → Analyze → Record the next view → Review history/evidence → Export JSON**

1. Sign in with your password and the current authenticator code. An expired sign-in challenge is refreshed automatically.
2. Select **New observation**. Choose **Launch the demo** for synthetic inputs, or **Analyze paired frames** for two PNG frames, upper/lower ROI masks, and a calibration/model configuration.
3. OpenCV 5 measures relative layer motion. The research model updates possible worlds and selects the next observation.
4. Record that observation, or analyze a follow-up capture. The session and evidence trace are saved.
5. Reopen **History**, verify **Evidence**, and export the decision witness/trace as JSON.

The photo board displays the nine demo photos; browsing a photo does not run motion analysis.

## Color, fold, stack and tie

Select a demo photo or add your own photo, then choose **Segment & guide**. OpenCV 5 uses HSV chroma, border-relative Lab color, adaptive hue peaks, edge markers and watershed to color visible cardboard surface regions. Select the pieces you want to bundle and choose **Flat sheet**, **Open / assembled box**, or **Not cardboard / duplicate face**. Use **Draw a missing region** for a missed or white cardboard surface.

Geometric crease evidence produces **Fold this box · candidate** callouts. It is a reviewable heuristic, not a trained box classifier or a calibrated probability; surfaces may merge or split and a single photo cannot establish depth, hidden pieces, or physical dimensions. Confirm the shapes before building the guide. The guide uses actual photo cutouts and visible contours in an interactive 3D view. Enter measured long/short edges and thickness for millimetre proportions, or work consistently with photo proportions. Each layer has its own placement step. Front, top, side and underside cameras show how the twine passes around the stack; the timeline can be paused and inspected. Grippy twine with a flat stack uses a square binding knot; a springy stack uses a double first throw and an opposite single throw. Smooth plastic line prompts a change of material. Open boxes need a new flattened capture before continuing, and individual flat photographs can replace obscured regions. Navigation keeps the original pixel font. See [the implementation and limits](docs/real-navigation.md).

## Judge access

The operator signs in as `operator`. A separate `judge` identity is created by the offline account command in [the security setup guide](docs/security-setup.md). At `/judge`, judges enter only their generated password. Their private copyable login text stays in `runtime/security/judge-login.txt`, outside Git and release packages. Judge sessions can access the demo and their own synthetic observations, with server-enforced isolation from operator captures, sessions and audit records. Operator MFA remains required. Judge accounts last 30 days by default; sessions last one hour with a 15-minute idle timeout.

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

- The nine supplied cardboard photos are demo-only and included as original PNGs. Switch photos with the thumbnail strip and expand a frame for a closer look.
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
| `app/static/photos/manifest.json` | SHA256 hashes and provenance of the nine replacement demo photos |
| `bind-zero-x/` | v4.9 design archive and maintained research code |
| `runtime/` | Local sessions, PNG archive, integrity keys, execution evidence |
| `data/physical/` | Physical data collection and independent measurements |
| `SECURITY.md` | Security boundaries and publication policy |
| `docs/security-setup.md` | MFA enrollment and private Wi-Fi HTTPS setup |
| `docs/physical-data.md` | Physical data collection procedure |

Runtime files, integrity keys, environments, and physical datasets are excluded from the source release. The source release includes the nine demo photos supplied for this interface. The release manifest contains current source hashes; manifests in the original design archive describe historical versions.

## Verification

```powershell
.\.venv5\Scripts\python.exe scripts\verify.py
```

Run the command above for the current core, console, and authentication regression results. Browser checks cover English navigation, photo switching/import, narrow layouts, observation save, history restore, and evidence inspection.

The supplied still photos are demo material. Paired capture analysis still uses the original calibration, ROI, evidence, and approval contracts. Earlier AWS evidence uses synthetic inputs in Tokyo CloudShell. Account-specific AWS evidence remains local and is excluded from the public source repository.

## Handover

See [HANDOVER.txt](HANDOVER.txt) for the detailed Japanese operational and development handover, including data flow, MFA/TLS, demo catalog, orientation conventions, tests, publication and remaining validation.

## Public judge deployment

Localhost works only on the hosting PC. The isolated AWS public-HTTPS deployment workflow is documented in [aws-public-demo.md](docs/aws-public-demo.md). Preparation does not mean the public URL is operational.

The latest packing guide completes occluded outlines as striped, reviewable hypotheses; folds flaps to compact panels; groups compatible footprints between a broad base/cap; and renders wraps and knot from one continuous twine model. V4 exports preserve those decisions. Physical friction and lifting strength are not inferred from a photo.
