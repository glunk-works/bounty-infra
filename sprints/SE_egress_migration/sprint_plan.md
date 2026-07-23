### FILEPATH: /sprints/SE_egress_migration/sprint_plan.md

**Sprint Goal:** Move scan **egress off AWS** onto a **per-scan ephemeral Vultr VM with a
reserved IP** (BI-D5), keeping AWS as the control plane (S3 findings + KMS, tofu state, OIDC
roles — all in `global-bootstrap`). Re-point the image build and the scan launcher, re-scope
the scanner's S3 credential to least-privilege short-lived STS, **prove it end-to-end**, then
**retire** the Fargate/VPC/ECR estate. The scanner image itself does not change (BI-D5: the
provider coupling is only the launcher and the credential path).

**This is the SE roadmap sprint (BI-D5).** It closes the roadmap's `SE — Egress migration` row:
retire ECS/VPC/ECR from `infra/**`; per-scan Vultr VM; re-point `run-scan.yml`; S3-write
credential path for the VM; provider abuse-team notification.

---

## Decisions locked this planning pass (2026-07-22, owner-confirmed via micro-gates)

- **SE-MG1 — Hybrid management.** `infra/` swaps the AWS provider for the **Vultr provider** and
  manages only the **long-lived** reserved IP + firewall + startup config; `run-scan.yml`
  **imperatively creates/attaches/destroys the per-scan VM**, the direct heir of today's
  `aws ecs run-task`. `infra/` survives repurposed; BI-D2's plan+approval gate stays intact;
  `tofu-plan`/`tofu-validate` stay meaningful. (Rejected: *all-imperative, delete `infra/`* —
  loses the visible-plan gate on persistent topology and drops two required checks;
  *all-tofu incl. the per-scan VM* — state-lock contention + state churn per scan, ephemeral
  cattle in a durable state file.)
- **SE-MG2 — Scoped STS creds via cloud-init user-data.** `run-scan.yml` assumes its OIDC role
  (as today), then `sts:AssumeRole` with a **session policy** narrowed to *this program's*
  findings prefix + the RoE object + KMS, and a **short `DurationSeconds`** (≈ scan timeout).
  The three session vars ride in the VM's **cloud-init user-data**; boto3's default chain reads
  them. **No ingress on the VM** (zero-ingress preserved). This session policy **is the
  re-scoped #11** — least-privilege replaces the broad Fargate `task_role`. (Rejected:
  *post-boot SSH injection* — needs inbound 22, regresses zero-ingress; *VM never touches AWS,
  runner writes S3* — third-party vuln data would transit the runner, and it rewrites
  scanner.py's S3 path that BI-D5 says needs no change.)
- **SE-MG3 — GHCR, public image.** `build-image.yml` pushes
  `ghcr.io/glunk-works/bounty-scanner:<sha>` via `GITHUB_TOKEN` (`packages: write`); the build
  path **stops touching AWS entirely** (blast-radius win), and the VM pulls a **public** image
  with **no credential** (one fewer secret on the most disposable box). Sha-pinned / no
  `:latest` / CI-gated preserved; consistent with BI-D4's public posture (the image carries no
  secrets; `src/Dockerfile` is already public). (Rejected: *private GHCR* — needs a pull token
  on the VM to protect an image with nothing to protect; *Docker Hub* — extra account +
  anon-pull rate limits → flaky scans.)
