# BIND ZERO-X v4.3 — BIND-WITNESS

This ZIP contains a revised **research prototype** and historical v4.2 design. The new *normative* specification is `BIND_ZERO_X_v4.3_95点超を目指す実装・独創性・実証設計.md`.

### Run local tests

```
python -m pip install numpy opencv-python
PYTHONPATH=code python -m unittest discover -s code -p 'test_*.py' -v
```

The distributed evidence only proves **local synthetic/algorithm tests**. Local OpenCV in this build environment is **4.13.0**, not OpenCV5. Tests using `research_pipeline.analyze` explicitly override `require_opencv5=False` for synthetic regression. The default research CLI requires OpenCV5; container Dockerfile pins `opencv-python-headless==5.0.0.93` but its real AWS execution is **NOT RUN**.

### Core source

- `code/vision_motion_core.py`: expert-ROI optical flow, RANSAC, relative rigid transform; duplicate/overlap masks refused.
- `code/research_pipeline.py`: explicit calibration, data quality, rotation/footprint metrics, operator ROI manifest, fail-closed rule decision.
- `code/witness_planner.py`: **BIND-WITNESS** inspectable two-world contradiction and noncontact view choice (hypothetical deterministic model only).
- `code/decision_bridge.py`: separate **illustrative** view-signature model; signals CV-dependent choice without claiming real-world calibration.
- `code/cape_rule_core.py`: measured channel-specific decision, action allowlist and human approval.
- `code/measurement_contract.py`: unit and uncertainty integrity.
- `code/challenge_contract.py`: preapproved experiment profile, UTC, tolerance checks.

### Evidentiary limitations

`REAL_GT_NOT_RUN / AWS_OPENCV5_NOT_RUN / PHYSICAL_BENCHMARK_NOT_RUN / HUMAN_COMPARISON_NOT_RUN`.

This source cannot establish 95+ competition score, any certified load, patent novelty, industrial readiness, or better-than-human performance.

### Traceability

`v4.3_テストケース台帳_394件.csv`: 187 local PASS + 207 NOT_RUN.
`v4.3_要求仕様_88件.csv`: 88 requirements.
`v4.3_要求テスト多対多対応.csv`: links from specification to tests.

### Regenerate evidence and release

Run `PYTHONPATH=code python build_v43_release.py` after extraction into a writable directory containing the source files and previous ledger. The generated ZIP is written into `/mnt/data` in this environment; change `newzip` path in the script for other machines.
