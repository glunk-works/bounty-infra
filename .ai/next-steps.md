# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `implementing`.** Task 5 (the live proof) is
**COMPLETE** as of this session. Phase 2 (PR2, the AWS Fargate teardown) has not
started.

## Just done (this session — found and fixed the actual root cause, live-proved the pipeline)

- **Watched the VM boot live via the Vultr web console** (my.vultr.com) — boot itself
  was always clean; the leading "VM never fully boots" hypothesis from the prior
  session was wrong. Console access needed a restart from the instance's main
  dashboard page, not the console popup's own controls (last session's docs-based
  guidance on that button didn't match the live UI).
- **Root cause found**: `infra/scan-vm-userdata.sh.tftpl` ran
  `apt-get install docker.io awscli` since this file's first commit — Ubuntu 24.04
  has no `awscli` apt candidate, so the whole install failed as a unit and **docker
  was never installed either**, meaning the pipeline's `docker run` was skipped on
  every single dispatch this entire SE saga. Fixed in **PR #74**: install AWS CLI v2
  via its official zip installer instead.
- Dispatched with the fix: pipeline ran end-to-end for the first time (sandbox target,
  exit 0, sentinel written, S3 artifacts landed) — but zero real findings.
- **Second bug found**: `subs_file` contained subfinder's own
  `open /home/sec-ops/.config/subfinder/config.yaml: no such file or directory`
  error (gologger writes this to stdout even under `-silent`). `useradd -r` never
  creates `sec-ops`'s home directory, so subfinder can't init its config; that one
  garbage line was the only "candidate" host, failed scope validation, `kept == 0`,
  and the (correctly tested/pinned) "no subdomains → skip httpx/nuclei" path fired —
  meaning **the pipeline was structurally guaranteed to find nothing**, independent of
  the real target. Fixed in **PR #75**: `HOME=/opt/sec-ops` (already `chown`'d).
- **Live-proved the fixed pipeline against BOTH targets**, post-#75 image
  (`8dab552d548a1cef138773d5b2d9e942710f5c93`):
  - Sandbox (`scanme.nmap.org`/`SANDBOX-NMAP`, run 30110026420): exit 0, zero
    subdomains (expected — trivial single-host domain), base-prefix S3 artifacts
    (`scan_metadata.json`/`raw_findings.json`/`dropped_out_of_scope.json`) confirmed
    present by the operator.
  - Real target (`ztna.myngc.com`/`DIB-VDP`, run 30110630579): same clean exit,
    same base-prefix artifacts confirmed present, zero findings.
- **Investigated the real target's zero findings** (SSH-debug dispatch was too fast to
  connect to before teardown — a ~2min run doesn't leave a usable window; deferred
  that tooling gap rather than fixing it). Instead built `src/Dockerfile`'s image
  **locally** (Docker was already available) and ran `subfinder -d ztna.myngc.com -v`
  directly: confirmed the config fix works, and found that **~30 of subfinder's ~37
  sources have no API key provisioned anywhere**, the few free ones are mostly
  Cloudflare-blocked, and `crtsh`'s direct Postgres query is broken on this (latest)
  subfinder version but silently falls back to its HTTP JSON API, which also found
  zero — consistent with `ztna.myngc.com` being a single-purpose hostname with no
  real subdomains. Filed as **issue #76** (S1/S2 scope, not a live-proof blocker).
- Neither PR #74 nor #75 had a `/critic-gate` pass — both shipped as live-debugging
  fixes, validated by direct dispatch + result inspection instead. Declined a
  retroactive pass this session; same open item as the prior session's #62–71.

## Next

- **Start SE Phase 2 (PR2, sprint_plan.md Tasks 6–7).** No HITL gate blocks starting
  this — it's normal coder work up to opening the PR:
  1. In `infra/`, delete the AWS Fargate half: VPC/IGW/subnet/route/RTA/SG, ECS
     cluster/task-def, ECR repo, CloudWatch log group, `execution_role`/`task_role` +
     policies/attachments. Drop the now-unused `outputs.tf` entries
     (`ecr_repository_url`, `ecs_cluster_name`, `subnet_id`, `security_group_id`) and
     the `image_tag` variable.
  2. `tofu plan` must be **destroys-only**, rendered summarized per BI-D4 (change
     counts + resource addresses, never IDs).
  3. Docs pass: `README.md` (fix the phantom `build-and-push.yml` → `build-image.yml`,
     correct the IAM claim, describe Vultr egress), `CLAUDE.md` (replace the "do not
     extend infra/" note with the Vultr reality + `global-bootstrap` writer-role
     pointer), mark SE done in `docs/hardening_roadmap.md`, close #11.
  - **The actual `tofu apply` still needs BI-D2's protected `production` Environment
    approval** — that's enforced by existing CI/branch-protection, not a manual note
    here.
- Recon-coverage gap (issue #76) is queued separately, not urgent, S1/S2 scope.

## Queued behind PR2

- **S2 — Scanner robustness** — follows SE. The automated-heartbeat idea
  (`runs/<RUN_ID>/progress.json`) from the prior session is still just an idea, needs
  an architect planning pass.
- **SSH-debug tooling gap**: a normal SSH-debug dispatch can complete (and the VM get
  torn down) faster than a human can connect. Noted, not fixed — deferred in favor of
  the local-Docker-repro path this session, which turned out to answer the actual
  question anyway. If it recurs, the fix sketched (and not yet applied) is a
  short releasable hold in `scan-vm-userdata.sh.tftpl`, gated on `operator_ssh_key`
  being set.
- **loop-orchestrator Phase 4** — planned in that repo.

## Still-open operator gates (a coder cannot do these)

- **Reserved IP** — provision only when onboarding a program that mandates
  source-IP registration (MG5): flip `reserved_ip_enabled`, apply, register, dispatch
  with `use_reserved_ip=true`.
- **Proactive abuse-team notification to Vultr** (BI-D5) — not yet done.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; read **BI-D5**.
- `sprints/SE_egress_migration/sprint_plan.md` — the approved plan (MG1–MG5, two-phase
  task breakdown, DoD, operator gates).
- Issue #76 — recon-coverage gap (subfinder has no working sources).