- **SE-MG4 — Two-phase within SE: stand up + prove, then retire.** PR1 adds Vultr **alongside**
  the existing AWS resources, re-points both workflows, and proves a scan end-to-end from a
  Vultr box to S3. PR2, **only after that proof**, deletes the Fargate half as a **destroys-only**
  plan (exactly what BI-D2's visible-plan gate is for). Never leaves the operator without a
  working scanner; the big destroy is reviewed in isolation. (Rejected: *big-bang* — no Vultr
  proof before the fallback is gone, hardest plan to review safely; *stand-up only, retire
  later* — leaves zombie AWS infra and doc/reality drift, and doesn't close SE's roadmap row.)
- **SE-MG5 — On-demand, registration-aware reserved IP (refines MG1 under the cost-ephemerality
  principle).** The reserved IP is Vultr's **only standing cost** (billed for as long as it
  exists — detaching doesn't stop the meter, only deleting does, and deleting loses the address).
  It exists solely to satisfy BI-D5's *stable, registrable identity* need, which only bites for
  **programs that mandate source-IP registration/deconfliction**. So SE ships with **no reserved
  IP → zero standing cost** (there are no onboarded programs yet). The reserved IP is a
  tofu resource **behind a toggle** (`reserved_ip_enabled`, default `false`), provisioned only
  when the operator onboards a registration-required program; `run-scan.yml` **attaches it only
  when the dispatcher asks** (`use_reserved_ip`, default `false`) — every other scan runs fully
  ephemeral on the instance's own auto-assigned IP and leaves nothing behind. (Rejected:
  *persistent from stand-up* — standing $/mo before any program needs it, the exact
  deploy-before-needed pattern the principle discourages; *no reserved IP ever* — can't satisfy
  registration-required programs, contradicting BI-D5's network-identity finding, a locked
  decision.) **Principle, not requirement:** the default is zero-cost ephemeral; the reserved IP
  is a deliberate, operator-triggered exception scoped to the programs that require it.

**Cross-repo dependency (`global-bootstrap`).** The AWS action set the workflow needs changes
from `ecs:RunTask` to `sts:AssumeRole` + a narrow S3 writer. Per BI-D5/CLAUDE.md,
`global-bootstrap` owns **every** OIDC role, subject-pinned. SE needs a **dedicated
`bounty-scanner-s3-writer` role** there (or confirmation the existing role can be chained-from)
whose permissions are S3 `PutObject` to the findings prefix + `GetObject` on the RoE object +
KMS `GenerateDataKey*`/`Decrypt`, and whose trust admits the existing `run-scan.yml` subject.
This is **not** a widened trust condition (the trigger is unchanged) — it is a new/adjusted
role, landed as its own gated PR **in `global-bootstrap`**, and it must merge before PR1's
`run-scan.yml` can authenticate.

---

## The seam that makes this small (why BI-D5 says the image needs no changes)

Today's two AWS touchpoints map cleanly onto the new substrate:

