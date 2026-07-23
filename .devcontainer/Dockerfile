# Dev-environment image for bounty-infra (DC sprint). Reproduces every command in the
# repo's green gate (.ai/project.yml gates.green) on one consistent Linux base, so
# contributors stop fighting Windows / PowerShell / CRLF / missing-jq drift.
#
# Scanner runtime is deliberately EXCLUDED: src/Dockerfile stays the sole definition of
# that runtime, and BI-D5 (docs/hardening_roadmap.md) migrates it off AWS entirely, so
# duplicating it here would just be a second thing to drift.
#
# Every tool below is pinned to a fixed version and SHA256-verified against a recorded
# checksum before use -- no floating `latest`/`@main` (CLAUDE.md, while #12 is open).
# Where the upstream project publishes its own checksum manifest (OpenTofu, tflint,
# gitleaks, yq), the value below was copied from that manifest. zizmor's release
# publishes no checksum manifest at all, so its value was computed locally from the
# downloaded release asset by this build session -- self-sourced, not upstream-verified,
# but still a fixed, recorded pin rather than an unverified download.
# `debian-bookworm` (as originally scoped) is not a published tag for this image;
# `bookworm` is the correct one -- verified against the registry during the build pass.
FROM mcr.microsoft.com/devcontainers/base:bookworm

ARG TOFU_VERSION=1.12.5
ARG TOFU_SHA256=a6894d45ae7a17ce83189cce8fe04b5a65f68cefceb62455b5a6a89fa53ab38f
# Pinned to match the tofu-validate required check's setup-tflint version exactly.
ARG TFLINT_VERSION=0.64.0
ARG TFLINT_SHA256=cca9d13e2e1d7a2c627af60ff899a3c9b74212899416aeb96ec764d2ef954537
ARG GITLEAKS_VERSION=8.30.1
ARG GITLEAKS_SHA256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
ARG ZIZMOR_VERSION=1.28.0
ARG ZIZMOR_SHA256=e87b67160194884e375a46a12c57ccc904f762b53845f254fab7f17d98809c09
ARG YQ_VERSION=4.53.3
ARG YQ_SHA256=fa52a4e758c63d38299163fbdd1edfb4c4963247918bf9c1c5d31d84789eded4
# hatch itself has no upstream checksum manifest to verify against (it's a PyPI
# package, not a signed binary release) -- pip's own TLS + PyPI index integrity is
# the trust root here. Version-pinned so a build doesn't silently pick up whatever
# is newest on PyPI, matching CLAUDE.md's no-`@latest` posture (#12 open).
ARG HATCH_VERSION=1.17.1

# curl/unzip/ca-certificates: fetch + verify the pinned binaries below.
# python3-pip: gives this layer its own pip so `hatch` installs without depending on the
# devcontainer.json `features` layer, which composites on TOP of this Dockerfile and
# therefore isn't guaranteed present yet when this RUN executes.
# jq: required check tooling the way-of-working session skills shell out to directly
# (not hatch-provisioned, unlike ruff/bandit/pytest/pip-audit/cyclonedx).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      unzip \
      ca-certificates \
      python3-pip \
      jq \
    && rm -rf /var/lib/apt/lists/*

# OpenTofu -- ci.yml pins only the setup-opentofu ACTION (v2.0.2), not a tofu binary
# version, so there is no CI value to match here. This build session selected the
# current stable release at the time DC was built.
RUN curl -fsSLo /tmp/tofu.tar.gz \
      "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_amd64.tar.gz" \
    && echo "${TOFU_SHA256}  /tmp/tofu.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/tofu.tar.gz -C /usr/local/bin tofu \
    && chmod 755 /usr/local/bin/tofu \
    && rm /tmp/tofu.tar.gz

# tflint -- pinned to v0.64.0 so local output matches CI's tofu-validate job byte-for-byte.
RUN curl -fsSLo /tmp/tflint.zip \
      "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_amd64.zip" \
    && echo "${TFLINT_SHA256}  /tmp/tflint.zip" | sha256sum -c - \
    && unzip -q /tmp/tflint.zip -d /usr/local/bin \
    && chmod 755 /usr/local/bin/tflint \
    && rm /tmp/tflint.zip

# gitleaks -- ci.yml's secrets-scan job pins only gitleaks-action (v3.0.0), not a
# gitleaks binary version, so there is no CI value to match here. This build session
# selected the current stable release at the time DC was built.
RUN curl -fsSLo /tmp/gitleaks.tar.gz \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    && echo "${GITLEAKS_SHA256}  /tmp/gitleaks.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && chmod 755 /usr/local/bin/gitleaks \
    && rm /tmp/gitleaks.tar.gz

# zizmor -- ci.yml's zizmor job pins only zizmor-action (v0.6.0), not a zizmor binary
# version, so there is no CI value to match here. This build session selected the
# current stable release at the time DC was built. Unlike its four neighbors, zizmor's
# GitHub release publishes NO checksum manifest, so ZIZMOR_SHA256 above was computed
# locally from this exact downloaded asset, not cross-checked against an upstream
# source -- trust-on-first-use, not upstream-verified.
RUN curl -fsSLo /tmp/zizmor.tar.gz \
      "https://github.com/zizmorcore/zizmor/releases/download/v${ZIZMOR_VERSION}/zizmor-x86_64-unknown-linux-gnu.tar.gz" \
    && echo "${ZIZMOR_SHA256}  /tmp/zizmor.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/zizmor.tar.gz -C /usr/local/bin zizmor \
    && chmod 755 /usr/local/bin/zizmor \
    && rm /tmp/zizmor.tar.gz

# yq -- `/resume`/`/handoff` read .ai/project.yml with it; ships as a raw binary, no archive.
RUN curl -fsSLo /tmp/yq \
      "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_amd64" \
    && echo "${YQ_SHA256}  /tmp/yq" | sha256sum -c - \
    && mv /tmp/yq /usr/local/bin/yq \
    && chmod 755 /usr/local/bin/yq

# hatch provisions ruff/bandit/pytest/pip-audit/cyclonedx-bom as envs (src/pyproject.toml);
# none of those need a separate OS install. Python 3.14 is the `package` job's build
# target (ci.yml) -- hatch's own interpreter manager provisions it independently of
# whatever Python version the devcontainer.json `python` feature adds on top of this
# image, so the #16 3.11-vs-3.14 split (CLAUDE.md) is surfaced, not resolved, here.
RUN pip install --break-system-packages --no-cache-dir "hatch==${HATCH_VERSION}" \
    && su vscode -c "hatch python install 3.14"

USER vscode
