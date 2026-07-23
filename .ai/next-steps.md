# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `blocked` on operator actions.** PR1 (Phase 1, additive)
merged as [#57](https://github.com/glunk-works/bounty-infra/pull/57). Merging it queued a
real `tofu apply` — it's now sitting on the `production` Environment's required-reviewer
gate (BI-D2), waiting on approval.

## Just done

- **Implemented and merged PR1**: `infra/` gains the Vultr provider and two persistent
  resources (free no-ingress firewall group; `reserved_ip_enabled`-toggled reserved IP,
  default off — zero standing cost, SE-MG5); `build-image.yml` now pushes to public GHCR
  instead of ECR/ECS (SE-MG3); `run-scan.yml` launches/polls/always-destroys a per-scan
  Vultr VM through a session-policy-scoped STS credential + an S3 status-sentinel completion
  signal (SE-MG1/MG2), replacing `ecs run-task`. AWS Fargate/ECS resources are left in place
  as a fallback pending PR2. Merge commit `920eb4c`.
- **Ran `/critic-gate`** (`architect` + `security-critic`, parallel, read-only) before
  merge. Found and fixed one blocker — the cloud-init `docker run` never passed the STS
  creds/bucket name into the container, so the scan would have exited 1 before ever reaching
  S3 — plus an unvalidated `severities` input reaching the VM's shell, an orphaned-VM window
  in the `always()` teardown step, and a timeout/session-duration edge case.
- **Found and fixed a pre-existing bug in `plan-infra.yml`**, surfaced while investigating
  why PR1's `tofu-plan` check showed "0 changes" for a brand-new resource:
  `opentofu/setup-opentofu`'s wrapper script normalizes `-detailed-exitcode`'s two success
  codes (0 = no changes, 2 = changes present) to the same process exit 0, so a script reading
  raw `$?` can never tell them apart. Fixed with `tofu_wrapper: false`. Latent since the
  workflow's creation — PR1 was the first PR since bootstrap to put a real `infra/` diff in
  front of it, which is why it never surfaced before. The real resource-change table (read
  from `plan.json`, independent of `$?`) was correct throughout; this was never a BI-D2
  visible-plan gap, just a misleading diagnostic line.
- **Cursor synced** as [#58](https://github.com/glunk-works/bounty-infra/pull/58), merged.

## Next

- **HITL Gate: OPEN (two, in sequence).**
  1. **Approve the pending apply** —
     [run 30013497825](https://github.com/glunk-works/bounty-infra/actions/runs/30013497825)
     is parked on the `production` Environment reviewer gate for PR1's merge. A coder cannot
     approve its own deploy. Approving it creates the real `vultr_firewall_group` (still zero
     standing cost — the reserved IP stays unprovisioned).
  2. **After that apply succeeds:** run **Task 5, the live proof** (operator-triggered) —
     flip `ghcr.io/glunk-works/bounty-scanner` to **public** visibility on GitHub (Packages →
     package settings; GHCR defaults new packages private and nothing in `build-image.yml`
     can change that), then dispatch `run-scan.yml` against an **operator-owned domain**
     (with a minimal RoE `scope.json` placed in S3 for that target), `use_reserved_ip=false`.
     Confirm: a Vultr instance boots, the scan runs, findings land in S3 **from the Vultr
     IP**, the status sentinel drives a clean exit, the instance is destroyed.
  - **Cross-repo prerequisite (Task 1, `global-bootstrap` — separate repo):** the
    `bounty-scanner-s3-writer` role must land (trust admits `run-scan.yml`'s existing OIDC
    subject; S3 PutObject to findings + `runs/*/status.json`, GetObject on the RoE object,
    KMS DataKey) before `run-scan.yml` can authenticate at all.

## Queued behind the live proof

- **PR2 (teardown)** — delete the AWS Fargate/VPC/ECR/IAM estate as a destroys-only,
  summarized plan (BI-D2); docs pass; mark SE done; close #11. Only after the Phase-1 proof.
- **S2 — Scanner robustness** — follows SE (#11 is closed here; #14 only partly advanced via
  the status sentinel).
- **loop-orchestrator Phase 4** — planned in that repo.

## Still-open operator gates (a coder cannot do these)

- **S1 RoE `scope.json` doesn't exist**; **UA contact-URL** check
  (`https://hackerone.com/seuss`). Both gate any *real-program* scan — SE's Phase-1 proof
  deliberately uses an **operator-owned** target to avoid this.
- **Reserved IP** — provision only when onboarding a program that mandates source-IP
  registration (MG5): flip `reserved_ip_enabled`, apply, register, dispatch with
  `use_reserved_ip=true`. The `reserved_ipv4` field's exact semantics (id vs. address) are
  noted in `run-scan.yml` as unverified against a live call — confirm before the first such
  dispatch.
- **GHCR package visibility** — flip to public after the first `build-image.yml` push,
  before any scan can pull the image.
- Two unrelated, long-stale `deploy-infra.yml` runs (from PRs #35, #27, merged 2026-07-21)
  are still parked "pending"/"waiting" on the same production-environment gate, 40+ hours
  old — likely abandoned/no-op by now, but worth a look (approve-and-verify-no-op, or
  dismiss) next time someone's in the Actions tab.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; read **BI-D5**.
- `sprints/SE_egress_migration/sprint_plan.md` — the approved plan (MG1–MG5, two-phase task
  breakdown, DoD, operator gates).
