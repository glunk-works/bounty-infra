# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `blocked` on operator actions.** PR1 (Phase 1, additive)
merged as [#57](https://github.com/glunk-works/bounty-infra/pull/57) **and applied
successfully** — the real Vultr firewall group now exists (zero standing cost; the reserved
IP stays unprovisioned). Only **Task 5, the live proof**, remains before this phase is done.

## Just done

- **Implemented, critic-passed, and merged PR1**: `infra/` gains the Vultr provider and two
  persistent resources (free no-ingress firewall group; `reserved_ip_enabled`-toggled
  reserved IP, default off — zero standing cost, SE-MG5); `build-image.yml` now pushes to
  public GHCR instead of ECR/ECS (SE-MG3); `run-scan.yml` launches/polls/always-destroys a
  per-scan Vultr VM through a session-policy-scoped STS credential + an S3 status-sentinel
  completion signal (SE-MG1/MG2), replacing `ecs run-task`. AWS Fargate/ECS resources are
  left in place as a fallback pending PR2. Merge commit `920eb4c`.
- **Found and fixed a pre-existing bug in `plan-infra.yml`**: `opentofu/setup-opentofu`'s
  wrapper script normalizes `-detailed-exitcode`'s two success codes (0 = no changes, 2 =
  changes present) to the same process exit 0, so a script reading raw `$?` — as this
  workflow's plan step does — can never tell them apart. Fixed with `tofu_wrapper: false`.
  Latent since the workflow's creation; PR1 was the first PR since bootstrap to put a real
  `infra/` diff in front of it, which is why it never surfaced before. Never a BI-D2
  visible-plan gap — the real resource-change table (read from `plan.json`, independent of
  `$?`) was correct throughout; only a diagnostic line was wrong.
- **Applied PR1.** First attempt failed: Vultr rejected the API call with a 401
  (`"Unauthorized IP address"`) — the `VULTR_API_KEY` had an IP access-control allowlist
  that didn't include GitHub Actions' ephemeral runner IPs. Operator removed the
  restriction; the retry succeeded.
- **Cursor synced** as [#58](https://github.com/glunk-works/bounty-infra/pull/58) and
  [#59](https://github.com/glunk-works/bounty-infra/pull/59), both merged.

## Next

- **HITL Gate: OPEN.** Task 5 (the live proof) is fully operator-gated:
  1. Flip `ghcr.io/glunk-works/bounty-scanner` to **public** visibility on GitHub (Packages →
     package settings; GHCR defaults new packages private and nothing in `build-image.yml`
     can change that).
  2. Confirm the **cross-repo prerequisite** (Task 1, `global-bootstrap` — separate repo) has
     landed: the `bounty-scanner-s3-writer` role (trust admits `run-scan.yml`'s existing OIDC
     subject; S3 PutObject to findings + `runs/*/status.json`, GetObject on the RoE object,
     KMS DataKey). `run-scan.yml` cannot authenticate until this exists.
  3. Dispatch `run-scan.yml` against an **operator-owned domain** (with a minimal RoE
     `scope.json` placed in S3 for that target), `use_reserved_ip=false`, and an `image_tag`
     from a `build-image.yml` run. Confirm: a Vultr instance boots, the scan runs, findings
     land in S3 **from the Vultr IP**, the status sentinel drives a clean exit, the instance
     is destroyed.

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

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; read **BI-D5**.
- `sprints/SE_egress_migration/sprint_plan.md` — the approved plan (MG1–MG5, two-phase task
  breakdown, DoD, operator gates).
