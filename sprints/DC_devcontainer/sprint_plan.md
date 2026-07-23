### FILEPATH: /sprints/DC_devcontainer/sprint_plan.md

**Sprint Goal:** Give this repo a `.devcontainer/` that runs the **entire green gate and the
session workflow on a consistent Linux base**, so a contributor stops fighting Windows /
PowerShell / CRLF / `jq`-missing drift and can reproduce every mergeable check locally *except*
the one that is credentialed by design (`tofu-plan`). One `Reopen in Container` and the same
commands CI runs — `hatch run lint:check`, `hatch run test:run`, `tofu fmt`/`validate`/`tflint`,
`hatch run audit:run`, `hatch run sbom:run`, `gitleaks`, `zizmor` — all pass locally.

**Not a roadmap sprint.** DC is an owner-prioritised dev-environment tooling task, inserted ahead
of **SE** (egress migration, BI-D5) and loop-orchestrator Phase 4. It introduces no BI-D decision
and changes no product behaviour: it touches **only** `.devcontainer/**` (plus, optionally, a
repo-root `.gitattributes` — see Task 4). No `src/**`, no `infra/**`, no `.github/workflows/**`,
no ruleset.

**Owner decisions locked this pass (2026-07-22):**
1. **Exclude the scanner runtime.** No Go, no subfinder/httpx/nuclei in the devcontainer.
   `src/Dockerfile` stays the *sole* definition of the runtime; duplicating it would create a
   second thing to drift, and **BI-D5 migrates that runtime to per-scan Vultr VMs** anyway. Unit
   tests use `tmp_path` I/O and never shell to the real tools, so nothing in the green gate needs
   them.
2. **Hybrid, pinned composition.** Official devcontainer *features* (version-tagged) for the
   well-trodden bits — Python 3.11 and the GitHub CLI. A small **`Dockerfile` layer** installs
   everything with no trustworthy official feature — OpenTofu, tflint, gitleaks, zizmor, `yq` —
   **by pinned version with SHA256-checksum verification**, matching this repo's SHA-pin-everything
   ethos (actions pinned to commit SHAs; scope-core pinned to a SHA; `pip-audit`/`cyclonedx`
   version-pinned). We do **not** pull unpinned third-party (`devcontainers-contrib`) features that
   run build-time install scripts.

**Out of scope:**
- The scanner runtime tier (decision 1 above).
- Any change to `src/`, `infra/`, workflows, or the ruleset. DC is dev-environment only.
- A Codespaces / prebuild configuration, a CI job that *builds* the devcontainer, or publishing
  the image to a registry. The devcontainer is built locally on demand; if we later want a CI
  "devcontainer still builds" check, that is a follow-on, not this task.
- Reconciling the #16 Python-runtime split. DC *surfaces* it (it ships both 3.11 and 3.14 so the
  operator can run the 3.14 `package` build locally) but does not *resolve* it — #16 stays open.

---

## The finding that shapes the sprint

The green gate looks like eight tools but is really **two OS-level prerequisites plus hatch**. Of
the eight required checks (`.ai/project.yml` → `ruleset.required_checks`):

| Required check | What it actually needs locally | Source |
|---|---|---|
| `lint`, `test`, `dependency-audit`, `sbom` | **Python 3.11 + hatch only** — ruff, bandit, pytest, `pip-audit==2.10.1`, `cyclonedx-bom==7.3.0` are all **hatch-provisioned envs**, not separate OS installs | `src/pyproject.toml` `[tool.hatch.envs.*]` |
| `tofu-validate` | **OpenTofu + tflint `v0.64.0`** (`tofu fmt -check -recursive`, `tofu init -backend=false && tofu validate`, `tflint --recursive`) | `.github/workflows/ci.yml` `tofu-validate` job |
| `secrets-scan` | **gitleaks** binary + the repo's `.gitleaks.toml` | `ci.yml` `secrets-scan` |
| `zizmor` | **zizmor** | `ci.yml` `zizmor` |
| `tofu-plan` | AWS + Infisical credentials — **cannot and should not run locally** (BI-D2). Correctly out of the devcontainer's reach. | `plan-infra.yml` |

Two consequences the original scope note missed:
- **`tflint v0.64.0` is part of a required check** and was absent from the note's tool list. It is
  in-scope, pinned to exactly `v0.64.0` so local `tflint` matches CI byte-for-byte.
- **The Python audit/sbom/lint tools do not need OS installs.** Python 3.11 + `hatch` provisions
  them. This keeps the `Dockerfile` layer small.

Beyond the gate, the **way-of-working session skills shell out to a workflow toolchain** the host
often lacks on Windows: `gh` (every `/resume` and `/handoff` call), `yq` (`/resume` reads
`.ai/project.yml`), `jq`, `git`. Shipping these is the other half of killing the drift — it is why
"the devcontainer" and not merely "a Python image."

---

## Target layout

