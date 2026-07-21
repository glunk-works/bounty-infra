# bounty-infra — hardening & working-method roadmap (reference of record)

> Established 2026-07-21 from the loop-orchestrator side (Opus/architect planning pass).
> This retrofits loop-orchestrator's disciplined working method onto this pre-existing repo
> **and** remediates the 2026-07-19 security review findings (#6–#14). It is the analog of
> loop-orchestrator's `docs/migration_roadmap.md` for this repo.

## Posture

**Governance-first, then scanner fixes, method interleaved** (locked, micro-gate 1). Branch
protection + a plan gate is the prerequisite for gating everything after it — you cannot
safely merge security fixes through the very ungated path (#8/#9) that is itself a finding.

## Public-repo posture (BI-D4)

**This repository is intentionally public** (portfolio project). Nothing below is a reason to
make it private; it is the set of invariants that make "public" safe. Verified 2026-07-21:
`.tf`/`.yml`/`.py`/`.toml`/`.md` contain **no** account IDs, ARNs, bucket names, or identity
IDs — every account-specific value resolves at runtime through Infisical (`env.TF_STATE_BUCKET`,
`env.AWS_OIDC_ROLE_ARN`, `vars.IDENTITY_ID`) or tofu variables. The only committed literal is
the ECR repo name `glunk-works/bounty-scanner`, which is inert.

**Where each class of sensitive material lives:**

| Class | Home | Never |
|---|---|---|
| Genuine secrets, account-specific values | Infisical (`/bounty-infra`, `prod`) | Committed, or echoed to a workflow log |
| RoE / scope allowlist (S1, #7) | Infisical — **runtime config** | A committed `scope.yaml`. It enumerates which bounty programs the operator is engaged with — the most sensitive artifact the system will hold |
| Scan findings, triage reports, resolved hosts/subdomains | S3 only | A workflow log, artifact, or PR comment. This is third-party vulnerability data |
| Pre-remediation vulnerability detail | Draft security advisories (below) | A public issue body, until the fix has landed |

**`tofu plan` output is summarized, never dumped.** Plan renders the account ID, real bucket
names, subnet/SG IDs, and ARNs at runtime even though none are committed. On a **public** repo,
workflow artifacts are world-readable, so "post an artifact instead of a PR comment" is **not**
a mitigation — both disclose. S0-T2 emits change counts + resource addresses only.

**Fork PRs receive no secrets**, so a required `tofu plan` check can never go green for an
outside contributor. Accepted (no external contributors expected). **`pull_request_target` must
stay off the table** as the "fix" — it would hand repo-scoped credentials to fork-controlled code.

**Coordinated disclosure.** Findings #6–#14 were filed as public issues while still unpatched.
Full pre-remediation detail now also lives in **private draft advisories** — `GHSA-59j8-c4rc-2jf4`
(#6), `GHSA-pf9q-vx7g-f8gr` (#7), `GHSA-p3hr-h7cq-xp5m` (#13) — to be **published once the
corresponding sprint closes**. Publishing the analysis *after* remediation is better portfolio
material than the current state, because it demonstrates the timing was understood.

**No private mirror repo.** Each candidate has a better-fitting home than a second repo (table
above); a mirror buys split history and a sync burden, and none of the four classes wants to
live in git. Revisit only if engagement contracts or program NDAs need a document home.

**Wrap + harden, not wrap-only:** loop-orchestrator's bounty loop enforces scope/sanitization
at *its* boundary, but that protects loop-mediated runs only. This scanner is independently
dispatchable, so #7 (scope) and #13 (triage injection) are fixed **here**, not delegated to
the wrapper (loop-orchestrator S47-D12; comments on #7/#13).

## Sprint sequence

| Sprint | Closes | Scope |
|---|---|---|
| **S0 — Governance & CI/CD hardening** | #6, #8, #9, #10 | Branch-protection ruleset + minimal working method; gated OpenTofu deploy (plan-on-PR + apply-on-merge, `production` Environment approval); non-bypassable CI on all paths; `run-scan.yml` injection fix + drop unused `GITHUB_TOKEN`. **Also unblocks loop-orchestrator S47's #18** (same file as #6). |
| **S1 — Scanner security core** | #7, #13 | The scanner's **own** structural scope check (RoE allowlist before any subprocess) and triage-prompt hardening (delimit/neutralize target-derived fields; triage advisory-only). The wrap+harden core. Its own planning pass at its boundary. |
| **S2 — Scanner robustness** | #11, #12, #14 | Tighten task-role IAM to what's used; pin tools/templates/deps (reproducible builds); distinguish partial/failed scans from clean success. |

**#6 severity is anticipatory, not live (qualifier added 2026-07-21).** `workflow_dispatch`
requires repo **write** access and there is a single collaborator, so #6 is not currently an
external privilege-boundary crossing — a principal who can dispatch could equally commit a
malicious workflow. It becomes genuinely High the moment **#18** lands and makes the workflow
machine-dispatchable from loop-orchestrator, at which point `target_domain` stops being
operator-typed. This does **not** change the ordering (#6 still ships before #18) but it does
mean S0 is not firefighting. *(`sprints/S0_governance_hardening/sprint_plan.md` still describes
this as "a live RCE-with-AWS-creds surface" — overstated on current facts; amend when S0 opens.)*

Method (skills, an IaC/AWS/Actions `security-critic` agent, the fresh-session
`architect-review` CI gate) layers across S0–S2 — not a dedicated sprint (MG1).

## The central conventions repo (BI-D3)

A **new central repo** is the single source of truth for the **working method / Global
Conventions** — the "our way of working" docs that each repo's `CLAUDE.md` **references**,
with **local extensions** per repo. This is a **docs/conventions** central home, **not** a
shared-code package:
- The portable Global Conventions (Python / IaC / commit taxonomy / Definition of Done) live
  in the central repo; loop-orchestrator's `conventions.md` moves/mirrors there too.
- Each repo's `CLAUDE.md` references the central conventions **and adds a local section**
  (bounty-infra: OpenTofu / Actions-security / scanner DoD).
- **Explicitly NOT in scope:** sharing *code* (`scope_validator`, `ingest.sanitize`) as a
  package — #7's scope check is the scanner's **own** implementation (S1). No cross-repo code
  refactor is implied.
- **Lightweight** (stand up a repo, host the conventions, point both `CLAUDE.md` files at it)
  and **does not block or feed S1**. **S0 does not depend on it** — S0's `CLAUDE.md` references
  loop-orchestrator's `conventions.md` as the interim source and points at the central repo
  once it exists.

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
- **BI-D3 (MG3, 2026-07-21) — a central repo hosts the shared conventions/way-of-working**
  that each repo's `CLAUDE.md` **references + locally extends** (best long-term home for the
  method). This is the reference-and-extend model with the shared source in a **dedicated
  central repo** rather than in loop-orchestrator. **Docs/conventions only — NOT a shared-code
  package** (`scope_validator` etc. stay each repo's own; #7 is bounty-infra's own impl).
  (Rejected: shared source living in loop-orchestrator's own repo — a dedicated central home
  is cleaner long-term; a shared *code* package — not wanted, out of scope.)
- **BI-D4 (2026-07-21) — public-repo posture** (§ *Public-repo posture* above): the repo stays
  **public**; secrets and the RoE allowlist live in **Infisical**, findings in **S3**,
  pre-remediation vuln detail in **draft advisories** published post-fix; `tofu plan` output is
  summarized only. (Rejected: making the repo private — it is deliberate portfolio material;
  a **private mirror repo** for the sensitive elements — every candidate has a better home than
  git, and a mirror adds split history + sync burden.)

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
