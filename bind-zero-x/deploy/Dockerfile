FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    'numpy==2.2.6' 'opencv-python-headless==5.0.0.93' \
    'fastapi==0.128.2' 'uvicorn==0.48.0' 'pydantic==2.12.5'
COPY code/ /app/code/
ENV PYTHONPATH=/app/code
RUN python -c "import cv2; assert cv2.__version__.split('.')[0]=='5', cv2.__version__;print('OPENCV5',cv2.__version__)"
# Bind inside private container network only; publish port via loopback/tunnel, NEVER public.
# BZX_CAPTURE_ARCHIVE_DIR must point to a writable, persistent bind-mounted volume;
# the local research loop store is not S3/DynamoDB or multi-tenant AWS state.
EXPOSE 8080
USER 65534:65534
CMD ["uvicorn","api_research:app","--host","0.0.0.0","--port","8080","--workers","1","--no-proxy-headers"]
