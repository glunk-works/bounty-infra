# CLAUDE.md

Lean routing layer for this repo — kept small and stable so it stays prompt-cached.
What remains here is **local truth**: what this system is, and the rules that hold only
here. The portable working method no longer lives in this file (see § *The working method*).
The deep record (roadmap, sprint plans, decisions) is in `docs/` and `sprints/`, loaded on
demand. **Where we are right now** lives in `.ai/next-steps.md`.

## What this is

bounty-infra is an **AWS bug-bounty reconnaissance pipeline**: a `workflow_dispatch`
launches a Fargate task (`.github/workflows/run-scan.yml`) running the `bounty_scanner`
Python package, which shells `subfinder`/`httpx`/`nuclei` (baked into `src/Dockerfile`,
multi-stage Go builder), triages findings through Gemini, and writes results to S3.
OpenTofu in `infra/` owns the cluster, ECR repo, task definition, IAM, and networking.
Zero ingress; every account-specific value resolves at runtime through Infisical
(`env.AWS_OIDC_ROLE_ARN`, `env.TF_STATE_BUCKET`, `vars.IDENTITY_ID`) or tofu variables.

> **This repo is under active hardening — read the roadmap before extending it.**
> [`docs/hardening_roadmap.md`](docs/hardening_roadmap.md) is the reference of record:
> the sprint sequence (S0 governance → S1 scanner security → S2 robustness, plus **SG** CI
> gates and **SE** egress migration), and the locked decisions (**BI-D1..BI-D13**).
>
> **The compute-model question is RESOLVED as of 2026-07-21 (BI-D5):** scan egress leaves
> AWS for per-scan ephemeral VMs on Vultr; AWS keeps the control plane (S3 findings + KMS,
> tofu state, OIDC roles). The ECS/Fargate + VPC half of `infra/` is slated for retirement,
> so **do not extend it** — read BI-D5 before touching `infra/main.tf`.

## The working method (owned elsewhere — do not restate it here)

Session protocol, Global Conventions, commit/branch grammar, the merge bar, model routing,
and the review agents come from the **`way-of-working` plugin** (`glunk-works/claude-workbench`,
pinned to a tag in `.claude/settings.json`), parameterized by
**[`.ai/project.yml`](.ai/project.yml)** — this repo's required checks, green gate, code
paths, and the paths to the deep record. Read `.ai/project.yml` at the start of a session;
never copy its values into this file, and never shadow a plugin skill with a local copy of
the same name. Both rules, and why, are in the plugin's `reference/project-schema.md`.

## Local: OpenTofu

- `tofu fmt` is the formatter of record; `tofu validate` must exit 0. Use
  `tofu init -backend=false` when validating so no AWS credentials are needed — only a
  real `plan`/`apply` gets creds.
- **No infra change reaches AWS without a visible plan and a human approval** (BI-D2):
  `tofu plan` on PRs touching `infra/**`, apply on merge-to-main behind the protected
  `production` Environment. `-auto-approve` is allowed *only* post-approval.
- **`tofu plan` output is summarized, never dumped** (BI-D4). Plan renders the account ID,
  bucket names, and subnet/SG IDs at runtime even though none are committed, and on a
  public repo both PR comments *and* workflow artifacts are world-readable. Emit change
  counts + resource addresses only.

## Local: GitHub Actions security

- **Never interpolate `${{ }}` inline into a `run:` block.** Pass values via `env:`, quote
  every expansion (`"$TARGET_DOMAIN"`), and build JSON with `jq -n --arg` — never string
  concatenation. This was finding #6, fixed in S0-T4; `run-scan.yml`'s *Trigger Scan Task*
  step is the in-house reference shape.
- `set -euo pipefail` at the top of any non-trivial `run:` block.
- Grant the **narrowest `permissions:`** that works and delete unused ones (#10: the
  scanner makes no GitHub API call, so `issues: write` and `GITHUB_TOKEN` do not belong).
- **Never `pull_request_target`.** Fork PRs get no secrets, and that is the correct
  outcome — `pull_request_target` would hand repo-scoped credentials to fork-controlled
  code. Accepted consequence: a credentialed check can never go green for a fork.
