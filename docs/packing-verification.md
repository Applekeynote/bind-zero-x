# Packing navigator verification

The English pixel console includes OpenCV 5 surface segmentation, fold-first shape review, and an animated packing guide. It runs in the existing MFA-protected PC/private Wi-Fi deployment. No cloud resource or paid model is required.

## Implemented flow

Photo → Segment & guide → select colored regions → confirm flat/open/exclude → fold open boxes → center the stack → align folds → lengthwise twine → crosswise twine → two opposite half-knots → final check → JSON plan.

OpenCV 5 computes HSV/Lab tan-cardboard masks, edge-separated watershed seeds, colored labels and bounded polygons. Crease-direction/compactness features produce reviewable **Fold this box · candidate** hypotheses. No filename-specific shape decisions, learned object model, trained confidence, physical scale or independent GT is used. Merged/split surfaces and missed white or printed cardboard can be corrected by selecting/excluding regions and drawing missing rectangles. The animation's initial order uses image area; the operator can reorder it to actual sheet sizes. Region colors persist into the stacking animation. This is a geometric assisted workflow, not validated autonomous instance segmentation or a proven unfolded-box classifier.

## Validation

- Genuine OpenCV 5.0.0 processed all five supplied demo photos, each returning bounded visible surface regions and colored outputs.
- Native tests cover separate tan sheets, negative background, reviewable crease cues, malformed/oversized PNG rejection before decode, source path allowlisting, authentication, CSRF, upload provenance, and concurrency limits.
- JavaScript tests cover fold-before-stack ordering, manual shape review, changing stack order, explicit step completion, missing-region drawing, and separation of demo versus real completion.
- Chrome on the production PC app exercised segmentation of Stacked boxes, candidate callout, selection of two open-box regions, two folding steps, stack reorder, animation play/pause, both twine paths, the reversed knot crossings, final demo check, and plan download. CSS animation names and paused state were read from the rendered DOM.
- At a 390px responsive viewport, the guide had no horizontal page overflow. The viewport override was reset afterward. Physical phone camera, certificate installation, and real-device operation were not exercised in this check.
- Downloaded demo plan contained nine simulated steps, **completed_in_demo=true**, **completed_by_user=false**, and **physical_action_authorized=false**. Demo photos are never promoted to real physical GT. Existing research authorization gates remain unchanged.

The uploaded photo and segmentation output are processed in memory. Operator JSON exports are explicit downloads. Source releases exclude runtime plans, private captures, credentials and TLS keys. The new endpoint inherits MFA/CSRF/Origin restrictions and uses the same bounded expensive-work gate.

Algorithm reference: [OpenCV 5 watershed tutorial](https://docs.opencv.org/5.0/tutorials/imgproc/imgtrans/distance_transformation/distance_transform.html).
