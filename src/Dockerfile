# ==========================================
# STAGE 1: Go Builder for Security Binaries
# ==========================================
FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git

RUN go install -v \
    github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install -v \
    github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install -v \
    github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# ==========================================
# STAGE 2: Lightweight Python Runner
# ==========================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/sec-ops/bin:${PATH}" \
    NUCLEI_TEMPLATES_DIR="/opt/sec-ops/nuclei-templates"

WORKDIR /opt/sec-ops

RUN groupadd -r sec-ops && useradd -r -g sec-ops sec-ops

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /go/bin/subfinder /opt/sec-ops/bin/subfinder
COPY --from=builder /go/bin/httpx /opt/sec-ops/bin/httpx
COPY --from=builder /go/bin/nuclei /opt/sec-ops/bin/nuclei

# Added boto3 for S3 interaction
RUN pip install --no-cache-dir google-genai pydantic boto3

RUN /opt/sec-ops/bin/nuclei -update-templates -ud ${NUCLEI_TEMPLATES_DIR}

COPY scanner.py /opt/sec-ops/scanner.py

RUN chown -R sec-ops:sec-ops /opt/sec-ops

USER sec-ops

ENTRYPOINT ["python", "/opt/sec-ops/scanner.py"]