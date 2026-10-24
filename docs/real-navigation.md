# Photo-based 3D packing navigation

The packing player now uses actual source-photo pixels and the OpenCV region mask. Its flat surfaces retain the observed contour and up to eight detected holes instead of being replaced by generic rectangles. Three.js 0.186.1 is served locally; the npm tarball SHA512 and shipped-file SHA256 values are retained in `app/static/vendor/three/provenance.json`, with its MIT license. No CDN or paid model is used.

## Geometry and interaction

The source image is drawn at the segmentation resolution. Label-map pixels isolate each selected region; manually drawn regions use their selected polygon. The image long axis aligns that cutout before the operator's chosen orientation. The visible contour is extruded for thickness, with the actual photo mapped to its top face and a plain cardboard underside. A new individual flat photograph can replace each region's source. Open boxes require a post-flattening capture before their fold step can be completed; the original open-box photo is never presented as a newly observed flattened surface.

Optional long edge, short edge and thickness measurements set physical proportions in millimetres. Incomplete measurements cannot start a plan. A mixed measured/unmeasured collection uses image proportions consistently; it never combines millimetres and pixels into one scale. When every selected piece is measured, ordering starts with the largest measured footprint and the next layer's 0/90-degree orientation is chosen to improve rectangular support overlap. The operator can override order and direction. These are operator-entered dimensions and footprint heuristics, not independently calibrated measurements or a validated mechanical optimizer.

The player provides front, top, side and underside cameras, pointer/keyboard orbit, speed, pause/replay and a timeline scrubber. Twine is a continuous shaded tube with surface fibre detail. Its path is derived from the current stack footprint and total height, including the route below the lowest layer and outside opposite edges. The underside camera exposes the concealed route. Two differently marked strands distinguish the knot ends and their separate over/under depth lanes. The second crossing retains the first crossing and reverses its handedness. A high-springback plan adds a second turn to the first crossing.

The rendering is a photo-textured surface extrusion, not photogrammetric reconstruction of hidden surfaces. Contact forces, rope friction, paper bending, strength and lifting suitability are not simulated or certified. A single overlapping photo only supplies visible regions; use individual flat captures and measured dimensions for a more faithful guide. Existing `physical_action_authorized=false` boundaries remain unchanged. These limits are documented here rather than promoted into unearned claims in the product.

## Knot policy

The operator supplies the twine material and whether the compressed stack springs back. The image classifier does not infer these properties.

| Condition | Guide |
| --- | --- |
| Grippy paper/cotton, stays flat | Square binding knot: one crossing, then the opposite crossing |
| Grippy paper/cotton, springs back | Surgeon binding knot: two turns in the first crossing, then one opposite crossing |
| Smooth plastic/nylon | Change to grippy binding material before starting this guide |

This conservative selection is an implementation policy for cardboard binding, not empirical evidence of knot strength for a particular bundle. The square-knot reference describes its binding purpose and limitations, and explains the extra first turn used to hold while completing the second half. The two-handed ligature reference describes the double first throw and reverse second crossing. The implementation uses original geometry and copies no source animation or video. References: [Square knot](https://www.animatedknots.com/square-knot), [double-throw ligature](https://www.animatedknots.com/ligature-knot-two-hands-technique).

## Data and lifecycle

`packing-model.js` holds pure dimension, layout, route and knot-policy functions. `packing-real.js` owns the original WebGL renderer, source masking and disposal. `packing.js` owns review, capture, step confirmation and the UI. `BZX-PACKING-GUIDE-V3` exports the condition, selected knot, layout units, per-piece orientation, measured values, individual-capture hashes and textual instructions. It excludes embedded capture pixels. Demo confirmations remain distinct from actual operator confirmations.

Rendering is bounded to 24 pieces and a capped device-pixel ratio. GPU drawing stops when the guide is hidden; replaced geometries/materials/textures are disposed and source-image caching is bounded. Reduced motion shows completed positions without animated movement. Devices without WebGL receive the source photo and textual guide rather than the previous generic diagram.

## Judge account

`scripts/create_judge_account.py` creates a separate password-only `judge` identity while the server is stopped. The `/judge` page asks only for its generated password, as requested. A private copyable handout is saved at `runtime/security/judge-login.txt`, excluded from Git and release packaging. The account lasts 30 days by default, with one-hour sessions and a 15-minute idle timeout. Operator MFA and Wi-Fi HTTPS remain required for their existing purposes.

Judge sessions bind to a principal. Their synthetic sessions have an explicit owner; listing, opening, exporting and advancing another principal's session is denied. Judge access to captured-frame analysis and the global evidence audit is blocked server-side. Revoking other devices affects only the same principal. Account expiry and revocation invalidate existing sessions. Provisioning refuses to reset active accounts. Pending legacy invitation tokens are invalidated during conversion; their enrollment routes are removed. The existing operator credentials are preserved; a normal restart revokes device sessions.

## Verification

The updated suites cover password-only judge login, mandatory operator MFA, password failure limits, account expiration/revocation, cross-principal session access, owner-session isolation, measured-versus-relative scale, orientation support, under-stack rope routing, and knot-strand separation. Normal operator enrollment/login/replay/CSRF tests remain enabled. Browser checks and exact final counts are recorded in the handover and the local execution record; real physical bundle testing remains a separate task.

## Supported panels and continuous binding update (2026-10-24)

Completion masks are separate unverified hypotheses: rotated envelopes fill only pixels occupied by other visible regions, never empty background. Inferred pixels receive their own surface's median color and stripes. The observed label map is untouched. An inscribed panel estimates the footprint after flaps are folded inward; PREPARE requires checking it against the real sheet. Individual captures, completion off/full-outline mode and finished dimensions provide corrections.

The planner groups panels by containment, uses broad base/cap panels around smaller centered panels, alternates bulky fold edges, and splits incompatible footprints. Support below 98% or height/short-edge above 0.25 blocks the planning confirmation. These are geometric heuristics, not measured friction or load ratings. Final checks press/release the stack, test accessible sheets for motion, then lift 2 cm with both hands supporting the underside and set down. Twine is never presented as a carrying handle.

The renderer consumes one bindingPaths model for both wraps and the knot. Amber A and blue B meet at the twine midpoint under the stack and extend continuously into opposite knot crossings. Independent white loops/floating knot strands are removed. V4 exports bundle membership, support evidence and exact paths, with lifting_verified=false.
## Shared-photo size and crease-aligned completion (24 October 2026)

The default needs no manual measurements. Each piece displays its estimated folded-panel long/short edges in pixels from the same overview image. The planner compares these dimensions, and every bundle uses one shared display normalizer. Close-up photos replace textures without changing overview size ratios. Optional measured dimensions must cover every selected piece; partially entered measurements no longer disappear into a relative layout. Thickness defaults to an explicitly estimated value when omitted.

Cross-shaped nets no longer use a minimum-area bounding box to determine their fold direction. OpenCV straight-edge/crease votes determine an axis modulo 90 degrees. Visible silhouette reflections propose hidden edges only behind other regions, preserving background cutouts. Reflected texture comes from the same piece, while observed labels remain unchanged. Outline shoulders and nearby creases locate the folded panel. The per-piece **Inspect completed outline** view exposes the result before stacking.

These are image dimension ratios, not absolute millimetres or a calibrated perspective reconstruction. On the supplied Primary sheets, blue is about 233×205 px and green 126×124 px; the previous diagonal panel estimate incorrectly made them similar in size.

