# Whole outlines and unpainted cardboard

The default guide retains the complete sheet polygon, slots and flaps. The renderer applies one uniform image scale and never replaces a flat net with its central rectangle. All selected pieces appear in a persistent photo inventory. Finishing a bundle advances to the next unfinished bundle; exports include every selected piece rather than only the active bundle.

Painted sheets retain hue/edge separation. For touching unpainted surfaces with internal structure, inference uses OpenCV 5 DNN with the OpenCV Zoo EfficientSAM-Ti model. Image features are computed once, then point/box proposals, a containment hierarchy, neighbour-negative refinement and foreground-constrained watershed assign visible instance IDs. Candidate parts no longer each become a sheet merely because a crease exists. Inference uses no PyTorch or external image service.

Install the conversion dependencies with `pip install -r requirements-segmentation.txt`, then run `python scripts/install_segmentation_model.py`. Setup.ps1 does both. Weights remain in runtime/models, outside Git/source ZIPs. The installer verifies the official full-model SHA-256 before splitting the encoder/decoder. Production uses `/opt/bzx/models`, read-only to the application. Missing/corrupt models fail explicitly instead of silently falling back to the known faulty unpainted heuristic.

The model is the Apache-2.0 OpenCV Zoo 2025-April export, SHA-256 `4eb496e0a7259d435b49b66faf1754aa45a5c382a34558ddda9a8c6fe5915d77`. See the [official model and license](https://github.com/opencv/opencv_zoo/tree/main/models/image_segmentation_efficientsam). ONNX is needed for installation/conversion; runtime inference is OpenCV 5.

The UI submits bounded background jobs and polls their state, avoiding the public gateway request deadline. Results are visible only to the requesting account, expire after ten minutes, and are held only in memory. At most two expensive tasks and eight retained jobs exist. Worker errors expose only allowlisted codes.

Regression checks use the supplied demo pixels. The three-sheet and five-sheet unpainted images must return three and five identities, keep distinct visible bodies separate, and attach checked front-sheet flap points to the same body. These are local developer annotations, not independent physical ground truth. Dense pile/spread results remain reviewable hypotheses; occluded instance count and hidden shape are not proven by a single image. No per-filename region count or hand-drawn demo mask enters production inference.