```
.devcontainer/
  devcontainer.json     # base image + features (python 3.11, github-cli) + build ref + VS Code
  Dockerfile            # pinned+checksummed: OpenTofu, tflint v0.64.0, gitleaks, zizmor, yq;
                        #   hatch; Python 3.14 via `hatch python install 3.14`; jq
.gitattributes          # (optional, Task 4) enforce LF so host CRLF can't re-enter the tree
```

**Base image:** `mcr.microsoft.com/devcontainers/base:debian-bookworm` (Debian, non-root `vscode`
user — kills the Windows/PowerShell/CRLF friction outright, since the container filesystem is
Linux/LF).

**Dual Python without a second feature:** Python **3.11** comes from the official
`ghcr.io/devcontainers/features/python` feature (the CI-validated version). Python **3.14** — the
version CI *packages* on (`ci.yml` `package` job, the #16 drift) — is installed via
`hatch python install 3.14` in the Dockerfile, so hatch owns the second interpreter exactly as it
does in CI, rather than layering a second, differently-managed Python feature.

**VS Code extensions** (in `devcontainer.json` `customizations`): `ms-python.python`,
`charliermarsh.ruff`, `hashicorp.terraform` (the HCL LSP works against OpenTofu files). Kept to a
sensible minimum; trim on review if you prefer leaner.

---

## Pinning approach (decision 2, made concrete)

Each tool in the `Dockerfile` layer is fetched at a **fixed version** and its download verified
against a **recorded SHA256** before use — the same discipline as the repo's SHA-pinned actions.
`tflint` is fixed at **`v0.64.0`** to match CI. For OpenTofu, gitleaks, zizmor, and `yq`, the build
session selects the current stable release, **records the exact version + checksum in the
`Dockerfile`**, and does not use a floating `latest`/`@main`. (CLAUDE.md forbids `@latest`-style
installs while #12 is open; that spirit applies here.) The official `python` and `github-cli`
features are pinned to a **major-version tag** (`:1`), the standard, supported feature-pinning
granularity.

---

## Task breakdown (for the Sonnet build session)

1. **`devcontainer.json`** — Debian base image; `features` block with `python` (3.11) and
   `github-cli`, both `:1`-pinned; `build.dockerfile: Dockerfile`; `customizations.vscode.extensions`
   as above; a `remoteUser: vscode`. Add a `postCreateCommand` that runs `pip install hatch` **only
   if hatch is not baked into the image** (prefer baking it into the Dockerfile — see Task 2 — and
   keep postCreate empty or a one-line sanity echo).

2. **`Dockerfile`** — `FROM mcr.microsoft.com/devcontainers/base:debian-bookworm`; install, each
   pinned + SHA256-verified: OpenTofu, `tflint v0.64.0`, gitleaks, zizmor, `yq`; `jq` from apt;
   `pip install hatch`; `hatch python install 3.14`. Non-root-safe (install to `/usr/local/bin`).
   No scanner runtime.

3. **Verify the gate runs green in-container** (the Definition of Done). From a freshly built
   container, all of these pass:
   - `cd src && hatch run lint:check`
   - `cd src && hatch run test:run`
   - `cd src && hatch run audit:run`
   - `cd src && hatch run sbom:run`
   - `cd infra && tofu fmt -check -recursive && tofu init -backend=false && tofu validate && tflint --recursive`
   - `gitleaks detect --config .gitleaks.toml` (or the invocation matching how CI runs it)
   - `zizmor .github/workflows/`
   - `cd src && hatch build` on Python 3.14 (the `package` path) succeeds
   - `gh --version`, `yq --version`, `jq --version` resolve
   Record the run in the build session's `/handoff`. This list **is** the acceptance test.

4. **(Judgment call, build session decides) `.gitattributes`** — a repo-root `* text=auto eol=lf`
   would stop the Windows host from ever re-introducing CRLF into tracked files, which is a root
   cause of the drift DC targets. It is a repo-wide change beyond `.devcontainer/`, so it is called
   out separately: include it if the build session confirms it doesn't churn existing line endings
   unexpectedly (check `git add --renormalize .` diff first); otherwise leave it out and note why.

5. **README/docs pointer** — one short line somewhere discoverable (top of `CLAUDE.md` § Commands
   or a `.devcontainer/README.md`) that "Reopen in Container gives you the full green-gate
   toolchain." Keep it minimal; do not restate the tool list.

---

## Definition of Done

- `.devcontainer/devcontainer.json` + `.devcontainer/Dockerfile` build cleanly.
- Every command in Task 3 passes inside the container.
- Every tool in the `Dockerfile` layer is pinned to a fixed version with a recorded SHA256; the
  two features are `:1`-pinned. No floating `latest`/`@main`.
- No change under `src/`, `infra/`, or `.github/workflows/`; the `.gitattributes` decision (Task 4)
  is recorded either way.
- The repo's own green gate still passes (this task adds files it doesn't gate on, but the PR runs
  CI regardless).

## Follow-on (not this sprint)

- A CI "devcontainer still builds" check, if the image starts drifting silently. Deferred until
  there's evidence it's needed.
- **SE — egress migration (BI-D5)** remains the next *roadmap* sprint after DC.
