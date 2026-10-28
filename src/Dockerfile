# STAGE 1: Go Builder
FROM golang:1.27-alpine@sha256:4c9fe60190a2a3350ddc51de80d0224b8a6698d12bdfc999fee45ea9d6c46dbc AS builder
RUN apk add --no-cache git
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@v2.14.0 && \
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@v1.10.0 && \
    go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@v3.11.0

# STAGE 2: Python Runner
FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/sec-ops/bin:${PATH}" \
    NUCLEI_TEMPLATES_DIR="/opt/sec-ops/nuclei-templates" \
    HOME="/opt/sec-ops"

WORKDIR /opt/sec-ops
RUN groupadd -r sec-ops && useradd -r -g sec-ops sec-ops

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /go/bin/subfinder /opt/sec-ops/bin/subfinder
COPY --from=builder /go/bin/httpx /opt/sec-ops/bin/httpx
COPY --from=builder /go/bin/nuclei /opt/sec-ops/bin/nuclei

# Copy the project files and install natively (removes reliance on external 'dist/' folder)
COPY pyproject.toml .
COPY bounty_scanner/ bounty_scanner/
RUN pip install --no-cache-dir .

RUN /opt/sec-ops/bin/nuclei -update-templates -ud ${NUCLEI_TEMPLATES_DIR}
RUN chown -R sec-ops:sec-ops /opt/sec-ops
USER sec-ops

ENTRYPOINT ["python", "-m", "bounty_scanner.scanner"]