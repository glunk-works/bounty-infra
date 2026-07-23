# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `implementing`.** Plan written and **owner-approved** this
session ([sprints/SE_egress_migration/sprint_plan.md](../sprints/SE_egress_migration/sprint_plan.md)),
five decisions locked. Next up is **PR1** — the additive Vultr stand-up + end-to-end proof.
**Sonnet/Coder.**

## Just done

- **SE planned & approved.** Five micro-gates locked: **MG1** hybrid — tofu owns persistent
  Vultr, `run-scan.yml` owns the ephemeral per-scan VM; **MG2** scoped short-lived STS creds via
  cloud-init user-data (this is the re-scoped #11); **MG3** GHCR public image, build path goes
  AWS-free; **MG4** two-phase: stand-up + prove (PR1), then retire (PR2); **MG5** on-demand,
  registration-aware reserved IP — **zero standing cost by default**, per the cost-ephemerality
  principle.
- **DC archived earlier this session** (PRs #54/#55 merged); `main` at `056fc6d`. Cursor advanced
  DC → SE.

## Next

- **Implement PR1 (Phase 1, additive)** per the plan's task breakdown — the **bounty-infra-local**
  changes:
  - **Task 2** — `infra/`: add the Vultr provider + free firewall group + startup/cloud-init
    template; reserved IP **`count`-gated behind `reserved_ip_enabled` (default false)**; new
    vars/outputs. `tofu fmt`/`validate`/`tflint` green.
  - **Task 3** — `build-image.yml` → GHCR `:<sha>` via `GITHUB_TOKEN`; drop all ECR/AWS/ECS steps.
  - **Task 4** — `run-scan.yml` → Vultr launch-poll-destroy; scoped `sts:AssumeRole`; STS triple
    in user-data; S3 **status sentinel** for the completion signal; `use_reserved_ip` input
    (default false).
  - Run the green gate. **STOP before Task 5 (the live proof)** — it needs the operator **and**
    the cross-repo prerequisite below.
- **Cross-repo prerequisite (Task 1, `global-bootstrap` — separate repo, lands first):** the
  `bounty-scanner-s3-writer` role (S3 PutObject to findings + `runs/*/status.json`, GetObject on
  the RoE object, KMS DataKey), trust admitting `run-scan.yml`'s subject. `run-scan.yml` can't
  authenticate until it exists. Operator-sequenced.
- **HITL Gate: NONE OPEN** (plan approved, PR1 implementation authorized). Next gates in order:
  PR1 review+merge → the live proof → PR2 teardown.

## Queued behind PR1

- **PR2 (teardown)** — delete the AWS Fargate/VPC/ECR/IAM estate as a destroys-only, summarized
  plan (BI-D2); docs pass; mark SE done; close #11. Only after the Phase-1 proof.
- **S2 — Scanner robustness** — follows SE (#11 is closed here; #14 only partly advanced via the
  status sentinel).
- **loop-orchestrator Phase 4** — planned in that repo.

## Still-open operator gates (a coder cannot do these)

- **S1 RoE `scope.json` doesn't exist**; **UA contact-URL** check (`https://hackerone.com/seuss`).
  Both gate any *real-program* scan — SE's Phase-1 proof deliberately uses an **operator-owned**
  target to avoid this.
- **Reserved IP** — provision only when onboarding a program that mandates source-IP registration
  (MG5): flip `reserved_ip_enabled`, apply, register, dispatch with `use_reserved_ip=true`.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; read **BI-D5**.
- `sprints/SE_egress_migration/sprint_plan.md` — the approved plan (MG1–MG5, two-phase task
  breakdown, DoD, operator gates).
