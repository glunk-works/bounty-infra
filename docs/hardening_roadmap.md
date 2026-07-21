# bounty-infra — hardening & working-method roadmap (reference of record)

> Established 2026-07-21 from the loop-orchestrator side (Opus/architect planning pass).
> This retrofits loop-orchestrator's disciplined working method onto this pre-existing repo
> **and** remediates the 2026-07-19 security review findings (#6–#14). It is the analog of
> loop-orchestrator's `docs/migration_roadmap.md` for this repo.

## Posture

**Governance-first, then scanner fixes, method interleaved** (locked, micro-gate 1). Branch
protection + a plan gate is the prerequisite for gating everything after it — you cannot
safely merge security fixes through the very ungated path (#8/#9) that is itself a finding.

**Wrap + harden, not wrap-only:** loop-orchestrator's bounty loop enforces scope/sanitization
at *its* boundary, but that protects loop-mediated runs only. This scanner is independently
dispatchable, so #7 (scope) and #13 (triage injection) are fixed **here**, not delegated to
the wrapper (loop-orchestrator S47-D12; comments on #7/#13).

## Sprint sequence

| Sprint | Closes | Scope |
|---|---|---|
| **S0 — Governance & CI/CD hardening** | #6, #8, #9, #10 | Branch-protection ruleset + minimal working method; gated OpenTofu deploy (plan-on-PR + apply-on-merge, `production` Environment approval); non-bypassable CI on all paths; `run-scan.yml` injection fix + drop unused `GITHUB_TOKEN`. **Also unblocks loop-orchestrator S47's #18** (same file as #6). |
| **S1 — Scanner security core** | #7, #13 | The scanner's own structural scope check (RoE allowlist before any subprocess) and triage-prompt hardening (delimit/neutralize target-derived fields; triage advisory-only). Consumes the **shared scope validator** from the central repo (BI-D3). Its own planning pass at its boundary. |
| **S2 — Scanner robustness** | #11, #12, #14 | Tighten task-role IAM to what's used; pin tools/templates/deps (reproducible builds); distinguish partial/failed scans from clean success. |

Method (skills, an IaC/AWS/Actions `security-critic` agent, the fresh-session
`architect-review` CI gate) layers across S0–S2 — not a dedicated sprint (MG1).

## Parallel workstream — the central shared repo (BI-D3, revised)

A **new central repo** is the single source of truth for the working method **and** shared
code, consumed by both loop-orchestrator and bounty-infra:
- **Conventions** (the portable Global Conventions) live there; each repo's `CLAUDE.md`
  references them + adds local extensions.
- **Shared code** — `scope_validator`, `ingest.sanitize` — migrates there so #7/#13 (here)
  and loop-orchestrator's own boundary consume **one** implementation, not mirrored copies.
- **Implication (cross-repo refactor):** loop-orchestrator eventually migrates its
  `tools/scope_validator`/`tools/ingest` to depend on the shared package — its own planning
  item, not blocking.
- **Sequencing:** feeds **S1** (the shared scope validator #7 consumes). Needs its **own
  architecture/planning pass** (repo creation, package layout, versioning/publish, the
  loop-orchestrator migration). **S0 does not depend on it** — S0's `CLAUDE.md` references
  loop-orchestrator's `conventions.md` as the interim source and notes the migration.

## OPEN — compute-model architecture decision (raised 2026-07-21; needs its own pass)

The **described** architecture (loop-orchestrator `docs/bounty_loop_architecture.md` / older
framing) is *dynamically provisioned Ubuntu compute nodes bootstrapped with Nuclei/Amass/ffuf*
— a VM model that would be **Ansible-provisioned**. The **actual** implementation is **AWS
Fargate** with `subfinder`/`httpx`/`nuclei` **baked into the Docker image** (`src/Dockerfile`,
multi-stage Go builder) — **no Ansible, no VM, a different toolset**. This is a real
mismatch, and "missing Ansible" is a symptom of an unmade decision:
- **Option A — stay Fargate/Docker** (current reality): no Ansible; tool provisioning is the
  Dockerfile. Reconcile the docs to match. Simplest; keeps the zero-ingress serverless model.
- **Option B — move to Ansible-provisioned VM nodes** (the described model): adds Ansible
  playbooks for node bootstrap, EC2/ASG infra, Amass/ffuf. A large re-architecture.
- **Option C — hybrid:** Fargate for batch recon, Ansible-provisioned nodes for a class of
  deep/long scans.

**Do not resolve in passing** — it changes the compute topology, the IAM model, and the S3
output path all three sprints assume. Needs a dedicated architecture pass before it can be
sequenced. **Captured here so it is not lost.** (Also note a docs-drift symptom: the README
lists workflows `build-and-push.yml` that don't exist and claims "least privilege IAM" that
#11 contradicts — fold into S2 / a docs pass.)

## Locked decisions (this planning pass, 2026-07-21, owner-confirmed via micro-gates)

- **BI-D1 (MG1)** — governance-first sequence (above). (Rejected: full-method-first — delays
  the High vulns; vulns-only — doesn't establish the working method.)
- **BI-D2 (MG2)** — gated deploy: `tofu plan` on PRs touching `infra/**` (visible), apply job
  on merge-to-main targeting a protected `production` **Environment** with a required
  reviewer; `-auto-approve` stays but runs only post-approval. (Rejected: no Environment gate;
  manual-dispatch-only apply.)
- **BI-D3 (MG3, revised 2026-07-21) — central shared repo** (best long-term single source):
  conventions **and** shared code (`scope_validator`, `ingest.sanitize`) live in a new central
  repo both repos consume. Its own workstream (above); feeds S1. (Chosen over: shared-core +
  local-extension reference — still two code copies; copied-and-owned — drifts.)

## Cross-repo coupling

- **loop-orchestrator #18** (recon dispatch contract) lands `seed`/`token` inputs in
  `run-scan.yml` — **must ride S0's #6 fix** (env+jq, no inline `${{ }}`). So S0 unblocks
  S47's live V-run.
- **kms:Decrypt:** #11 tightens the *scanner task role*; loop-orchestrator's fetch uses a
  *different* OIDC role that needs its own `kms:Decrypt` — no conflict (distinct principals).

## Pointers

- The 2026-07-19 review findings: issues #6–#16 (this repo).
- loop-orchestrator `docs/bounty_loop_architecture.md` §5/§10, S47-D12 — shared design context.
- `sprints/S0_governance_hardening/sprint_plan.md` — the detailed S0 plan.