- **A job's OIDC subject is derived from its trigger and its `environment:`, in that
  precedence: Environment > `pull_request` > branch ref.** Adding `environment: X` to a job
  makes it present `repo:<org>/<repo>:environment:X` *instead of* the branch subject, which
  breaks auth at both hops until each is updated. Treat a trigger/environment change as a
  change to the job's identity. Where the verifier takes a list (the AWS trust condition)
  **append** the new subject — never replace, since sibling workflows share the role. Where
  it takes a single value (Infisical's Subject) **bind on the `repository` + `ref` claims
  instead**: they are invariant to the environment. Never widen with a `repo:…:*` glob —
  in OIDC auth `*` matches `:` too, so it also admits `:pull_request`.
- Pin third-party actions to a **commit SHA**, not a floating tag — a mutable tag on an
  action that receives OIDC claims is a credential-handoff to whoever moves the tag.
- **Required checks match by check-run name = job id**, so never add a `name:` override to a
  gated job — it renames the check run and silently un-requires the gate. The authoritative
  list of what is required is `ruleset.required_checks` in `.ai/project.yml`.
- **Secrets and identity never reach a workflow log.** No `aws sts get-caller-identity`
  echo, no `set -x` around a credentialed step.

## Local: scanner (`src/`)

- Definition of Done for a `src/` change: `hatch run lint:check` (ruff check + ruff format
  --check + `bandit -ll`) and `hatch run test:run` both green, plus pinned tools — do not
  add a `@latest` install while #12 is open.
- The scanner runs **untrusted, target-derived data**. Anything reaching a subprocess argv,
  a filename, or a Gemini prompt is hostile input.
- **Shared *code* is consumed, not reimplemented (BI-D6).** The scope check (#7) and the
  triage sanitizer (#13) come from **`glunk-works/scope-core`**; neither product repo depends
  on the other. See `sprints/SC_scope_core_extraction/sprint_plan.md`.
- `requires-python = ">=3.11"`, but CI validates on 3.11 and packages on 3.14; treat that
  split as drift to reconcile (see #16), not as an intended matrix.

## Local: what must not be committed

Genuine secrets and account-specific values → **Infisical** (`/bounty-infra`, `prod`).
The RoE / scope rules → **S3, one object per engagement** (`s3://<findings-bucket>/roe/<program>/scope.json`,
BI-D8/BI-D9), never this repo — a committed scope file would enumerate which bounty programs
the operator is engaged with, the most sensitive artifact this system holds. Scan findings,
triage reports, resolved hosts → **S3 only**, never a workflow log, artifact, or PR comment
(third-party vulnerability data). Pre-remediation vulnerability detail → a **draft security
advisory** until the fix ships. Full table and rationale: `docs/hardening_roadmap.md`
§ *Public-repo posture (BI-D4)*.

## Commands

The **green gate** — what must pass before a PR — is `gates.green` in `.ai/project.yml`, not
restated here. The rest of the local toolchain:

```bash
hatch run lint:fmt        # (from ./src) ruff format + ruff check --fix
hatch build               # (from ./src) wheel
```

A real `tofu plan`/`apply` additionally needs Infisical-sourced backend config
(`-backend-config="bucket=…"`, `region`, `dynamodb_table`) and the assumed OIDC role — it
does not run cleanly from a laptop by design.

## Pointers (load on demand)

- **`.ai/next-steps.md`** — the live cursor: current sprint/task, next action, which model.
  Read this first.
- **`.ai/project.yml`** — this repo's parameterization of the working method.
- **`docs/hardening_roadmap.md`** — reference of record: posture, BI-D1..D13, sprint
  sequence, public-repo rules, cross-repo coupling. Also serves as the threat model.
- **`sprints/*/sprint_plan.md`** — the per-sprint plans (S0, S1, SC, SW).
- **`glunk-works/global-bootstrap`** — owns this repo's AWS foundation: the OpenTofu state
  bucket + lock table, the findings bucket + KMS key, and **every GitHub OIDC role**
  (generated per project from `var.projects`). `AWS_OIDC_ROLE_ARN` and `AWS_PLAN_ROLE_ARN`
  resolve to roles defined *there*, not in `infra/`. Any change to what CI may do in AWS is
  a change to that repo — and its trust conditions are subject-scoped, so a **new workflow
  trigger generally needs a new role**, not a widened one.
- **`glunk-works/claude-workbench`** — the `way-of-working` plugin: skills, agents, the
  Global Conventions, and `reference/project-schema.md`.

> Note: the README predates the current architecture — it lists a `build-and-push.yml` that
> does not exist and claims least-privilege IAM that #11 contradicts. Trust
> `docs/hardening_roadmap.md` over the README.
