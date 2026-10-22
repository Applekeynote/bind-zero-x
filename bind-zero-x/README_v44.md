# BIND ZERO-X v4.4 — Evidence-Bound Intervention

**Normative design:** `BIND_ZERO_X_v4.4_正式改訂仕様_証明付き能動知覚.md`  
**Source status:** research prototype; not production, not a safety certification, not a verified OpenCV5/AWS submission.

### Quick start (local regression; OpenCV 4.13 is acceptable ONLY here)

```bash
python -m pip install numpy opencv-python fastapi uvicorn httpx pydantic
PYTHONPATH=code python -m unittest discover -s code -p 'test_*.py' -v
```

### What's newly implemented

- `code/witness_planner.py`: **optima SET** intersection; minimal conflicting subset (including 3-world core); possibility-set signatures; worst-case noncontact view regret; content-bound, deterministic evidence hash; verifier checks published fields match hashed payload. **Toy model, never physical authorization.**
- `code/failure_interaction_graph.py`: small typed layer/rope/knot evidence graph with missing-state provenance and immutable revisions. Edges are potential interactions, not learned causality.
- `code/decision_gateway.py`: **single final gate**; witness request blocks `REORDER` proposed by older heuristic; stale observation and uncalibrated inputs fail closed; no action is auto-executed.
- `code/research_pipeline.py`: CV measurements, FIG and WITNESS integrated; ROI-manifest binding; two-frame content-bound certificate; uncalibrated uncertainty not displayed as `0 mm`.
- `code/api_research.py`: research FastAPI worker, auth token, input caps, require OpenCV5, no physical action.
- `deploy/Dockerfile`: runtime service startup (old file ran tests then exited), build-time OpenCV5 assertion.
- `code/test_v44_*.py`: extra adversarial regression tests; `v4.4_ローカル実行ログ.txt` holds actual local evidence.

### Runtime dependency rules

The Dockerfile pins **OpenCV5**; the current sandbox could not verify its actual Docker build. The local unit/synthetic tests use OpenCV4.13. All `OpenCV5/AWS/real physical tests` are NOT RUN. In AWS, do not expose `/api/research/analyze` directly to the public Internet: its token is only a research-layer check, not a production IAM/user authorization framework. Use private ingress, TLS, real owner JWT, rate control and required persistent session auditing before any real deployment.

The Research API requires expert-supplied ROI and calibration. It is not automatic cardboard segmentation. Bedrock, S3/DynamoDB live integration, a user-facing interactive two-view workflow and empirical human baselines remain **unimplemented**.

### Docker (requires network and an actual Docker daemon)

```bash
docker build --pull -f deploy/Dockerfile -t bind-zero-x-v44:runtime .
docker run --rm bind-zero-x-v44:runtime python -c 'import cv2; assert cv2.__version__.split(".")[0]=="5"'
```

Run the API only behind private TLS and an authenticated reverse-proxy with `BZX_RESEARCH_TOKEN` (32+ random characters from a secret manager). Detailed environment, data contract and verification gates: `v4.4_AWS_OpenCV5_実稼働証拠収集.md`.

### Validation plan

`v4.4_実物比較実験_前登録と中止条件.md` defines E adaptive view vs D fixed view, and E vs skilled B. The results of those experiments are **NOT RUN**, not filled with invented measurements. A 95+ competition score is not guaranteed by unit tests or the design alone.

### Regeneration and integrity

Run `PYTHONPATH=code python build_v44_release.py` from the extracted archive root to regenerate the local log, ledger, link map, SHA256 listing and ZIP; output goes to the working directory. Reproducible file content is preferred over identical ZIP bytes across timestamps. The bundled `historical_v43` source documents are reference only. The new v4.4 spec overrides earlier versions for changed behavior.
