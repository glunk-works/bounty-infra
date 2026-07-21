# CLAUDE.md

Lean routing layer for this repo — kept small and stable so it stays prompt-cached.
Day-to-day guardrails (commands, boundaries, model routing) live here; the deep record
(roadmap, sprint plans, decisions) is in `docs/` and `sprints/`, loaded on demand.
**Where we are right now** lives in `.ai/next-steps.md`.

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
> the sprint sequence (S0 governance → S1 scanner security → S2 robustness), the locked
> decisions (**BI-D1..BI-D4**), and the **OPEN compute-model question** (the docs describe
> Ansible-provisioned VM nodes; the implementation is Fargate + Docker — unresolved, do
> not settle it in passing). Findings #6–#14 from the 2026-07-19 review are open issues.

## Conventions: shared source + local extension (BI-D3)

The portable **Global Conventions** — Python, OpenTofu/IaC, Conventional-Commit grammar,
branch names, squash-merge policy, label taxonomy, Definition of Done — are **not restated
here**. Interim source of truth:
[`loop-orchestrator .ai/context/conventions.md`](https://github.com/glunk-works/loop-orchestrator/blob/main/.ai/context/conventions.md).
A dedicated central conventions repo is the agreed long-term home (BI-D3, its own pass);
re-point this link when it exists. **Docs/conventions only — not a shared-code package**:
the scanner's scope check (#7) is bounty-infra's own implementation, not an import.

Everything below is bounty-infra's **local extension**.

### Local: OpenTofu

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

### Local: GitHub Actions security

- **Never interpolate `${{ }}` inline into a `run:` block.** Pass values via `env:`, quote
  every expansion (`"$TARGET_DOMAIN"`), and build JSON with `jq -n --arg` — never string
  concatenation. This is finding #6; `run-scan.yml` still violates it until S0-T4 lands.
- `set -euo pipefail` at the top of any non-trivial `run:` block.
- Grant the **narrowest `permissions:`** that works and delete unused ones (#10: the
  scanner makes no GitHub API call, so `issues: write` and `GITHUB_TOKEN` do not belong).
- **Never `pull_request_target`.** Fork PRs get no secrets, and that is the correct
  outcome — `pull_request_target` would hand repo-scoped credentials to fork-controlled
  code. Accepted consequence: a credentialed check can never go green for a fork.
- Pin third-party actions to a **commit SHA**, not a floating tag — a mutable tag on an
  action that receives OIDC claims is a credential-handoff to whoever moves the tag.
- **Secrets and identity never reach a workflow log.** No `aws sts get-caller-identity`
  echo, no `set -x` around a credentialed step.

### Local: scanner (`src/`)

- Definition of Done for a `src/` change: `hatch run lint:check` (ruff check + ruff format
  --check + `bandit -ll`) and `hatch run test:run` both green, plus pinned tools — do not
  add a `@latest` install while #12 is open.
- The scanner runs **untrusted, target-derived data**. Anything reaching a subprocess argv,
  a filename, or a Gemini prompt is hostile input (#7 scope enforcement, #13 prompt
  injection — both S1).
- `requires-python = ">=3.11"`, but CI validates on 3.11 and packages on 3.14; treat that
  split as drift to reconcile (see #16), not as an intended matrix.

### Local: what must not be committed

Genuine secrets and account-specific values → **Infisical** (`/bounty-infra`, `prod`).
The RoE / scope allowlist → **Infisical, runtime config** — a committed `scope.yaml` would
enumerate which bounty programs the operator is engaged with, the most sensitive artifact
this system holds. Scan findings, triage reports, resolved hosts → **S3 only**, never a
workflow log, artifact, or PR comment (third-party vulnerability data). Pre-remediation
vulnerability detail → a **draft security advisory** until the fix ships. Full table and
rationale: `docs/hardening_roadmap.md` § *Public-repo posture (BI-D4)*.

## Commands

```bash
# scanner (run from ./src)
hatch run lint:check      # ruff check + ruff format --check + bandit -ll
hatch run lint:fmt        # ruff format + ruff check --fix
hatch run test:run        # pytest ./tests/
hatch build               # wheel

# infra (run from ./infra) — validate needs no credentials
tofu fmt -check -recursive
tofu init -backend=false && tofu validate
```

A real `tofu plan`/`apply` additionally needs Infisical-sourced backend config
(`-backend-config="bucket=…"`, `region`, `dynamodb_table`) and the assumed OIDC role — it
does not run cleanly from a laptop by design.

## Working here: models & the merge bar

- **Opus** — architecture, sprint **planning** (one question at a time, HITL micro-gates),
  reviewing a diff, threat-model calls, roadmap/decision-log updates.
- **Sonnet** — implementing an already-defined sprint task, tests, mechanical refactors,
  running the green gate.

Rule of thumb: deciding *what* to build or *whether* a diff is correct → Opus; executing a
spec that already exists → Sonnet.

**Every change lands via a reviewed PR.** Branch cut from `main` (`sprint/NN-slug` for
planned sprint work, `feat|fix|chore|docs/slug` for one-offs); **never commit to `main`,
never force-push a pushed branch, never merge your own PR** — the human's merge click is
the approval.

`main` is protected by the **`protected-integration-branches`** ruleset (id `19438326`,
matching loop-orchestrator's ruleset of the same name field-for-field): `pull_request` +
`deletion` + `non_fast_forward`, `bypass_actors: []`. **`required_approving_review_count`
is deliberately `0`** — single collaborator, and GitHub forbids self-approval, so any
review requirement would make every PR permanently unmergeable.

**Required status checks are not yet configured** — S0-T2/T3 create the checks
(`lint`, `test`, `tofu-validate`, `tofu-plan`) and the required list is applied at the
**end** of S0. Requiring a check that does not yet exist strands every open PR. Once
applied: **required checks match by check-run name = job id**, so never add a `name:`
override to a gated job — it renames the check run and silently un-requires the gate.

## Pointers (load on demand)

- **`.ai/next-steps.md`** — the live cursor: current sprint/task, next action, which model.
  Read this first.
- **`docs/hardening_roadmap.md`** — reference of record: posture, BI-D1..D4, sprint
  sequence, public-repo rules, the OPEN compute-model decision, cross-repo coupling.
- **`sprints/S0_governance_hardening/sprint_plan.md`** — the detailed S0 plan (T1–T4).
- **loop-orchestrator** — the reference implementation for the working method. Read its
  equivalent (`CLAUDE.md`, `.ai/context/`, `ci.yml`, `ruleset-drift.yml`) **before**
  designing any governance or CI pattern here, so the two repos stay diffable.

> Note: `docs/` and the README predate the current architecture in places — the README
> lists a `build-and-push.yml` that does not exist and claims least-privilege IAM that #11
> contradicts. Trust `docs/hardening_roadmap.md` over the README.
