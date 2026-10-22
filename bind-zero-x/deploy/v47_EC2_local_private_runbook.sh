#!/usr/bin/env bash
# BIND ZERO-X v4.7: Run from EC2 checkout under a private, authenticated tunnel.
# This is a manual runbook, NOT proof of AWS deployment or completion.
set -euo pipefail
mkdir -p evidence
DATE=$(date -u +%Y%m%dT%H%M%SZ)
# Avoid logging tokens and environment; never expose the research API on 0.0.0.0 publicly.
docker build --pull --no-cache -f deploy/Dockerfile -t bind-zero-x:v4.7 . \
  2>&1 | tee "evidence/${DATE}_docker_build.log"
docker image inspect bind-zero-x:v4.7 --format '{{.Id}}' > "evidence/${DATE}_image_id.txt"
docker run --rm --entrypoint python bind-zero-x:v4.7 \
  -c 'import cv2; print("OPENCV_VERSION",cv2.__version__); print(cv2.getBuildInformation())' \
  > "evidence/${DATE}_opencv5_build_information.txt"
grep -q 'OPENCV_VERSION 5.' "evidence/${DATE}_opencv5_build_information.txt" || {
  echo 'ERROR: genuine OpenCV 5 was not detected' >&2;exit 1;
}
if [[ ! -f ./deploy/research.env ]]; then
  echo 'Create deploy/research.env with a random >=32-character BZX_RESEARCH_TOKEN and'
  echo 'a separate >=32-character BZX_RESEARCH_INTEGRITY_KEY, chmod 600 it,'
  echo 'and configure BZX_RESEARCH_LOOP_DB=/tmp/bzx_research_loops.db.'
  echo 'Do not commit or publicly share research.env. No container launched.'
  exit 2
fi
chmod 600 ./deploy/research.env
# /tmp inside the container is EPHEMERAL. For durable state this prototype needs
# a deliberate bind mount with writable permissions or, preferably, DynamoDB.
docker run -d --rm --name bind-zero-x-research \
  --env-file ./deploy/research.env \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=100m \
  --security-opt no-new-privileges --cap-drop ALL \
  -p 127.0.0.1:8080:8080 bind-zero-x:v4.7
sleep 3
curl -fsS http://127.0.0.1:8080/health > "evidence/${DATE}_health.json"
curl -fsS http://127.0.0.1:8080/ready > "evidence/${DATE}_ready.json"
docker logs bind-zero-x-research > "evidence/${DATE}_container.log" 2>&1 || true
sha256sum evidence/${DATE}_* > "evidence/${DATE}_sha256.txt"
echo "Private local worker started. Evidence is in evidence/${DATE}_*"
echo 'Next: use actual images, independent GT and real AWS S3/DynamoDB provenance.'
