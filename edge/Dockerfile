# Pratyaksha Phase 4: CPU-Only Slim Edge Agent Dockerfile
# Optimized for Raspberry Pi 4/5 (ARM64) and Mini PCs (x86_64).
# Enforces non-root execution for edge device security.

FROM python:3.11-slim

# System runtime dependencies for OpenCV and SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system user
RUN groupadd -g 1000 pratyaksha && \
    useradd -u 1000 -g pratyaksha -s /bin/bash -m pratyaksha

WORKDIR /app

# Install Python requirements
COPY edge/requirements.txt /app/edge/requirements.txt
RUN pip install --no-cache-dir -r /app/edge/requirements.txt

# Copy application source code (Phase 1 modules + Phase 4 edge agent)
COPY detector.py pipeline.py zones.py config.yaml /app/
COPY yolov8n.pt /app/
COPY edge /app/edge

# Ensure write permissions on persistent storage directory
RUN mkdir -p /app/edge/data/evidence && \
    chown -R pratyaksha:pratyaksha /app

# Switch to non-root user
USER pratyaksha

# Volume mount for persistent SQLite outbox and logs
VOLUME ["/app/edge/data"]

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PRATYAKSHA_CONFIG_PATH=/app/edge/edge_config.yaml

CMD ["python", "-m", "edge.agent"]
