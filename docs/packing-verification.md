# Packing navigator verification

The English pixel console includes OpenCV 5 surface segmentation, fold-first shape review, and an animated packing guide. It runs in the existing MFA-protected PC/private Wi-Fi deployment. No cloud resource or paid model is required.

## Implemented flow

Photo → Segment & guide → select colored regions → confirm flat/open/exclude → fold open boxes → plan order and direction → place each numbered layer → align folds → lengthwise twine → crosswise twine → two opposite half-knots → final check → JSON plan.

OpenCV 5 computes HSV chroma masks with border-relative Lab background rejection and adaptive circular hue peaks, edge-separated watershed seeds, colored labels and bounded polygons. Crease-direction/compactness features produce reviewable **Fold this box · candidate** hypotheses. No filename-specific shape decisions, learned object model, trained confidence, physical scale or independent GT is used. Merged/split surfaces and missed white or printed cardboard can be corrected by selecting/excluding regions and drawing missing rectangles. The animation's initial order uses image area; the operator can reorder it to actual sheet sizes. Region colors persist into the stacking animation. This is a geometric assisted workflow, not validated autonomous instance segmentation or a proven unfolded-box classifier.

## Validation

- Genuine OpenCV 5.0.0 processed all nine replacement demo photos, each returning bounded visible surface regions and colored outputs.
- Native tests cover separate tan sheets, negative background, reviewable crease cues, malformed/oversized PNG rejection before decode, source path allowlisting, authentication, CSRF, upload provenance, and concurrency limits.
- JavaScript tests cover fold-before-stack ordering, manual shape review, changing stack order, explicit step completion, missing-region drawing, and separation of demo versus real completion.
- Chrome on the production PC app exercised segmentation of Stacked boxes, candidate callout, selection of two open-box regions, two folding steps, stack reorder, animation play/pause, both twine paths, the reversed knot crossings, final demo check, and plan download. CSS animation names and paused state were read from the rendered DOM.
- At a 390px responsive viewport, the guide had no horizontal page overflow. The viewport override was reset afterward. Physical phone camera, certificate installation, and real-device operation were not exercised in this check.
- Downloaded demo plan contained nine simulated steps, **completed_in_demo=true**, **completed_by_user=false**, and **physical_action_authorized=false**. Demo photos are never promoted to real physical GT. Existing research authorization gates remain unchanged.

The uploaded photo and segmentation output are processed in memory. Operator JSON exports are explicit downloads. Source releases exclude runtime plans, private captures, credentials and TLS keys. The new endpoint inherits MFA/CSRF/Origin restrictions and uses the same bounded expensive-work gate.

Algorithm reference: [OpenCV 5 watershed tutorial](https://docs.opencv.org/5.0/tutorials/imgproc/imgtrans/distance_transformation/distance_transform.html).


## Replacement demo update, 2026-10-22

The five previous demo PNGs were removed from the current asset folder, catalog, API allowlist and release allowlist. The nine new supplied PNGs were copied byte-for-byte; manifest.json records each SHA256 and demo provenance. All nine ran through genuine OpenCV 5. The jewel, pastel and primary-color images each produced five visible color regions. Brown and assembled-box images produced 4–12 surface regions; these counts are not object counts. Shape evidence remains uncalibrated and manually reviewed.

The STACK planning step now controls the actual per-piece order, long-edge direction (left-to-right/front-to-back) and bulky-fold side. Every PLACE step retains its region ID and color, shows its layer number and top-view direction, and describes the approximate clockwise turn from the detected image long axis. Reordering regenerates subsequent placement instructions and clears their confirmations. Twine guidance distinguishes under-stack dotted paths from visible paths and gives front/back and left/right routing. Square-knot steps use opposite crossings.

The original 5x7 font now covers lowercase input with pixel-capital glyphs and navigation punctuation. Navigation copy, controls, layer settings and SVG text use it. BZX-PACKING-GUIDE-V2 exports each instruction, piece ID, orientation and bulky-fold side. Demo checks remain simulated completion.

Automated validation after this update: core 397 passed plus one skipped, application 32 passed, JavaScript 14 passed. The earlier Chrome checks above describe the previous five-photo build.

The replacement build was also checked in the MFA-authenticated production Chrome app. Primary sheets returned five color regions. All five were reviewed as flat; region 02 was moved to the base and its long edge set front-to-back. The next placement instruction correctly named layer 1 / region 02 and the approximate 55-degree clockwise turn. All five placements, alignment, both twine routes, both opposite knot crossings and the final demo confirmation were exercised. The downloaded V2 JSON contained 12 completed simulated steps, order [2,1,3,4,5], orientation 90 for its base piece, no real physical completion, and physical_action_authorized=false. Open boxes trio was separately reviewed as OPEN and correctly started with Fold region 01 flat. Pause/play/replay worked. At the 390px viewport override, document client and scroll widths were both 375px (the browser reserves a scrollbar); no horizontal page overflow occurred. The pixel font was loaded and used for the instruction copy. The viewport override was reset. Screenshots and the downloaded plan remain private under runtime/demo-results/. Real phone operation and physical measurements remain unverified.

## Photo-textured 3D and judge update, 2026-10-22

The current packing player replaces the previous SVG packing diagrams with source-photo cutouts, surface contours and holes, extruded thickness, 3D camera controls, continuous shaded twine and separate knot strands. The earlier SVG screenshots above are historical evidence. See `real-navigation.md` for the measured/relative scale boundary and the limits of the geometry.

Production Chrome signed in at `/judge` using only the generated judge password. The judge navigation excluded the global evidence view. Primary sheets again returned five regions, all explicitly reviewed as flat. With paper twine and high springback, the guide selected the surgeon binding knot and two first-crossing turns. All 12 demo steps were confirmed, including per-layer placement, the front-to-back and left-to-right routes, and opposite final crossing. The underside camera visibly exposed twine beneath the full stack. Timeline scrubbing paused at the selected position. Console error/warning checks returned no renderer errors.

At the 390px responsive override, document client/scroll widths were both 375px, and the knot, camera controls and timeline remained visible without horizontal overflow. Instruction copy used the loaded Pixel font. The viewport override was reset. The downloaded `BZX-PACKING-GUIDE-V3` JSON contained 12 `completed_in_demo=true` / `completed_by_user=false` steps, `SURGEON`, `firstTurns=2`, the selected condition, relative layout units and `physical_action_authorized=false`. The browser download event notification timed out, but the actual completed file in Downloads was independently parsed and verified, then copied into the private demo-results directory.

Regression totals: research 397 passed plus one skipped, application 38 passed, JavaScript 21 passed (456 passed plus one skipped overall). They include operator MFA remaining mandatory, password-only judge login, one-hour/idle expiry, password failure limits, account revocation, principal-scoped sign-out, cross-account history denial, measured layout, below-stack paths and separated knot-strand depth lanes. Physical phone operation, real bundle strength and independent GT are not established by these demo checks.

Open boxes trio was separately reviewed with one OPEN region. Its fold-step completion checkbox and Next control remained disabled until an individual flattened photo was added. The upload path was exercised using the supplied flat-brown-three demo asset (a UI fixture, not a photograph proving that this particular box was physically folded). The player displayed the replacement photo and enabled review/confirmation. Browser file-chooser automation was slow but completed successfully.
