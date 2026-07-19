# OpsMate RAG backend — python:3.12-slim, non-root, uvicorn on 8001.
# Multi-arch: the base image is published for arm64 and amd64, so the same
# Dockerfile builds on a Mac and on a Linux node (the M3 portability rule).
FROM python:3.12-slim

# Chroma pulls in a few native wheels; slim has what they need at runtime, but
# keep the image lean and predictable.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first so the layer caches across code edits.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .

# Run as a non-root user, and own the data dir so the embedded Chroma store is
# writable when the volume is mounted.
RUN useradd --create-home --uid 10001 opsmate \
    && mkdir -p /data/chroma \
    && chown -R opsmate:opsmate /app /data
USER opsmate

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