| Today (AWS) | SE (Vultr + GHCR) | Where |
|---|---|---|
| `build-image.yml`: build `src/` → push **ECR** `:<sha>` → register **ECS task-def** rev | build `src/` → push **GHCR** `:<sha>`; **no** ECR login, **no** task-def step | `.github/workflows/build-image.yml` |
| `run-scan.yml`: read tofu state (cluster/subnet/sg) → `ecs run-task` w/ overrides → `ecs wait` → read `exitCode` | assume role → **scoped `sts:AssumeRole`** → **`vultr instance-create`** (reserved IP, firewall, user-data) → **poll S3 status sentinel** → read exit code → **`vultr instance-delete`** | `.github/workflows/run-scan.yml` |
| `infra/main.tf`: VPC/IGW/subnet/SG, ECS cluster/task-def, ECR, CloudWatch, 2× Fargate IAM | `infra/main.tf`: **Vultr** firewall (free) + startup config; reserved IP **toggle-gated, off by default** (zero standing cost) | `infra/**` |
| `task_role` (broad S3 `PutObject`/`GetObject`/`ListBucket` + KMS on whole bucket) | **STS session policy**, per-program prefix-scoped (the re-scoped #11) | `run-scan.yml` + `global-bootstrap` role |

The scanner container's argv contract is **unchanged**: `<domain> --program <p> --contact-url
<url> --severities <s> --timeout <t> --max-findings <n>`, and `scanner.py` still uses boto3's
default credential chain. Only *where* the creds come from and *what host* runs the image change.

**The one genuinely new mechanism — the completion signal.** ECS gave us `ecs wait
tasks-stopped` + `exitCode`. A VM has no equivalent, and we must not stream findings
(third-party vuln data) back through the runner or a log (BI-D4). Chosen shape, **S3-mediated,
no SSH**: the launcher generates a `RUN_ID`; the user-data wrapper runs the container, captures
its exit code, and writes a tiny **status sentinel** (`runs/<RUN_ID>/status.json = {exit_code}`)
to S3 with the same scoped creds; the launcher **polls S3** for that object (bounded by the scan
timeout + margin), reads the exit code, then **always** destroys the instance (success, failure,
or timeout). This keeps success/failure distinguishable (a down-payment on S2's #14, not its full
treatment) with zero ingress and nothing sensitive in logs. Writing the sentinel is **user-data
shell, not an image change** — so BI-D5's "image needs no changes" holds. The session policy must
therefore also permit `PutObject` on `runs/<RUN_ID>/status.json`.

---

## Out of scope

- **A real-program live scan.** SE proves the path with a **controlled scan against an
  operator-owned domain**. A real bounty-program scan stays gated on **S1's missing RoE**
  (`s3://<findings-bucket>/roe/<program>/scope.json` does not exist yet — BI-D8/D9) and on the
  operator procedural gates below. This is the hermetic-vs-live line for the verification ledger.
- **Scanner image internals / `scanner.py`** — BI-D5: no changes. S1's #7 (scope enforcement)
  and #13 (prompt-injection sanitizer) are scanner-internal, provider-agnostic, and untouched.
- **S2 in full.** #11 is *absorbed* here (the STS re-scope); #14 (partial/failed vs clean) is
  only *touched* via the status sentinel — its full treatment stays S2. #12 (pin tools/deps)
  stays S2.
- **Concurrency beyond one scan.** A single reserved IP ⇒ scans **serialize** (see Constraints).
  A multi-IP pool is a future scale-up, not SE.
- **DigitalOcean fallback.** BI-D5 documents it as fallback; SE implements **Vultr only**.
- **The abuse-team notification and per-program IP registration** are **operator procedural
  gates** (below), documented as a runbook here but not code deliverables.

---

## Task breakdown

### Phase 1 — Stand up & prove (PR1, additive; AWS resources left in place)

1. **`global-bootstrap` (separate repo, separate gated PR — lands first).** Add/adjust the
   `bounty-scanner-s3-writer` role: trust admits `run-scan.yml`'s existing OIDC subject;
   permissions = S3 `PutObject` on the findings prefix + `runs/<...>/status.json`, `GetObject`
   on `roe/<program>/scope.json`, KMS `GenerateDataKey*`/`Decrypt` on the findings key.
   Confirm whether the existing `AWS_OIDC_ROLE_ARN` can `sts:AssumeRole`-chain into it (role
   chaining caps session duration at 1h — fine; default scan timeout is 1800s). Export its ARN
   as an Infisical value (e.g. `AWS_SCANNER_WRITER_ROLE_ARN`).

2. **`infra/` — add the Vultr provider + persistent resources** (keep all AWS resources this
   phase):
   - `provider "vultr"` (source `vultr/vultr`), API key from a new Infisical secret
     `VULTR_API_KEY`; region + plan as variables (default region near targets; plan 1 vCPU /
     2 GB to match the retired Fargate sizing).
   - `vultr_reserved_ip` **behind a toggle** — `count = var.reserved_ip_enabled ? 1 : 0`,
     `reserved_ip_enabled` **default `false`** (SE-MG5). Default state provisions **no** reserved
     IP → **zero standing cost**. The operator flips the toggle and applies only when onboarding
     a program that mandates source-IP registration; that apply is the resource's first (and
     only) provisioning. Its `reserved_ip_address` is then registered with the program.
   - `vultr_firewall_group` + rules: **no ingress**, egress unrestricted (mirrors the retired
     zero-ingress SG). Firewall groups are **free**, so this stays persistent and is referenced
     by every per-scan instance regardless of the reserved-IP toggle.
   - The **cloud-init / startup template** (as a `templatefile` or a committed
     `infra/scan-vm-userdata.sh.tftpl`) — see run-scan.yml Task 4 for what it must do; keep the
     *secret-bearing* parts (STS vars) injected by the launcher at run time, **not** baked into
     tofu state.
   - New `variables.tf` entries (`vultr_api_key`, `vultr_region`, `vultr_plan`,
     `reserved_ip_enabled` default `false`); new `outputs.tf` entries (`reserved_ip_id`,
     `reserved_ip_address`) that are **null/empty when the toggle is off** (guard with
     `one(...)`/`try(...)` so a disabled reserved IP doesn't error the plan). `tofu fmt` /
     `tofu validate` / `tflint --recursive` green.
   - `plan-infra.yml` / `deploy-infra.yml` gain `VULTR_API_KEY` from Infisical (the Vultr
     provider needs it to refresh/plan). Fork PRs still get no secrets — a Vultr plan can't go
     green for a fork, the same accepted consequence as the AWS plan today.

3. **`build-image.yml` → GHCR.** Replace the ECR login + build-push + `register-task-definition`
   steps with: `docker/login-action` to `ghcr.io` using `GITHUB_TOKEN`; build `./src`; push
   `ghcr.io/glunk-works/bounty-scanner:${{ github.sha }}` — **sha only, no `:latest`**. Add
   `permissions: packages: write`. **Drop** the AWS-credentials / OpenTofu / ECR steps entirely
   (the build path no longer touches AWS). The last ECR image is left intact as an emergency
   fallback until PR2 tears it down.

4. **`run-scan.yml` → Vultr launcher.** Replace the *Fetch Infrastructure Networking States* and
   *Trigger Scan Task* steps (keep the two structural validators for `target_domain` and
   `program`):
   - Add a `use_reserved_ip` **boolean `workflow_dispatch` input** (default `false`, SE-MG5).
     The dispatcher sets it `true` only for a program that requires source-IP registration.
     When `true`, read `reserved_ip_id` from tofu state and attach it at `instance-create`;
     when `false`, omit it and let the instance use its **own auto-assigned public IP** (fully
     ephemeral, nothing left behind). Fail fast with a clear error if `use_reserved_ip` is `true`
     but the reserved IP isn't provisioned (`reserved_ip_enabled=false`) — never silently fall
     back to a rotating IP for a program that required a registered one.
     *(Future robustness, not SE: make this authoritative from the RoE `scope.json` — a
     `requires_ip_registration` field owned by S1/BI-D9 — so it can't be forgotten at dispatch.)*
   - `sts:AssumeRole` into `AWS_SCANNER_WRITER_ROLE_ARN` with an inline **session policy**
     narrowed to `roe/<program>/scope.json` (Get), the findings prefix + `runs/<RUN_ID>/*`
     (Put), and KMS; `--duration-seconds` ≈ scan timeout. Capture the session triple.
   - Generate `RUN_ID`. `vultr-cli`/API `instance-create`: region, plan, a **current Ubuntu LTS**
     image, attach the reserved IP + firewall group, `--user-data` = the cloud-init that:
     installs Docker (or uses a Docker-preinstalled image), exports the STS triple + scan argv,
     `docker run ghcr.io/glunk-works/bounty-scanner:<sha> <domain> --program … --contact-url …`,
     captures exit code, writes `runs/<RUN_ID>/status.json`, and best-effort powers off.
   - **Poll S3** for `runs/<RUN_ID>/status.json` (bounded by timeout + margin); read `exit_code`.
   - **Always** `instance-delete` in a step that runs on success, failure, and timeout. When a
     reserved IP was attached, **detach it — never delete it** (deleting loses the registered
     address); it returns to the pool for the next registration-required scan. Fail the job on
     non-zero / missing sentinel.
   - **Never** log the STS creds, the user-data, or any finding (BI-D4). Build all JSON with
     `jq -n --arg`; pass every value via `env:` (CLAUDE.md Actions rules).

5. **Live proof (the acceptance test).** Operator runs `run-scan.yml` against an
   **operator-owned domain** (with a minimal RoE `scope.json` placed in S3 for that owned
   target). Confirm: a Vultr instance boots with the reserved IP, the scan runs, findings land
   in S3 written **from the Vultr IP**, the status sentinel drives a clean exit, and the instance
   is destroyed. Record the run in the build session's `/handoff` — this **is** the Phase-1 DoD.

### Phase 2 — Retire (PR2, teardown; only after Phase-1 proof)

6. **`infra/` — delete the AWS Fargate half.** Remove VPC/IGW/subnet/route/RTA/SG, ECS
   cluster/task-def, ECR repo, CloudWatch log group, `execution_role`/`task_role` + policies +
   attachments; drop the now-unused `outputs.tf` entries (`ecr_repository_url`,
   `ecs_cluster_name`, `subnet_id`, `security_group_id`) and the `image_tag` variable.
   `tofu plan` = **destroys only**, rendered **summarized** (BI-D4: change counts + resource
   addresses, no IDs), approved under BI-D2's `production` Environment gate.

7. **Docs pass** (fold in the outstanding drift BI-D5 flagged):
   - `README.md`: the phantom `build-and-push.yml` is really `build-image.yml`; the "least
     privilege IAM" claim is now *true* (STS re-scope closed #11) — correct both, and describe
     Vultr egress.
   - `CLAUDE.md`: the note "the ECS/Fargate + VPC half of `infra/` is slated for retirement —
     do not extend it" is now **done** — replace with the Vultr reality and the `global-bootstrap`
     writer-role pointer.
   - `docs/hardening_roadmap.md`: mark **SE done** (status + commit); note **#11 closed** via the
     STS re-scope; note #14 partially advanced by the status sentinel.
   - Close/annotate the **#11** issue.

---

## Definition of Done

**Phase 1**
- A **controlled end-to-end scan** runs on a per-scan Vultr VM using the **reserved IP** and
  writes findings to S3. *(Hermetic: `tofu validate`/`tflint`, workflow lints, `zizmor`. Live:
  one controlled scan against an operator-owned target. **Real-program live smoke is deferred →
  tracked on the S1 RoE gate**, not claimed here.)*
- The VM holds **no long-lived credential** — only short-lived, **per-program-scoped** STS
  session creds via user-data. The session policy is least-privilege (the re-scoped **#11**).
- **Zero standing cost in the default state** (SE-MG5): no reserved IP is provisioned; a scan
  dispatched with `use_reserved_ip=false` creates a VM, runs, and destroys it, leaving no
  cost-generating resource behind. The reserved-IP path is exercised/verified with the toggle on
  but is **not** required for the Phase-1 proof.
- The **build path touches no AWS** (GHCR); the VM pulls a **public** image with **no** pull
  credential. Image is **sha-pinned, no `:latest`**, CI-gated by the ruleset as before.
- **No credential, user-data, or finding appears in any workflow log** (BI-D4).
- `global-bootstrap` writer-role PR merged; `run-scan.yml` authenticates through it.

**Phase 2**
- AWS **VPC/ECS/ECR/CloudWatch/Fargate-IAM fully destroyed**; `tofu plan`/`validate`/`tflint`
  green; both PRs approved under BI-D2; the teardown plan was rendered summarized (BI-D4).
- `README.md`, `CLAUDE.md`, `docs/hardening_roadmap.md` updated; SE marked done; **#11 closed**.

---

## Operator procedural gates (not sprints; a coder cannot do these — BI-D5 required controls)

- **Provision + register the reserved IP** *only when onboarding a program that mandates
  source-IP registration/deconfliction* (SE-MG5): flip `reserved_ip_enabled=true`, apply (BI-D2
  gated), register the resulting `reserved_ip_address` with the program, and dispatch that
  program's scans with `use_reserved_ip=true`. Until then there is **no reserved IP and no
  standing cost**.
- **Proactive abuse-team notification** to Vultr with scope + an RoE reference, kept retrievable
  (AUP permission ≠ abuse-desk immunity — BI-D5).
- These, plus **S1's missing RoE `scope.json`** and the **UA contact-URL** check, gate any
  **real-program** live scan. SE's own proof does not depend on them (owned-target scan).

## Constraints & follow-ons (not this sprint)

- **When the reserved IP is in use, those scans serialize** (a single reserved IP ⇒ one
  concurrent registration-required scan). Fully-ephemeral scans (`use_reserved_ip=false`) have
  no such limit. A multi-IP pool is a future scale-up.
- **S2** still owns #12 (pin tools/deps) and the **full** #14 (partial/failed vs clean); SE only
  lays the status-sentinel groundwork. S2 follows SE (its #11 is closed here).
- **DigitalOcean fallback** (BI-D5) remains documented-only.
- **loop-orchestrator adoption (Phase 4)** — unrelated, planned in that repo.

## Pointers

- `docs/hardening_roadmap.md` — **BI-D5** (compute-model decision + *consequences-for-sprints*)
  and the public-repo posture (BI-D4); the threat model.
- `global-bootstrap` — owns the OIDC roles; the `bounty-scanner-s3-writer` role lands there.
- `infra/main.tf`, `.github/workflows/{build-image,run-scan}.yml` — the three files SE rewrites.
